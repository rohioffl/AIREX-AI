"""
Incident CRUD + approval endpoint.
"""

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel

from app.api.dependencies import (
    CurrentUser,
    Redis,
    RequireOperator,
    TenantId,
    TenantSession,
)
from airex_core.core.rate_limit import approval_rate_limit
from airex_core.core.config import settings
from airex_core.core.state_machine import IllegalStateTransition, transition_state
from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.comment import Comment
from airex_core.models.user import User
from airex_core.models.feedback_learning import FeedbackLearning
from airex_core.models.incident import Incident
from airex_core.models.incident_template import IncidentTemplate
from airex_core.models.related_incident import RelatedIncident
from airex_core.schemas.incident import (
    ApproveRequest,
    CorrelatedIncidentItem,
    CorrelationGroupSummary,
    EvidenceResponse,
    ExecutionResponse,
    FeedbackRequest,
    FeedbackResponse,
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


# ── Manual Incident Creation Schemas ──────────────────────────────


class ManualIncidentCreateRequest(BaseModel):
    title: str
    description: str | None = None
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    alert_type: str
    host_key: str | None = None
    meta: dict | None = None


# ── Bulk Operations Schemas ──────────────────────────────────────


class BulkApproveRequest(BaseModel):
    incident_ids: list[uuid.UUID]
    reason: str | None = None


class BulkRejectRequest(BaseModel):
    incident_ids: list[uuid.UUID]
    reason: str


# ── Comment Schemas ──────────────────────────────────────────────


class CommentCreateRequest(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str
    user_display_name: str
    content: str
    created_at: datetime


# ── Assignment Schemas ────────────────────────────────────────────


class AssignRequest(BaseModel):
    assigned_to: uuid.UUID | None = None  # None = unassign


# ── Manual Incident Creation ──────────────────────────────────────


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=IncidentCreatedResponse,
)
async def create_incident_manual(
    body: ManualIncidentCreateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    redis: Redis,
    current_user: CurrentUser,
    template_id: Optional[uuid.UUID] = Query(
        None, description="Optional template ID to pre-fill fields"
    ),
    _role: RequireOperator = None,
) -> IncidentCreatedResponse:
    """
    Manually create an incident (for operators/admins).

    Optionally use a template to pre-fill fields.
    """
    from airex_core.services.incident_service import create_incident
    from airex_core.core.tenant_limits import check_concurrent_incidents

    # If template_id provided, load template and merge with body
    if template_id:
        result = await session.execute(
            select(IncidentTemplate).where(
                IncidentTemplate.tenant_id == tenant_id,
                IncidentTemplate.id == template_id,
                IncidentTemplate.is_active,
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found or inactive",
            )

        # Merge template defaults with body (body takes precedence)
        title = body.title or template.default_title or "Manual Incident"
        severity_str = body.severity or template.severity
        alert_type = body.alert_type or template.alert_type
        meta = {**(template.default_meta or {}), **(body.meta or {})}
    else:
        title = body.title
        severity_str = body.severity
        alert_type = body.alert_type
        meta = body.meta

    # Validate severity
    try:
        severity = SeverityLevel(severity_str.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity: {severity_str}. Must be one of: CRITICAL, HIGH, MEDIUM, LOW",
        )

    # Check tenant limits
    allowed, current, max_allowed = await check_concurrent_incidents(session, tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Tenant limit exceeded: {current}/{max_allowed} concurrent incidents.",
        )

    # Create incident
    incident = await create_incident(
        session=session,
        tenant_id=tenant_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        meta=meta,
    )

    # Set host_key if provided
    if body.host_key:
        incident.host_key = body.host_key

    # Set description if provided
    if body.description:
        incident.description = body.description

    await session.flush()

    # Transition to INVESTIGATING
    await transition_state(
        session,
        incident,
        IncidentState.INVESTIGATING,
        reason=f"Manual incident creation by {current_user.user_email}",
        actor=str(current_user.user_id),
    )

    logger.info(
        "manual_incident_created",
        tenant_id=str(tenant_id),
        incident_id=str(incident.id),
        template_id=str(template_id) if template_id else None,
        user_id=str(current_user.user_id),
    )

    # Enqueue investigation
    try:
        from arq import create_pool
        from arq.connections import RedisSettings
        from airex_core.core.config import settings as app_settings

        pool = await create_pool(RedisSettings.from_dsn(app_settings.REDIS_URL))
        await pool.enqueue_job("investigate_incident", str(tenant_id), str(incident.id))
        await pool.aclose()
        logger.info("investigation_task_enqueued", incident_id=str(incident.id))
    except Exception as exc:
        logger.error("investigation_enqueue_failed", error=str(exc))

    return IncidentCreatedResponse(incident_id=incident.id)


# ── List Incidents ────────────────────────────────────────────────


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
        default=None,
        description="Search in title, alert_type, meta, and evidence fields",
    ),
    date_from: datetime | None = Query(
        default=None,
        description="Filter incidents created after this date (ISO format)",
    ),
    date_to: datetime | None = Query(
        default=None,
        description="Filter incidents created before this date (ISO format)",
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
    Search queries match against title, alert_type, meta JSON fields, and evidence.
    """
    from sqlalchemy import String, cast, or_
    from airex_core.models.evidence import Evidence

    logger.info("incidents_list_requested", tenant_id=str(tenant_id))

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

    # Search functionality: match against title, alert_type, meta JSON, and evidence
    if search and search.strip():
        search_term = f"%{search.strip().lower()}%"

        # Search in incident fields
        incident_search = or_(
            Incident.title.ilike(search_term),
            Incident.alert_type.ilike(search_term),
            cast(Incident.meta, String).ilike(search_term),
        )

        # Also search in evidence raw_output (subquery)
        evidence_subq = (
            select(Evidence.incident_id)
            .where(
                Evidence.tenant_id == tenant_id,
                Evidence.raw_output.ilike(search_term),
            )
            .distinct()
        )

        base_filters.append(
            or_(
                incident_search,
                Incident.id.in_(evidence_subq),
            )
        )

    # Date range filters
    if date_from:
        base_filters.append(Incident.created_at >= date_from)
    if date_to:
        base_filters.append(Incident.created_at <= date_to)

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


# ── Get Incident ──────────────────────────────────────────────────


@router.get("/{incident_id:uuid}", response_model=IncidentDetail)
async def get_incident(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> IncidentDetail:
    """Get detailed incident information."""
    logger.info(
        "incident_detail_requested",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
    )
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
            detail="Incident not found",
        )

    # Recommendation is stored in meta (populated by AI service)
    recommendation = None
    if incident.meta and "recommendation" in incident.meta:
        try:
            recommendation = RecommendationResponse.model_validate(
                incident.meta["recommendation"]
            )
        except (TypeError, ValueError) as exc:
            logger.warning(
                "incident_recommendation_parse_failed",
                tenant_id=str(tenant_id),
                incident_id=str(incident_id),
                error=str(exc),
            )
            # If validation fails, try to use raw dict (for backwards compatibility)
            rec_dict = incident.meta["recommendation"]
            if isinstance(rec_dict, dict) and "proposed_action" in rec_dict:
                from airex_core.models.enums import RiskLevel

                recommendation = RecommendationResponse(
                    root_cause=rec_dict.get("root_cause", ""),
                    proposed_action=rec_dict.get("proposed_action", ""),
                    risk_level=RiskLevel(rec_dict.get("risk_level", "MED")),
                    confidence=rec_dict.get("confidence", 0.0),
                )

    rag_context = None
    if incident.meta and "rag_context" in incident.meta:
        rag_context = incident.meta["rag_context"]

    # Related incidents: same host (host_key) + manually linked incidents
    related: list[RelatedIncidentItem] = []
    related_ids = set()

    # 1. Same host incidents (automatic)
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
            if other.id not in related_ids:
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
                related_ids.add(other.id)

    # 2. Manually linked incidents (explicit relationships)
    manual_links_result = await session.execute(
        select(RelatedIncident, Incident)
        .join(
            Incident,
            (RelatedIncident.tenant_id == Incident.tenant_id)
            & (RelatedIncident.related_incident_id == Incident.id),
        )
        .where(
            RelatedIncident.tenant_id == tenant_id,
            RelatedIncident.incident_id == incident_id,
        )
    )
    for rel, other in manual_links_result.all():
        if other.id not in related_ids:
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
            related_ids.add(other.id)

    evidence = [EvidenceResponse.model_validate(e) for e in incident.evidence]
    transitions = [
        StateTransitionResponse.model_validate(t) for t in incident.state_transitions
    ]
    executions = [ExecutionResponse.model_validate(ex) for ex in incident.executions]

    # Cross-host correlated incidents (Phase 4 ARE)
    correlated: list[CorrelatedIncidentItem] = []
    correlation_summary_data: CorrelationGroupSummary | None = None
    if incident.correlation_group_id:
        try:
            from airex_core.services.correlation_service import get_correlated_incidents

            correlated_list = await get_correlated_incidents(
                session,
                tenant_id,
                incident.correlation_group_id,
                exclude_id=incident_id,
            )
            for other in correlated_list:
                correlated.append(
                    CorrelatedIncidentItem(
                        id=other.id,
                        alert_type=other.alert_type,
                        state=other.state,
                        severity=other.severity,
                        title=other.title,
                        created_at=other.created_at,
                    )
                )

            # Build summary
            if correlated_list:
                earliest = min(c.created_at for c in correlated_list)
                latest = max(c.created_at for c in correlated_list)
                span = int((latest - earliest).total_seconds())
                correlation_summary_data = CorrelationGroupSummary(
                    group_id=incident.correlation_group_id,
                    count=len(correlated_list) + 1,  # +1 for self
                    span_seconds=span,
                )
        except Exception as exc:
            logger.warning(
                "correlation_lookup_failed",
                tenant_id=str(tenant_id),
                incident_id=str(incident_id),
                error=str(exc),
            )

    return IncidentDetail(
        id=incident.id,
        tenant_id=incident.tenant_id,
        alert_type=incident.alert_type,
        state=incident.state,
        severity=incident.severity,
        title=incident.title,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        investigation_retry_count=incident.investigation_retry_count,
        execution_retry_count=incident.execution_retry_count,
        verification_retry_count=incident.verification_retry_count,
        host_key=incident.host_key,
        correlation_group_id=incident.correlation_group_id,
        resolution_type=incident.resolution_type,
        resolution_summary=incident.resolution_summary,
        resolution_duration_seconds=incident.resolution_duration_seconds,
        feedback_score=incident.feedback_score,
        feedback_note=incident.feedback_note,
        resolved_at=incident.resolved_at,
        evidence=evidence,
        state_transitions=transitions,
        executions=executions,
        recommendation=recommendation,
        related_incidents=related,
        rag_context=rag_context,
        correlated_incidents=correlated,
        correlation_summary=correlation_summary_data,
    )


# ── Approve ───────────────────────────────────────────────────────


@router.post(
    "/{incident_id:uuid}/approve",
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
    current_user: CurrentUser,
) -> IncidentCreatedResponse:
    """
    Approve an incident's recommended action.

    Requires AWAITING_APPROVAL state.
    Enqueues execution task via ARQ.
    Idempotent via idempotency_key (Redis).
    """
    actor_email = current_user.sub if current_user else "system"
    actor_user_id = str(current_user.user_id) if current_user else "system"

    logger.info(
        "incident_approval_requested",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
        action=body.action,
        user_id=actor_user_id,
    )

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
            detail="Incident not found",
        )

    if incident.state != IncidentState.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incident must be in AWAITING_APPROVAL state, current: {incident.state.value}",
        )

    # Idempotency check
    idempotency_key = f"approve:{tenant_id}:{incident_id}:{body.idempotency_key}"
    existing = await redis.get(idempotency_key)
    if existing:
        logger.info(
            "approval_idempotent_skip",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
            idempotency_key=body.idempotency_key,
        )
        return IncidentCreatedResponse(incident_id=incident.id)

    # Validate action exists in registry
    from airex_core.actions.registry import ACTION_REGISTRY

    if body.action not in ACTION_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action: {body.action}. Must be one of: {', '.join(ACTION_REGISTRY.keys())}",
        )

    # Transition to EXECUTING
    try:
        await transition_state(
            session,
            incident,
            IncidentState.EXECUTING,
            reason=f"Approved by {actor_email}: {body.action}",
            actor=actor_email,
        )
    except IllegalStateTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition: {exc}",
        ) from exc

    # Store idempotency key (TTL 1 hour)
    await redis.setex(idempotency_key, 3600, "approved")

    # Track feedback learning
    try:
        meta = incident.meta or {}
        rec = meta.get("recommendation", {})
        confidence_before = rec.get("confidence")
        feedback = FeedbackLearning(
            tenant_id=tenant_id,
            incident_id=incident.id,
            recommendation_id=body.idempotency_key,
            action_taken="approved",
            user_id=current_user.user_id if current_user else None,
            confidence_before=confidence_before,
            confidence_after=confidence_before,  # Approved = confidence maintained
        )
        session.add(feedback)
    except Exception as exc:
        logger.warning("feedback_learning_tracking_failed", error=str(exc))

    # Enqueue execution task
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await pool.enqueue_job(
            "execute_action_task",
            str(incident.tenant_id),
            str(incident.id),
            body.action,
        )
        await pool.aclose()
        logger.info("execution_enqueued", action=body.action)
    except Exception as exc:
        logger.error("execution_enqueue_failed", error=str(exc))
        # Don't fail the approval, execution will be retried

    await session.commit()

    return IncidentCreatedResponse(incident_id=incident.id)


# ── Reject ────────────────────────────────────────────────────────


@router.post(
    "/{incident_id:uuid}/reject",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IncidentCreatedResponse,
)
async def reject_incident(
    incident_id: uuid.UUID,
    body: RejectRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> IncidentCreatedResponse:
    """
    Reject an incident (operator-only action).

    Transitions to REJECTED state and stores rejection reason in meta.
    """
    actor_email = current_user.sub if current_user else "system"
    actor_user_id = str(current_user.user_id) if current_user else "system"

    logger.info(
        "incident_rejection_requested",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
        user_id=actor_user_id,
    )

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
            detail="Incident not found",
        )

    # REJECTED can be reached from any non-terminal state
    if incident.state in (IncidentState.RESOLVED, IncidentState.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject incident in terminal state: {incident.state.value}",
        )

    # Update meta with rejection reason
    rejection_reason = body.reason or "Manually rejected by operator"
    meta = dict(incident.meta or {})
    meta["_manual_review_reason"] = rejection_reason
    meta["_manual_review_required"] = True
    incident.meta = meta
    flag_modified(incident, "meta")

    # Transition to REJECTED
    try:
        await transition_state(
            session,
            incident,
            IncidentState.REJECTED,
            reason=rejection_reason,
            actor=actor_email,
        )
    except IllegalStateTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid state transition: {exc}",
        ) from exc

    await session.commit()

    return IncidentCreatedResponse(incident_id=incident.id)


# ── Acknowledge ───────────────────────────────────────────────────


@router.post("/{incident_id:uuid}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_incident(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
    _: RequireOperator,
) -> dict:
    """
    Mark an incident as acknowledged (seen) by the current user.

    Stores acknowledged_by and acknowledged_at in incident.meta.
    Idempotent — re-acknowledging overwrites the previous entry.
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    actor = current_user.sub if current_user else "system"
    meta = dict(incident.meta or {})
    meta["acknowledged_by"] = actor
    meta["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    incident.meta = meta
    flag_modified(incident, "meta")
    await session.commit()

    logger.info("incident_acknowledged", incident_id=str(incident_id), by=actor)
    return {"status": "acknowledged", "acknowledged_by": actor}


# ── Feedback ───────────────────────────────────────────────────────


@router.post(
    "/{incident_id:uuid}/feedback",
    status_code=status.HTTP_200_OK,
    response_model=FeedbackResponse,
)
async def submit_feedback(
    incident_id: uuid.UUID,
    body: FeedbackRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> FeedbackResponse:
    """
    Submit operator feedback on a resolved/rejected incident.

    Stores feedback_score (-1 to 5) and optional feedback_note.
    """
    logger.info(
        "incident_feedback_submitted",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
        score=body.score,
        user_id=str(current_user.user_id),
    )

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
            detail="Incident not found",
        )

    # Only allow feedback on terminal states
    if incident.state not in (IncidentState.RESOLVED, IncidentState.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Feedback can only be submitted for resolved/rejected incidents. Current state: {incident.state.value}",
        )

    # Update feedback fields
    incident.feedback_score = body.score
    incident.feedback_note = body.note
    await session.commit()

    return FeedbackResponse(
        incident_id=incident.id,
        feedback_score=body.score,
        feedback_note=body.note,
    )


# ── Soft Delete ────────────────────────────────────────────────────


@router.delete("/{incident_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> None:
    """
    Soft delete an incident (sets deleted_at).

    Only allowed for terminal states (RESOLVED, REJECTED, FAILED_EXECUTION, FAILED_VERIFICATION).
    """
    logger.info(
        "incident_deletion_requested",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
        user_id=str(current_user.user_id),
    )

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
            detail="Incident not found",
        )

    # Only allow deletion of terminal states
    terminal_states = {
        IncidentState.RESOLVED,
        IncidentState.REJECTED,
        IncidentState.FAILED_EXECUTION,
        IncidentState.FAILED_VERIFICATION,
    }
    if incident.state not in terminal_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete incident in non-terminal state: {incident.state.value}",
        )

    incident.deleted_at = datetime.now(timezone.utc)
    await session.commit()

    logger.info(
        "incident_deleted",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
    )


# ── Restore ────────────────────────────────────────────────────────


@router.post("/{incident_id:uuid}/restore", status_code=status.HTTP_200_OK)
async def restore_incident(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> dict:
    """
    Restore a soft-deleted incident (clears deleted_at).
    """
    logger.info(
        "incident_restore_requested",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
        user_id=str(current_user.user_id),
    )

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

    if incident.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incident is not deleted",
        )

    incident.deleted_at = None
    await session.commit()

    logger.info(
        "incident_restored",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
    )

    return {
        "message": "Incident restored successfully",
        "incident_id": str(incident_id),
    }


# ── Bulk Operations ────────────────────────────────────────────────


@router.post("/bulk-approve", status_code=status.HTTP_200_OK)
async def bulk_approve(
    body: BulkApproveRequest,
    tenant_id: TenantId,
    session: TenantSession,
    redis: Redis,
    current_user: CurrentUser,
) -> dict:
    """
    Approve multiple incidents in bulk.

    Only processes incidents in AWAITING_APPROVAL state.
    Returns count of successfully approved incidents.
    """
    actor_email = current_user.sub if current_user else "system"
    actor_user_id = str(current_user.user_id) if current_user else "system"

    logger.info(
        "bulk_approval_requested",
        tenant_id=str(tenant_id),
        count=len(body.incident_ids),
        user_id=actor_user_id,
    )

    if not body.incident_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No incident IDs provided",
        )

    # Fetch all incidents
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id.in_(body.incident_ids),
            Incident.deleted_at.is_(None),
            Incident.state == IncidentState.AWAITING_APPROVAL,
        )
    )
    incidents = list(result.scalars().all())

    approved_count = 0
    errors = []

    for incident in incidents:
        try:
            # Get recommendation action
            rec = incident.meta.get("recommendation") if incident.meta else None
            if not rec or not isinstance(rec, dict):
                errors.append(f"Incident {incident.id}: No recommendation found")
                continue

            action = rec.get("proposed_action")
            if not action:
                errors.append(f"Incident {incident.id}: No proposed action")
                continue

            # Validate action
            from airex_core.actions.registry import ACTION_REGISTRY

            if action not in ACTION_REGISTRY:
                errors.append(f"Incident {incident.id}: Unknown action {action}")
                continue

            # Transition to EXECUTING
            reason = body.reason or f"Bulk approved by {actor_email}"
            await transition_state(
                session,
                incident,
                IncidentState.EXECUTING,
                reason=reason,
                actor=actor_email,
            )

            # Enqueue execution
            try:
                from arq import create_pool
                from arq.connections import RedisSettings

                pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
                await pool.enqueue_job(
                    "execute_action_task",
                    str(incident.tenant_id),
                    str(incident.id),
                    action,
                )
                await pool.aclose()
            except Exception as exc:
                logger.warning(
                    "bulk_execution_enqueue_failed",
                    incident_id=str(incident.id),
                    error=str(exc),
                )

            approved_count += 1
        except Exception as exc:
            errors.append(f"Incident {incident.id}: {str(exc)}")
            logger.warning(
                "bulk_approval_item_failed",
                incident_id=str(incident.id),
                error=str(exc),
            )

    await session.commit()

    return {
        "approved_count": approved_count,
        "total_requested": len(body.incident_ids),
        "errors": errors,
    }


