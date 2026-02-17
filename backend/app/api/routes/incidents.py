"""
Incident CRUD + approval endpoint.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select

from app.api.dependencies import Redis, TenantId, TenantSession
from app.core.rate_limit import approval_rate_limit
from app.core.config import settings
from app.core.state_machine import IllegalStateTransition, transition_state
from app.models.enums import IncidentState, SeverityLevel
from app.models.incident import Incident
from app.schemas.incident import (
    ApproveRequest,
    IncidentCreatedResponse,
    IncidentDetail,
    IncidentListItem,
    PaginatedIncidents,
    RelatedIncidentItem,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/", response_model=PaginatedIncidents)
async def list_incidents(
    tenant_id: TenantId,
    session: TenantSession,
    state: IncidentState | None = None,
    severity: SeverityLevel | None = None,
    alert_type: str | None = None,
    limit: int = Query(default=50, le=200),
    cursor: str | None = Query(default=None, description="ISO timestamp cursor for keyset pagination"),
    offset: int = Query(default=0, ge=0, description="Legacy offset-based pagination"),
) -> PaginatedIncidents:
    """
    List incidents for the current tenant, newest first.

    Supports both keyset (cursor) and offset pagination.
    Cursor takes priority when provided.
    """
    base_filters = [
        Incident.tenant_id == tenant_id,
        Incident.deleted_at.is_(None),
    ]
    if state is not None:
        base_filters.append(Incident.state == state)
    if severity is not None:
        base_filters.append(Incident.severity == severity)
    if alert_type is not None:
        base_filters.append(Incident.alert_type == alert_type)

    # Count total (for first page only, when no cursor)
    total = None
    if cursor is None and offset == 0:
        count_q = select(func.count()).select_from(Incident).where(*base_filters)
        total_result = await session.execute(count_q)
        total = total_result.scalar_one()

    # Build query
    query = (
        select(Incident)
        .where(*base_filters)
        .order_by(desc(Incident.created_at), desc(Incident.id))
        .limit(limit + 1)
    )

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError:
            cursor_dt = datetime.now(timezone.utc)
        query = query.where(Incident.created_at < cursor_dt)
    elif offset > 0:
        query = query.offset(offset)

    result = await session.execute(query)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = last.created_at.isoformat() if last.created_at else None

    items = [IncidentListItem.model_validate(i) for i in rows]

    return PaginatedIncidents(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        total=total,
    )


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> IncidentDetail:
    """Get full incident detail including evidence, transitions, and executions."""
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    # Recommendation is stored in meta (populated by AI service)
    recommendation = None
    if incident.meta and "recommendation" in incident.meta:
        recommendation = incident.meta["recommendation"]

    # Related incidents: same host (host_key), same tenant, exclude self
    related: list = []
    if incident.host_key:
        related_result = await session.execute(
            select(Incident)
            .where(
                Incident.tenant_id == tenant_id,
                Incident.host_key == incident.host_key,
                Incident.id != incident_id,
                Incident.deleted_at.is_(None),
            )
            .order_by(desc(Incident.created_at))
            .limit(20)
        )
        for other in related_result.scalars().all():
            related.append(
                RelatedIncidentItem(
                    id=other.id,
                    alert_type=other.alert_type,
                    state=other.state,
                    severity=other.severity,
                    title=other.title,
                    created_at=other.created_at,
                )
            )

    return IncidentDetail(
        id=incident.id,
        tenant_id=incident.tenant_id,
        alert_type=incident.alert_type,
        state=incident.state,
        severity=incident.severity,
        title=incident.title,
        investigation_retry_count=incident.investigation_retry_count,
        execution_retry_count=incident.execution_retry_count,
        verification_retry_count=incident.verification_retry_count,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        evidence=incident.evidence,
        state_transitions=incident.state_transitions,
        executions=incident.executions,
        recommendation=recommendation,
        meta=incident.meta,
        related_incidents=related,
    )


@router.post(
    "/{incident_id}/approve",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IncidentCreatedResponse,
    dependencies=[Depends(approval_rate_limit)],
)
async def approve_incident(
    incident_id: uuid.UUID,
    body: ApproveRequest,
    tenant_id: TenantId,
    session: TenantSession,
    redis: Redis,
) -> IncidentCreatedResponse:
    """
    Approve an action for execution.

    1. Validate state == AWAITING_APPROVAL
    2. Acquire distributed Redis lock
    3. Transition to EXECUTING
    4. Queue async execution task
    """
    # Fetch incident
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    if incident.state != IncidentState.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incident is in state {incident.state.value}, expected AWAITING_APPROVAL",
        )

    # Idempotency check
    idem_exists = await redis.get(f"approve:{tenant_id}:{body.idempotency_key}")
    if idem_exists:
        logger.info(
            "duplicate_approval_rejected",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
        )
        return IncidentCreatedResponse(incident_id=incident.id)

    # Acquire distributed lock
    lock_key = f"lock:incident:{tenant_id}:{incident_id}"
    lock_acquired = await redis.set(
        lock_key,
        f"approval:{body.idempotency_key}",
        nx=True,
        ex=settings.LOCK_TTL,
    )
    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Incident is currently locked by another operation",
        )

    try:
        # Validate action is in registry
        from app.actions.registry import ACTION_REGISTRY

        if body.action not in ACTION_REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: {body.action}. Not in ACTION_REGISTRY.",
            )

        # Transition state
        await transition_state(
            session,
            incident,
            IncidentState.EXECUTING,
            reason=f"Approved action: {body.action}",
            actor="human_approval",
        )

        # Mark idempotency key (TTL = 1 hour)
        await redis.set(
            f"approve:{tenant_id}:{body.idempotency_key}",
            str(incident.id),
            ex=3600,
        )

        logger.info(
            "incident_approved",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
            action=body.action,
        )

        # Enqueue execution task via ARQ
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            await pool.enqueue_job(
                "execute_action_task",
                str(tenant_id),
                str(incident_id),
                body.action,
            )
            await pool.aclose()
            logger.info("execution_task_enqueued", incident_id=str(incident_id), action=body.action)
        except Exception as enq_exc:
            logger.error("execution_enqueue_failed", error=str(enq_exc))

    except IllegalStateTransition as exc:
        await redis.delete(lock_key)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return IncidentCreatedResponse(incident_id=incident.id)
