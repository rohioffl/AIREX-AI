"""
Anomaly detection service.

Detects unusual incident frequency, severity patterns, and deviations
from normal operational baselines.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.incident import Incident

logger = structlog.get_logger()

# ── Thresholds ───────────────────────────────────────────────

FREQUENCY_Z_SCORE_THRESHOLD: float = 2.0  # Standard deviations from mean
SEVERITY_ESCALATION_THRESHOLD: float = 0.3  # 30% increase in critical incidents
RESOLUTION_TIME_THRESHOLD: float = 2.0  # 2x the baseline resolution time


async def detect_anomalies(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    baseline_days: int = 30,
    detection_window_hours: int = 24,
) -> dict[str, Any]:
    """
    Detect anomalies across multiple dimensions.

    Compares recent incident patterns against a baseline period.
    """
    log = logger.bind(tenant_id=str(tenant_id))
    now = datetime.now(timezone.utc)
    baseline_start = now - timedelta(days=baseline_days)
    detection_start = now - timedelta(hours=detection_window_hours)

    # Fetch baseline incidents
    baseline_result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.created_at >= baseline_start,
            Incident.created_at < detection_start,
            Incident.deleted_at.is_(None),
        )
    )
    baseline_incidents = list(baseline_result.scalars().all())

    # Fetch recent incidents
    recent_result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.created_at >= detection_start,
            Incident.deleted_at.is_(None),
        )
    )
    recent_incidents = list(recent_result.scalars().all())

    anomalies: list[dict[str, Any]] = []

    # 1. Frequency anomaly
    freq_anomaly = _detect_frequency_anomaly(
        baseline_incidents, recent_incidents, baseline_days, detection_window_hours
    )
    if freq_anomaly:
        anomalies.append(freq_anomaly)

    # 2. Severity distribution anomaly
    sev_anomaly = _detect_severity_anomaly(baseline_incidents, recent_incidents)
    if sev_anomaly:
        anomalies.append(sev_anomaly)

    # 3. Resolution time anomaly
    res_anomaly = _detect_resolution_time_anomaly(baseline_incidents, recent_incidents)
    if res_anomaly:
        anomalies.append(res_anomaly)

    # 4. New alert type anomaly
    type_anomaly = _detect_new_alert_types(baseline_incidents, recent_incidents)
    if type_anomaly:
        anomalies.append(type_anomaly)

    # 5. Failure rate anomaly
    fail_anomaly = _detect_failure_rate_anomaly(baseline_incidents, recent_incidents)
    if fail_anomaly:
        anomalies.append(fail_anomaly)

    # 6. Host concentration anomaly
    host_anomaly = _detect_host_concentration(recent_incidents)
    if host_anomaly:
        anomalies.append(host_anomaly)

    log.info(
        "anomaly_detection_complete",
        anomaly_count=len(anomalies),
        baseline_count=len(baseline_incidents),
        recent_count=len(recent_incidents),
    )

    return {
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "baseline_period_days": baseline_days,
        "detection_window_hours": detection_window_hours,
        "baseline_incident_count": len(baseline_incidents),
        "recent_incident_count": len(recent_incidents),
        "checked_at": now.isoformat(),
    }


def _detect_frequency_anomaly(
    baseline: list[Incident],
    recent: list[Incident],
    baseline_days: int,
    window_hours: int,
) -> dict[str, Any] | None:
    """Detect if incident frequency is abnormally high or low."""
    if not baseline:
        return None

    baseline_daily = len(baseline) / max(baseline_days, 1)
    baseline_hourly = baseline_daily / 24
    recent_hourly = len(recent) / max(window_hours, 1)

    # Group baseline by day for std deviation
    daily_counts: dict[str, int] = defaultdict(int)
    for inc in baseline:
        if inc.created_at:
            day_key = inc.created_at.strftime("%Y-%m-%d")
            daily_counts[day_key] += 1

    counts = list(daily_counts.values()) if daily_counts else [0]
    mean = sum(counts) / len(counts)
    variance = sum((c - mean) ** 2 for c in counts) / len(counts)
    std_dev = variance**0.5 if variance > 0 else 1

    recent_daily_equivalent = recent_hourly * 24
    z_score = (recent_daily_equivalent - mean) / std_dev if std_dev > 0 else 0

    if abs(z_score) >= FREQUENCY_Z_SCORE_THRESHOLD:
        direction = "spike" if z_score > 0 else "drop"
        return {
            "type": "frequency_anomaly",
            "severity": "high" if abs(z_score) > 3 else "medium",
            "direction": direction,
            "description": f"Incident frequency {direction}: {recent_hourly:.1f}/hr vs baseline {baseline_hourly:.1f}/hr",
            "z_score": round(z_score, 2),
            "current_rate_per_hour": round(recent_hourly, 2),
            "baseline_rate_per_hour": round(baseline_hourly, 2),
            "recent_count": len(recent),
        }
    return None


def _detect_severity_anomaly(
    baseline: list[Incident], recent: list[Incident]
) -> dict[str, Any] | None:
    """Detect shifts in severity distribution."""
    if not baseline or not recent:
        return None

    baseline_critical = sum(1 for i in baseline if i.severity == SeverityLevel.CRITICAL)
    recent_critical = sum(1 for i in recent if i.severity == SeverityLevel.CRITICAL)

    baseline_ratio = baseline_critical / len(baseline)
    recent_ratio = recent_critical / len(recent) if recent else 0

    if recent_ratio > baseline_ratio + SEVERITY_ESCALATION_THRESHOLD and recent_critical >= 2:
        return {
            "type": "severity_escalation",
            "severity": "high",
            "description": f"Critical incident ratio increased: {recent_ratio:.0%} vs baseline {baseline_ratio:.0%}",
            "current_critical_ratio": round(recent_ratio, 3),
            "baseline_critical_ratio": round(baseline_ratio, 3),
            "recent_critical_count": recent_critical,
        }
    return None


def _detect_resolution_time_anomaly(
    baseline: list[Incident], recent: list[Incident]
) -> dict[str, Any] | None:
    """Detect if resolution times are abnormally long."""
    baseline_times = [
        i.resolution_duration_seconds
        for i in baseline
        if i.resolution_duration_seconds and i.state == IncidentState.RESOLVED
    ]
    recent_times = [
        i.resolution_duration_seconds
        for i in recent
        if i.resolution_duration_seconds and i.state == IncidentState.RESOLVED
    ]

    if not baseline_times or not recent_times:
        return None

    baseline_avg = sum(baseline_times) / len(baseline_times)
    recent_avg = sum(recent_times) / len(recent_times)

    if recent_avg > baseline_avg * RESOLUTION_TIME_THRESHOLD:
        return {
            "type": "slow_resolution",
            "severity": "medium",
            "description": f"Resolution time increased: {recent_avg:.0f}s vs baseline {baseline_avg:.0f}s",
            "current_avg_seconds": round(recent_avg),
            "baseline_avg_seconds": round(baseline_avg),
            "ratio": round(recent_avg / baseline_avg, 2),
        }
    return None


def _detect_new_alert_types(
    baseline: list[Incident], recent: list[Incident]
) -> dict[str, Any] | None:
    """Detect previously unseen alert types."""
    baseline_types = set(i.alert_type for i in baseline)
    recent_types = set(i.alert_type for i in recent)
    new_types = recent_types - baseline_types

    if new_types:
        return {
            "type": "new_alert_types",
            "severity": "low",
            "description": f"{len(new_types)} new alert type(s) detected",
            "new_types": sorted(new_types),
        }
    return None


def _detect_failure_rate_anomaly(
    baseline: list[Incident], recent: list[Incident]
) -> dict[str, Any] | None:
    """Detect increase in failed resolutions."""
    failed_states = {IncidentState.FAILED_EXECUTION, IncidentState.FAILED_VERIFICATION}

    baseline_failed = sum(1 for i in baseline if i.state in failed_states)
    recent_failed = sum(1 for i in recent if i.state in failed_states)

    baseline_rate = baseline_failed / len(baseline) if baseline else 0
    recent_rate = recent_failed / len(recent) if recent else 0

    if recent_rate > baseline_rate + 0.15 and recent_failed >= 2:
        return {
            "type": "high_failure_rate",
            "severity": "high",
            "description": f"Failure rate increased: {recent_rate:.0%} vs baseline {baseline_rate:.0%}",
            "current_failure_rate": round(recent_rate, 3),
            "baseline_failure_rate": round(baseline_rate, 3),
            "recent_failed_count": recent_failed,
        }
    return None


def _detect_host_concentration(
    recent: list[Incident],
) -> dict[str, Any] | None:
    """Detect if incidents are concentrated on a single host."""
    if len(recent) < 3:
        return None

    host_counts = Counter(i.host_key for i in recent if i.host_key)
    if not host_counts:
        return None

    top_host, top_count = host_counts.most_common(1)[0]
    concentration = top_count / len(recent)

    if concentration > 0.5 and top_count >= 3:
        return {
            "type": "host_concentration",
            "severity": "medium",
            "description": f"Host '{top_host}' has {concentration:.0%} of recent incidents ({top_count}/{len(recent)})",
            "host": top_host,
            "incident_count": top_count,
            "concentration_ratio": round(concentration, 3),
        }
    return None