@router.post("/bulk-reject", status_code=status.HTTP_200_OK)
async def bulk_reject(
    body: BulkRejectRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> dict:
    """
    Reject multiple incidents in bulk.

    Only processes incidents in non-terminal states.
    Returns count of successfully rejected incidents.
    """
    actor_email = current_user.sub if current_user else "system"
    actor_user_id = str(current_user.user_id) if current_user else "system"

    logger.info(
        "bulk_rejection_requested",
        tenant_id=str(tenant_id),
        count=len(body.incident_ids),
        user_id=actor_user_id,
    )

    if not body.incident_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No incident IDs provided",
        )

    # Fetch all incidents
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id.in_(body.incident_ids),
            Incident.deleted_at.is_(None),
        )
    )
    incidents = list(result.scalars().all())

    rejected_count = 0
    errors = []

    terminal_states = {IncidentState.RESOLVED, IncidentState.REJECTED}

    for incident in incidents:
        try:
            if incident.state in terminal_states:
                errors.append(
                    f"Incident {incident.id}: Already in terminal state {incident.state.value}"
                )
                continue

            # Update meta
            meta = dict(incident.meta or {})
            meta["_manual_review_reason"] = body.reason
            meta["_manual_review_required"] = True
            incident.meta = meta
            flag_modified(incident, "meta")

            # Transition to REJECTED
            await transition_state(
                session,
                incident,
                IncidentState.REJECTED,
                reason=body.reason,
                actor=actor_email,
            )

            rejected_count += 1
        except Exception as exc:
            errors.append(f"Incident {incident.id}: {str(exc)}")
            logger.warning(
                "bulk_rejection_item_failed",
                incident_id=str(incident.id),
                error=str(exc),
            )

    await session.commit()

    return {
        "rejected_count": rejected_count,
        "total_requested": len(body.incident_ids),
        "errors": errors,
    }


