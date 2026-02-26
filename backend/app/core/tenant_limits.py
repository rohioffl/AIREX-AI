"""
Tenant limit enforcement.

Checks tenant limits before creating incidents or executing actions.
"""

import uuid
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IncidentState
from app.models.incident import Incident
from app.models.tenant_limit import TenantLimit
from app.models.execution import Execution

logger = structlog.get_logger()


async def check_concurrent_incidents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> tuple[bool, int, int]:
    """
    Check if tenant has exceeded max concurrent incidents.
    
    Returns: (allowed, current_count, max_allowed)
    """
    # Get tenant limit (default if not set)
    limit_result = await session.execute(
        select(TenantLimit).where(TenantLimit.tenant_id == tenant_id)
    )
    limit = limit_result.scalar_one_or_none()
    max_allowed = limit.max_concurrent_incidents if limit else 50
    
    # Count active incidents
    count_result = await session.execute(
        select(func.count()).select_from(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state.in_([
                IncidentState.RECEIVED,
                IncidentState.INVESTIGATING,
                IncidentState.RECOMMENDATION_READY,
                IncidentState.AWAITING_APPROVAL,
                IncidentState.EXECUTING,
                IncidentState.VERIFYING,
            ]),
        )
    )
    current_count = count_result.scalar_one() or 0
    
    allowed = current_count < max_allowed
    
    if not allowed:
        logger.warning(
            "tenant_limit_exceeded",
            tenant_id=str(tenant_id),
            limit_type="concurrent_incidents",
            current=current_count,
            max=max_allowed,
        )
    
    return allowed, current_count, max_allowed


async def check_daily_executions(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> tuple[bool, int, int]:
    """
    Check if tenant has exceeded max daily executions.
    
    Returns: (allowed, current_count, max_allowed)
    """
    # Get tenant limit (default if not set)
    limit_result = await session.execute(
        select(TenantLimit).where(TenantLimit.tenant_id == tenant_id)
    )
    limit = limit_result.scalar_one_or_none()
    max_allowed = limit.max_daily_executions if limit else 200
    
    # Count executions today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    count_result = await session.execute(
        select(func.count()).select_from(Execution).where(
            Execution.tenant_id == tenant_id,
            Execution.started_at >= today_start,
        )
    )
    current_count = count_result.scalar_one() or 0
    
    allowed = current_count < max_allowed
    
    if not allowed:
        logger.warning(
            "tenant_limit_exceeded",
            tenant_id=str(tenant_id),
            limit_type="daily_executions",
            current=current_count,
            max=max_allowed,
        )
    
    return allowed, current_count, max_allowed
