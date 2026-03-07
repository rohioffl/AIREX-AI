"""
Cross-host incident correlation/grouping (Phase 4 ARE).

Detects when multiple hosts experience the same alert type within a time
window and groups them under a shared correlation_group_id. This enables
operators to see the blast radius of infrastructure-wide issues.

Correlation rules:
  - Same tenant_id
  - Same alert_type
  - Within CORRELATION_WINDOW_MINUTES of each other
  - Different host_key (cross-host, not same-host repeats)

The correlation_group_id is a deterministic hash of
(tenant_id + alert_type + time_bucket), so all incidents in the same
bucket automatically share the same group.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident

logger = structlog.get_logger()

# Window size: incidents of the same alert_type within this window
# are considered correlated.
CORRELATION_WINDOW_MINUTES: int = 15


def compute_correlation_group_id(
    tenant_id: uuid.UUID,
    alert_type: str,
    timestamp: datetime,
) -> str:
    """
    Deterministic group ID based on tenant + alert_type + time bucket.

    Uses 15-minute time buckets so that incidents arriving in the same
    window get the same group ID automatically.
    """
    bucket = timestamp.replace(
        minute=(timestamp.minute // CORRELATION_WINDOW_MINUTES)
        * CORRELATION_WINDOW_MINUTES,
        second=0,
        microsecond=0,
    )
    raw = f"{tenant_id}:{alert_type}:{bucket.isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def correlate_incident(
    session: AsyncSession,
    incident: Incident,
) -> str | None:
    """
    Assign a correlation group to an incident if cross-host siblings exist.

    Returns the correlation_group_id if the incident was grouped,
    None if it's a standalone incident (no cross-host matches).
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        correlation_id=str(incident.id),
        alert_type=incident.alert_type,
    )

    now = incident.created_at or datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=CORRELATION_WINDOW_MINUTES)

    group_id = compute_correlation_group_id(
        incident.tenant_id,
        incident.alert_type,
        now,
    )

    # Find recent incidents with the same alert_type in the same window
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == incident.tenant_id,
            Incident.alert_type == incident.alert_type,
            Incident.id != incident.id,
            Incident.created_at >= window_start,
            Incident.deleted_at.is_(None),
        )
    )
    siblings = result.scalars().all()

    # Filter to cross-host only (different host_key)
    cross_host = [
        s
        for s in siblings
        if s.host_key != incident.host_key
        or (s.host_key is None and incident.host_key is None)
    ]

    if not cross_host:
        log.debug("no_cross_host_siblings")
        return None

    # Assign the group to this incident
    incident.correlation_group_id = group_id

    # Also assign the group to any siblings that don't have one yet
    updated_count = 0
    for sibling in cross_host:
        if sibling.correlation_group_id is None:
            sibling.correlation_group_id = group_id
            updated_count += 1

    log.info(
        "correlation_group_assigned",
        group_id=group_id,
        cross_host_count=len(cross_host),
        updated_siblings=updated_count,
    )

    return group_id


async def get_correlated_incidents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    correlation_group_id: str,
    exclude_id: uuid.UUID | None = None,
) -> list[Incident]:
    """
    Fetch all incidents in a correlation group.
    """
    filters = [
        Incident.tenant_id == tenant_id,
        Incident.correlation_group_id == correlation_group_id,
        Incident.deleted_at.is_(None),
    ]
    if exclude_id is not None:
        filters.append(Incident.id != exclude_id)

    result = await session.execute(
        select(Incident).where(*filters).order_by(Incident.created_at.desc())
    )
    return list(result.scalars().all())


async def get_correlation_summary(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    correlation_group_id: str,
) -> dict[str, Any]:
    """
    Build a summary of a correlation group for API responses.
    """
    result = await session.execute(
        select(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.correlation_group_id == correlation_group_id,
            Incident.deleted_at.is_(None),
        )
        .order_by(Incident.created_at.asc())
    )
    incidents = list(result.scalars().all())

    if not incidents:
        return {}

    host_keys = set()
    states: dict[str, int] = {}
    severities: dict[str, int] = {}

    for inc in incidents:
        if inc.host_key:
            host_keys.add(inc.host_key)
        state_val = inc.state.value
        states[state_val] = states.get(state_val, 0) + 1
        sev_val = inc.severity.value
        severities[sev_val] = severities.get(sev_val, 0) + 1

    first = incidents[0]
    last = incidents[-1]

    return {
        "group_id": correlation_group_id,
        "alert_type": first.alert_type,
        "incident_count": len(incidents),
        "affected_hosts": len(host_keys),
        "host_keys": sorted(host_keys),
        "states": states,
        "severities": severities,
        "first_seen": first.created_at.isoformat() if first.created_at else None,
        "last_seen": last.created_at.isoformat() if last.created_at else None,
        "span_seconds": int((last.created_at - first.created_at).total_seconds())
        if first.created_at and last.created_at
        else 0,
    }