# ── Comments ────────────────────────────────────────────────────────


@router.get("/{incident_id:uuid}/comments", response_model=list[CommentResponse])
async def list_comments(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> list[CommentResponse]:
    """List all comments for an incident."""
    from airex_core.models.comment import Comment
    from airex_core.models.user import User

    result = await session.execute(
        select(Comment)
        .join(User, Comment.user_id == User.id)
        .where(
            Comment.tenant_id == tenant_id,
            Comment.incident_id == incident_id,
        )
        .order_by(Comment.created_at.asc())
    )
    comments = result.scalars().all()

    return [
        CommentResponse(
            id=c.id,
            incident_id=c.incident_id,
            user_id=c.user_id,
            user_email=c.user.email,
            user_display_name=c.user.display_name,
            content=c.content,
            created_at=c.created_at,
        )
        for c in comments
    ]


@router.post(
    "/{incident_id:uuid}/comments",
    status_code=status.HTTP_201_CREATED,
    response_model=CommentResponse,
)
async def create_comment(
    incident_id: uuid.UUID,
    body: CommentCreateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> CommentResponse:
    """Create a comment on an incident."""

    # Verify incident exists
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
            detail="Incident not found",
        )

    # Create comment
    comment = Comment(
        tenant_id=tenant_id,
        incident_id=incident_id,
        user_id=current_user.user_id,
        content=body.content,
    )
    session.add(comment)
    await session.flush()

    # Fetch user for response
    user_result = await session.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.id == current_user.user_id,
        )
    )
    user = user_result.scalar_one()

    logger.info(
        "comment_created",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
        comment_id=str(comment.id),
        user_id=str(current_user.user_id),
    )

    return CommentResponse(
        id=comment.id,
        incident_id=comment.incident_id,
        user_id=comment.user_id,
        user_email=user.email,
        user_display_name=user.display_name,
        content=comment.content,
        created_at=comment.created_at,
    )


