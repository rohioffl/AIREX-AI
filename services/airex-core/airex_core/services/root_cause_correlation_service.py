"""
Root cause correlation service.

Enhances the correlation service to identify common root causes across
different incident types and build a root cause knowledge graph.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident

logger = structlog.get_logger()


async def find_common_root_causes(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    days: int = 90,
    min_occurrences: int = 2,
) -> list[dict[str, Any]]:
    """
    Identify common root causes across different alert types.

    Analyzes resolved incidents to find root causes that appear
    across multiple alert types, indicating systemic issues.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.state == IncidentState.RESOLVED,
            Incident.created_at >= cutoff,
            Incident.deleted_at.is_(None),
        )
    )
    incidents = list(result.scalars().all())

    # Extract root causes with their associated alert types
    root_cause_map: dict[str, list[dict]] = defaultdict(list)
    for inc in incidents:
        meta = inc.meta or {}
        rec = meta.get("recommendation", {})
        root_cause = rec.get("root_cause")
        if not root_cause:
            continue

        root_cause_normalized = root_cause.strip().lower()
        root_cause_map[root_cause_normalized].append({
            "incident_id": str(inc.id),
            "alert_type": inc.alert_type,
            "severity": inc.severity.value,
            "host_key": inc.host_key,
            "resolution_type": inc.resolution_type,
            "resolution_seconds": inc.resolution_duration_seconds,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
        })

    # Filter to root causes meeting minimum occurrences
    common_root_causes = []
    for root_cause, occurrences in root_cause_map.items():
        if len(occurrences) < min_occurrences:
            continue

        alert_types = Counter(o["alert_type"] for o in occurrences)
        severities = Counter(o["severity"] for o in occurrences)
        hosts = set(o["host_key"] for o in occurrences if o["host_key"])
        resolution_times = [o["resolution_seconds"] for o in occurrences if o["resolution_seconds"]]
        resolution_types = Counter(o["resolution_type"] for o in occurrences if o["resolution_type"])

        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else None

        # Cross-type indicator: appears in multiple alert types
        is_cross_type = len(alert_types) > 1

        common_root_causes.append({
            "root_cause": root_cause,
            "occurrence_count": len(occurrences),
            "is_cross_type": is_cross_type,
            "alert_types": dict(alert_types),
            "severity_distribution": dict(severities),
            "affected_hosts": sorted(hosts),
            "avg_resolution_seconds": round(avg_resolution) if avg_resolution else None,
            "resolution_types": dict(resolution_types),
            "most_recent": max(o["created_at"] for o in occurrences if o["created_at"]),
            "sample_incident_ids": [o["incident_id"] for o in occurrences[:5]],
        })

    return sorted(
        common_root_causes,
        key=lambda x: (-int(x["is_cross_type"]), -x["occurrence_count"]),
    )


async def get_root_cause_graph(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    days: int = 90,
) -> dict[str, Any]:
    """
    Build a root cause dependency graph showing relationships
    between root causes, alert types, hosts, and actions.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.state == IncidentState.RESOLVED,
            Incident.created_at >= cutoff,
            Incident.deleted_at.is_(None),
        )
    )
    incidents = list(result.scalars().all())

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    for inc in incidents:
        meta = inc.meta or {}
        rec = meta.get("recommendation", {})
        root_cause = rec.get("root_cause")
        proposed_action = rec.get("proposed_action")
        if not root_cause:
            continue

        rc_id = f"rc:{root_cause.strip().lower()}"
        at_id = f"at:{inc.alert_type}"
        action_id = f"action:{proposed_action}" if proposed_action else None

        # Add nodes
        if rc_id not in node_ids:
            nodes.append({"id": rc_id, "label": root_cause, "type": "root_cause"})
            node_ids.add(rc_id)
        if at_id not in node_ids:
            nodes.append({"id": at_id, "label": inc.alert_type, "type": "alert_type"})
            node_ids.add(at_id)
        if action_id and action_id not in node_ids:
            nodes.append({"id": action_id, "label": proposed_action, "type": "action"})
            node_ids.add(action_id)

        if inc.host_key:
            host_id = f"host:{inc.host_key}"
            if host_id not in node_ids:
                nodes.append({"id": host_id, "label": inc.host_key, "type": "host"})
                node_ids.add(host_id)
            edges.append({"source": rc_id, "target": host_id, "type": "affects"})

        # Add edges
        edges.append({"source": at_id, "target": rc_id, "type": "caused_by"})
        if action_id:
            edges.append({"source": rc_id, "target": action_id, "type": "resolved_by"})

    # Deduplicate edges and count occurrences
    edge_counter: dict[str, int] = {}
    unique_edges: list[dict] = []
    for edge in edges:
        key = f"{edge['source']}:{edge['target']}:{edge['type']}"
        if key not in edge_counter:
            edge_counter[key] = 0
            unique_edges.append(edge)
        edge_counter[key] += 1

    for edge in unique_edges:
        key = f"{edge['source']}:{edge['target']}:{edge['type']}"
        edge["weight"] = edge_counter[key]

    return {
        "nodes": nodes,
        "edges": unique_edges,
        "node_count": len(nodes),
        "edge_count": len(unique_edges),
    }


async def suggest_root_cause_for_incident(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    incident: Incident,
) -> dict[str, Any] | None:
    """
    Suggest a likely root cause for a new incident based on historical data.
    """
    common = await find_common_root_causes(
        session, tenant_id, days=90, min_occurrences=2
    )
    if not common:
        return None

    # Find root causes for the same alert type
    matching = [
        rc for rc in common
        if incident.alert_type in rc["alert_types"]
    ]

    if not matching:
        return None

    top = matching[0]
    return {
        "suggested_root_cause": top["root_cause"],
        "confidence": min(top["occurrence_count"] / 10, 0.95),
        "historical_occurrences": top["occurrence_count"],
        "is_cross_type": top["is_cross_type"],
        "avg_resolution_seconds": top["avg_resolution_seconds"],
    }
