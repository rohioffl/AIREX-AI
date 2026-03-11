"""Core incident operations: create, list, get, approve."""

import uuid

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.incident import Incident

logger = structlog.get_logger()


async def create_incident(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    alert_type: str,
    severity: SeverityLevel,
    title: str,
    meta: dict | None = None,
) -> Incident:
    """Create a new incident in RECEIVED state."""
    incident = Incident(
        tenant_id=tenant_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        meta=meta,
    )
    session.add(incident)
    await session.flush()

    logger.info(
        "incident_created",
        tenant_id=str(tenant_id),
        incident_id=str(incident.id),
        correlation_id=str(incident.id),
        alert_type=alert_type,
    )
    return incident


async def get_incident(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    incident_id: uuid.UUID,
) -> Incident | None:
    """Fetch a single incident scoped to tenant."""
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )
    )
    return result.scalar_one_or_none()


async def list_incidents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    state: IncidentState | None = None,
    severity: SeverityLevel | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Incident]:
    """List incidents for a tenant, newest first. Always tenant-scoped."""
    query = (
        select(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
        )
        .order_by(desc(Incident.created_at))
        .limit(limit)
        .offset(offset)
    )
    if state is not None:
        query = query.where(Incident.state == state)
    if severity is not None:
        query = query.where(Incident.severity == severity)

    result = await session.execute(query)
    return list(result.scalars().all())