# ── Assignment ──────────────────────────────────────────────────────


@router.post("/{incident_id:uuid}/assign", status_code=status.HTTP_200_OK)
async def assign_incident(
    incident_id: uuid.UUID,
    body: AssignRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> dict:
    """
    Assign or unassign an incident to a user.

    If assigned_to is None, unassigns the incident.
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
            detail="Incident not found",
        )

    # Verify assigned user exists if provided
    if body.assigned_to:
        user_result = await session.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.id == body.assigned_to,
            )
        )
        assigned_user = user_result.scalar_one_or_none()
        if assigned_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned user not found",
            )

    # Update incident meta with assignment
    meta = dict(incident.meta or {})
    if body.assigned_to:
        meta["assigned_to"] = str(body.assigned_to)
        meta["assigned_by"] = str(current_user.user_id)
        meta["assigned_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(
            "incident_assigned",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
            assigned_to=str(body.assigned_to),
            assigned_by=str(current_user.user_id),
        )
    else:
        meta.pop("assigned_to", None)
        meta.pop("assigned_by", None)
        meta.pop("assigned_at", None)
        logger.info(
            "incident_unassigned",
            tenant_id=str(tenant_id),
            incident_id=str(incident_id),
            unassigned_by=str(current_user.user_id),
        )

    incident.meta = meta
    flag_modified(incident, "meta")
    await session.commit()

    return {
        "message": "Incident assigned" if body.assigned_to else "Incident unassigned",
        "incident_id": str(incident_id),
        "assigned_to": str(body.assigned_to) if body.assigned_to else None,
    }


# ── Export ──────────────────────────────────────────────────────────


@router.get("/export")
async def export_incidents(
    tenant_id: TenantId,
    session: TenantSession,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    state: IncidentState | None = None,
    severity: SeverityLevel | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=1000, le=10000),
) -> Response:
    """
    Export incidents as JSON or CSV.

    Supports filtering by state, severity, and date range.
    """
    base_filters = [
        Incident.tenant_id == tenant_id,
        Incident.deleted_at.is_(None),
    ]
    if state is not None:
        base_filters.append(Incident.state == state)
    if severity is not None:
        base_filters.append(Incident.severity == severity)
    if date_from:
        base_filters.append(Incident.created_at >= date_from)
    if date_to:
        base_filters.append(Incident.created_at <= date_to)

    result = await session.execute(
        select(Incident)
        .where(*base_filters)
        .order_by(desc(Incident.created_at))
        .limit(limit)
    )
    incidents = result.scalars().all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "Title",
                "Alert Type",
                "State",
                "Severity",
                "Host Key",
                "Created At",
                "Updated At",
                "Resolved At",
            ]
        )
        for inc in incidents:
            writer.writerow(
                [
                    str(inc.id),
                    inc.title,
                    inc.alert_type,
                    inc.state.value,
                    inc.severity.value,
                    inc.host_key or "",
                    inc.created_at.isoformat() if inc.created_at else "",
                    inc.updated_at.isoformat() if inc.updated_at else "",
                    inc.resolved_at.isoformat() if inc.resolved_at else "",
                ]
            )
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=incidents.csv"},
        )
    else:  # JSON
        items = [
            {
                "id": str(inc.id),
                "tenant_id": str(inc.tenant_id),
                "alert_type": inc.alert_type,
                "state": inc.state.value,
                "severity": inc.severity.value,
                "title": inc.title,
                "host_key": inc.host_key,
                "created_at": inc.created_at.isoformat() if inc.created_at else None,
                "updated_at": inc.updated_at.isoformat() if inc.updated_at else None,
                "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
                "meta": inc.meta,
                "evidence_count": len(inc.evidence),
                "execution_count": len(inc.executions),
            }
            for inc in incidents
        ]
        return Response(
            content=json.dumps(items, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=incidents.json"},
        )


# ── Related Incidents ──────────────────────────────────────────────────────


class LinkIncidentRequest(BaseModel):
    related_incident_id: uuid.UUID
    relationship_type: str = "related"  # "parent", "child", "duplicate", "related"
    note: str | None = None


class RelatedIncidentResponse(BaseModel):
    incident_id: uuid.UUID
    related_incident_id: uuid.UUID
    relationship_type: str
    note: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    # Related incident details
    related_incident: RelatedIncidentItem


@router.get("/{incident_id:uuid}/related", response_model=list[RelatedIncidentResponse])
async def list_related_incidents(
    incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> list[RelatedIncidentResponse]:
    """List all incidents explicitly linked to this incident."""
    result = await session.execute(
        select(RelatedIncident, Incident)
        .join(
            Incident,
            (RelatedIncident.tenant_id == Incident.tenant_id)
            & (RelatedIncident.related_incident_id == Incident.id),
        )
        .where(
            RelatedIncident.tenant_id == tenant_id,
            RelatedIncident.incident_id == incident_id,
        )
    )
    rows = result.all()

    return [
        RelatedIncidentResponse(
            incident_id=rel.incident_id,
            related_incident_id=rel.related_incident_id,
            relationship_type=rel.relationship_type,
            note=rel.note,
            created_by=rel.created_by,
            created_at=rel.created_at,
            related_incident=RelatedIncidentItem(
                id=inc.id,
                alert_type=inc.alert_type,
                state=inc.state,
                severity=inc.severity,
                title=inc.title,
                created_at=inc.created_at,
            ),
        )
        for rel, inc in rows
    ]


@router.post(
    "/{incident_id:uuid}/related",
    status_code=status.HTTP_201_CREATED,
    response_model=RelatedIncidentResponse,
)
async def link_incident(
    incident_id: uuid.UUID,
    body: LinkIncidentRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> RelatedIncidentResponse:
    """Link an incident to another incident."""
    if incident_id == body.related_incident_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot link an incident to itself",
        )

    # Verify both incidents exist
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id.in_([incident_id, body.related_incident_id]),
            Incident.deleted_at.is_(None),
        )
    )
    incidents = {inc.id: inc for inc in result.scalars().all()}

    if incident_id not in incidents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )
    if body.related_incident_id not in incidents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Related incident not found",
        )

    # Check if link already exists
    existing = await session.execute(
        select(RelatedIncident).where(
            RelatedIncident.tenant_id == tenant_id,
            RelatedIncident.incident_id == incident_id,
            RelatedIncident.related_incident_id == body.related_incident_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Incidents are already linked",
        )

    # Create the link (bidirectional)
    rel1 = RelatedIncident(
        tenant_id=tenant_id,
        incident_id=incident_id,
        related_incident_id=body.related_incident_id,
        relationship_type=body.relationship_type,
        note=body.note,
        created_by=current_user.user_id if current_user else None,
    )
    rel2 = RelatedIncident(
        tenant_id=tenant_id,
        incident_id=body.related_incident_id,
        related_incident_id=incident_id,
        relationship_type="parent"
        if body.relationship_type == "child"
        else (
            "child" if body.relationship_type == "parent" else body.relationship_type
        ),
        note=body.note,
        created_by=current_user.user_id if current_user else None,
    )
    session.add(rel1)
    session.add(rel2)
    await session.commit()

    related_inc = incidents[body.related_incident_id]
    return RelatedIncidentResponse(
        incident_id=rel1.incident_id,
        related_incident_id=rel1.related_incident_id,
        relationship_type=rel1.relationship_type,
        note=rel1.note,
        created_by=rel1.created_by,
        created_at=rel1.created_at,
        related_incident=RelatedIncidentItem(
            id=related_inc.id,
            alert_type=related_inc.alert_type,
            state=related_inc.state,
            severity=related_inc.severity,
            title=related_inc.title,
            created_at=related_inc.created_at,
        ),
    )


@router.delete(
    "/{incident_id:uuid}/related/{related_incident_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_incident(
    incident_id: uuid.UUID,
    related_incident_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> None:
    """Unlink two incidents (removes bidirectional link)."""
    result = await session.execute(
        select(RelatedIncident).where(
            RelatedIncident.tenant_id == tenant_id,
            RelatedIncident.incident_id == incident_id,
            RelatedIncident.related_incident_id == related_incident_id,
        )
    )
    rel1 = result.scalar_one_or_none()
    if not rel1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incidents are not linked",
        )

    # Remove bidirectional link
    result2 = await session.execute(
        select(RelatedIncident).where(
            RelatedIncident.tenant_id == tenant_id,
            RelatedIncident.incident_id == related_incident_id,
            RelatedIncident.related_incident_id == incident_id,
        )
    )
    rel2 = result2.scalar_one_or_none()

    await session.delete(rel1)
    if rel2:
        await session.delete(rel2)
    await session.commit()

    logger.info(
        "incidents_unlinked",
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
        related_incident_id=str(related_incident_id),
        user_id=str(current_user.user_id) if current_user else None,
    )
