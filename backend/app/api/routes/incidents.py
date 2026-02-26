"""
Incident CRUD + approval endpoint.
"""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm.attributes import flag_modified

from app.api.dependencies import (
    CurrentUser,
    Redis,
    TenantId,
    TenantSession,
    require_role,
)
from app.core.rate_limit import approval_rate_limit
from app.core.config import settings
from app.core.state_machine import IllegalStateTransition, transition_state
from app.models.enums import IncidentState, SeverityLevel
from app.models.incident import Incident
from app.schemas.incident import (
    ApproveRequest,
    EvidenceResponse,
    ExecutionResponse,
    IncidentCreatedResponse,
    IncidentDetail,
    IncidentListItem,
    PaginatedIncidents,
    RecommendationResponse,
    RejectRequest,
    RelatedIncidentItem,
    StateTransitionResponse,
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
    host_key: str | None = Query(
        default=None,
        description="Filter by host_key to show incidents from the same server",
    ),
    search: str | None = Query(
        default=None, description="Search in title, alert_type, and meta fields"
    ),
    limit: int = Query(default=50, le=200),
    cursor: str | None = Query(
        default=None, description="ISO timestamp cursor for keyset pagination"
    ),
    offset: int = Query(default=0, ge=0, description="Legacy offset-based pagination"),
) -> PaginatedIncidents:
    """
    List incidents for the current tenant, newest first.

    Supports both keyset (cursor) and offset pagination.
    Cursor takes priority when provided.
    Search queries match against title, alert_type, and meta JSON fields.
    """
    from sqlalchemy import or_, cast, String

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
    if host_key is not None:
        base_filters.append(Incident.host_key == host_key)

    # Search functionality: match against title, alert_type, or meta JSON
    if search and search.strip():
        search_term = f"%{search.strip().lower()}%"
        base_filters.append(
            or_(
                Incident.title.ilike(search_term),
                Incident.alert_type.ilike(search_term),
                cast(Incident.meta, String).ilike(search_term),
            )
        )

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
        try:
            recommendation = RecommendationResponse.model_validate(
                incident.meta["recommendation"]
            )
        except Exception:
            # If validation fails, try to use raw dict (for backwards compatibility)
            rec_dict = incident.meta["recommendation"]
            if isinstance(rec_dict, dict) and "proposed_action" in rec_dict:
                from app.models.enums import RiskLevel

                recommendation = RecommendationResponse(
                    root_cause=rec_dict.get("root_cause", ""),
                    proposed_action=rec_dict.get("proposed_action", ""),
                    risk_level=RiskLevel(rec_dict.get("risk_level", "MED")),
                    confidence=float(rec_dict.get("confidence", 0.8)),
                )

    rag_context = None
    if incident.meta and "rag_context" in incident.meta:
        rag_context = incident.meta["rag_context"]

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

    evidence = [EvidenceResponse.model_validate(e) for e in incident.evidence]
    transitions = [
        StateTransitionResponse.model_validate(t) for t in incident.state_transitions
    ]
    executions = [ExecutionResponse.model_validate(ex) for ex in incident.executions]

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
        evidence=evidence,
        state_transitions=transitions,
        executions=executions,
        recommendation=recommendation,
        meta=incident.meta,
        rag_context=rag_context,
        related_incidents=related,
        host_key=incident.host_key,
    )


@router.post(
    "/{incident_id}/approve",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IncidentCreatedResponse,
    dependencies=[
        Depends(approval_rate_limit),
        Depends(require_role("operator", "admin")),
    ],
)
async def approve_incident(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    redis: Redis,
    body: ApproveRequest,
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

    # Idempotency check — return early if already processed
    idem_key = f"approve:{tenant_id}:{body.idempotency_key}"
    idem_exists = await redis.get(idem_key)
    if idem_exists:
        logger.info(
            "duplicate_approval_rejected",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
        )
        return IncidentCreatedResponse(incident_id=incident.id)

    # Acquire distributed lock to prevent double-execution
    lock_key = f"lock:exec:{tenant_id}:{incident_id}"
    lock_acquired = await redis.set(
        lock_key,
        f"approve:{datetime.now(timezone.utc).isoformat()}",
        nx=True,
        ex=settings.LOCK_TTL,
    )
    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another approval is already being processed for this incident",
        )

    try:
        # Transition to EXECUTING
        try:
            await transition_state(
                session,
                incident,
                IncidentState.EXECUTING,
                reason=f"Approved by operator — action: {body.action}",
                actor="operator",
            )
        except IllegalStateTransition as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        # Mark idempotency key (24h TTL)
        await redis.set(idem_key, "1", ex=86400)

        # Queue async execution task via ARQ
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
        except Exception:
            logger.exception(
                "failed_to_enqueue_execution",
                tenant_id=str(tenant_id),
                incident_id=str(incident_id),
                action=body.action,
            )
            # Execution enqueue failure is non-fatal; the worker retry
            # scheduler will pick it up. Don't roll back the state transition.

        logger.info(
            "incident_approved",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
            action=body.action,
        )
    finally:
        await redis.delete(lock_key)

    return IncidentCreatedResponse(incident_id=incident.id)


@router.post(
    "/{incident_id}/reject",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IncidentCreatedResponse,
    dependencies=[Depends(require_role("operator", "admin"))],
)
async def reject_incident(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    body: RejectRequest,
) -> IncidentCreatedResponse:
    """
    Reject (skip) an incident.

    Moves the incident to REJECTED state (terminal).
    """
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

    manual_reason = (body.reason or "").strip()
    transition_reason = manual_reason or "Manually rejected by operator"

    meta = dict(incident.meta or {})
    meta["_manual_review_required"] = True
    meta["_manual_review_reason"] = transition_reason
    meta["_manual_review_actor"] = "human_rejection"
    meta["_manual_review_at"] = datetime.now(timezone.utc).isoformat()
    incident.meta = meta
    flag_modified(incident, "meta")
    session.add(incident)
    await session.flush()

    try:
        await transition_state(
            session,
            incident,
            IncidentState.REJECTED,
            reason=transition_reason,
            actor="human_rejection",
        )
    except IllegalStateTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    logger.info(
        "incident_rejected",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
    )

    return IncidentCreatedResponse(incident_id=incident.id)


@router.delete(
    "/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("operator", "admin"))],
)
async def soft_delete_incident(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> None:
    """
    Soft delete an incident (admin/operator only).

    Sets deleted_at timestamp. Incident must be in a terminal state
    (RESOLVED, REJECTED, FAILED_EXECUTION, FAILED_VERIFICATION).
    """
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
            Incident.deleted_at.is_(None),
        )
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found or already deleted",
        )

    # Only allow soft delete for terminal states
    terminal_states = {
        IncidentState.RESOLVED,
        IncidentState.REJECTED,
        IncidentState.FAILED_EXECUTION,
        IncidentState.FAILED_VERIFICATION,
    }
    if incident.state not in terminal_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete incident in state {incident.state.value}. Only terminal states can be deleted.",
        )

    incident.deleted_at = datetime.now(timezone.utc)
    await session.flush()

    logger.info(
        "incident_soft_deleted",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
        state=incident.state.value,
    )
