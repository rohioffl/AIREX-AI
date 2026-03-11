"""
Incident pattern detection using clustering.

Groups similar incidents based on alert_type, severity, host patterns,
and resolution outcomes to identify recurring patterns and reduce noise.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.incident import Incident

logger = structlog.get_logger()

# ── Configuration ────────────────────────────────────────────

PATTERN_WINDOW_DAYS: int = 30
MIN_CLUSTER_SIZE: int = 3
SIMILARITY_THRESHOLD: float = 0.7


def _feature_vector(incident: Incident) -> dict[str, Any]:
    """Extract features from an incident for clustering."""
    meta = incident.meta or {}
    recommendation = meta.get("recommendation", {})
    return {
        "alert_type": incident.alert_type,
        "severity": incident.severity.value if incident.severity else "UNKNOWN",
        "host_key": incident.host_key or "unknown",
        "root_cause": recommendation.get("root_cause", ""),
        "proposed_action": recommendation.get("proposed_action", ""),
        "resolution_type": incident.resolution_type or "",
    }


def _compute_similarity(a: dict, b: dict) -> float:
    """Compute similarity score between two feature vectors."""
    score = 0.0
    weights = {
        "alert_type": 0.35,
        "severity": 0.10,
        "root_cause": 0.25,
        "proposed_action": 0.20,
        "host_key": 0.10,
    }
    for key, weight in weights.items():
        val_a = str(a.get(key, "")).lower().strip()
        val_b = str(b.get(key, "")).lower().strip()
        if val_a and val_b:
            if val_a == val_b:
                score += weight
            elif val_a in val_b or val_b in val_a:
                score += weight * 0.5
    return score


def _generate_pattern_id(
    tenant_id: uuid.UUID, alert_type: str, root_cause: str
) -> str:
    """Deterministic pattern group ID."""
    raw = f"{tenant_id}:{alert_type}:{root_cause}".lower()
    return f"pat_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


async def detect_patterns(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    window_days: int = PATTERN_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """
    Detect incident patterns using a simplified DBSCAN-like approach.

    Returns a list of pattern groups with their incidents and metadata.
    """
    log = logger.bind(tenant_id=str(tenant_id))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    result = await session.execute(
        select(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.created_at >= cutoff,
            Incident.deleted_at.is_(None),
        )
        .order_by(Incident.created_at.desc())
    )
    incidents = list(result.scalars().all())

    if len(incidents) < MIN_CLUSTER_SIZE:
        log.debug("insufficient_incidents_for_clustering", count=len(incidents))
        return []

    # Extract features
    features = [(inc, _feature_vector(inc)) for inc in incidents]

    # Group by alert_type + root_cause (simplified clustering)
    clusters: dict[str, list[tuple[Incident, dict]]] = defaultdict(list)
    for inc, feat in features:
        key = f"{feat['alert_type']}::{feat.get('root_cause', 'unknown')}"
        clusters[key].append((inc, feat))

    # Filter to clusters meeting minimum size
    patterns = []
    for cluster_key, members in clusters.items():
        if len(members) < MIN_CLUSTER_SIZE:
            continue

        incidents_in_cluster = [m[0] for m in members]
        features_in_cluster = [m[1] for m in members]

        # Compute pattern metadata
        alert_type = features_in_cluster[0]["alert_type"]
        root_cause = features_in_cluster[0].get("root_cause", "Unknown")
        pattern_id = _generate_pattern_id(tenant_id, alert_type, root_cause)

        severities = Counter(f["severity"] for f in features_in_cluster)
        hosts = set(f["host_key"] for f in features_in_cluster if f["host_key"] != "unknown")
        actions = Counter(f["proposed_action"] for f in features_in_cluster if f["proposed_action"])
        resolution_types = Counter(f["resolution_type"] for f in features_in_cluster if f["resolution_type"])

        # Compute resolution stats
        resolved = [i for i in incidents_in_cluster if i.state == IncidentState.RESOLVED]
        avg_resolution = None
        if resolved:
            durations = [i.resolution_duration_seconds for i in resolved if i.resolution_duration_seconds]
            if durations:
                avg_resolution = sum(durations) / len(durations)

        # Frequency analysis
        timestamps = sorted([i.created_at for i in incidents_in_cluster if i.created_at])
        frequency_per_day = len(timestamps) / max(window_days, 1)

        # Trend: increasing or decreasing
        if len(timestamps) >= 4:
            mid = len(timestamps) // 2
            first_half = timestamps[:mid]
            second_half = timestamps[mid:]
            first_span = (first_half[-1] - first_half[0]).total_seconds() or 1
            second_span = (second_half[-1] - second_half[0]).total_seconds() or 1
            first_rate = len(first_half) / first_span
            second_rate = len(second_half) / second_span
            trend = "increasing" if second_rate > first_rate * 1.2 else (
                "decreasing" if second_rate < first_rate * 0.8 else "stable"
            )
        else:
            trend = "insufficient_data"

        patterns.append({
            "pattern_id": pattern_id,
            "alert_type": alert_type,
            "root_cause": root_cause,
            "incident_count": len(incidents_in_cluster),
            "incident_ids": [str(i.id) for i in incidents_in_cluster[:20]],
            "severity_distribution": dict(severities),
            "affected_hosts": sorted(hosts),
            "common_actions": dict(actions.most_common(3)),
            "resolution_types": dict(resolution_types),
            "avg_resolution_seconds": avg_resolution,
            "frequency_per_day": round(frequency_per_day, 2),
            "trend": trend,
            "first_seen": timestamps[0].isoformat() if timestamps else None,
            "last_seen": timestamps[-1].isoformat() if timestamps else None,
        })

    # Assign pattern_group_id to incidents
    for pattern in patterns:
        pid = pattern["pattern_id"]
        for inc_id_str in pattern["incident_ids"]:
            for inc, _ in features:
                if str(inc.id) == inc_id_str and not inc.pattern_group_id:
                    inc.pattern_group_id = pid

    log.info("patterns_detected", pattern_count=len(patterns))
    return sorted(patterns, key=lambda p: p["incident_count"], reverse=True)


async def get_pattern_summary(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    pattern_id: str,
) -> dict[str, Any] | None:
    """Get detailed summary for a specific pattern group."""
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.pattern_group_id == pattern_id,
            Incident.deleted_at.is_(None),
        )
    )
    incidents = list(result.scalars().all())
    if not incidents:
        return None

    return {
        "pattern_id": pattern_id,
        "incident_count": len(incidents),
        "incidents": [
            {
                "id": str(i.id),
                "title": i.title,
                "state": i.state.value,
                "severity": i.severity.value,
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "resolution_type": i.resolution_type,
            }
            for i in incidents
        ],
    }
