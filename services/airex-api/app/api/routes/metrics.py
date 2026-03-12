"""
Metrics API endpoints for dashboard statistics.

Provides aggregated metrics for the frontend dashboard.
"""

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import cast, Date, func, select

from app.api.dependencies import TenantId, TenantSession
from airex_core.models.enums import IncidentState
from airex_core.models.health_check import HealthCheck
from airex_core.models.incident import Incident
from airex_core.models.state_transition import StateTransition

logger = structlog.get_logger()

router = APIRouter()


class MetricsResponse(BaseModel):
    mttr_seconds: float | None  # Mean Time To Resolution
    avg_investigation_seconds: float | None
    ai_confidence_avg: float | None
    auto_resolved_count: int
    total_resolved_24h: int
    active_incidents: int
    critical_incidents: int
    acknowledged_count: int
    pending_ack_count: int


@router.get("/", response_model=MetricsResponse)
async def get_metrics(
    tenant_id: TenantId,
    session: TenantSession,
) -> MetricsResponse:
    """
    Get aggregated metrics for the dashboard.

    Calculates:
    - MTTR (Mean Time To Resolution) for resolved incidents
    - Average investigation duration
    - AI confidence average
    - Auto-resolved count (resolved without manual intervention)
    - Total resolved in last 24 hours
    - Active and critical incident counts
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)

    # Active incidents
    active_result = await session.execute(
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state.in_(
                [
                    IncidentState.RECEIVED,
                    IncidentState.INVESTIGATING,
                    IncidentState.RECOMMENDATION_READY,
                    IncidentState.AWAITING_APPROVAL,
                    IncidentState.EXECUTING,
                    IncidentState.VERIFYING,
                ]
            ),
        )
    )
    active_incidents = active_result.scalar_one() or 0

    # Critical incidents
    critical_result = await session.execute(
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state.in_(
                [
                    IncidentState.RECEIVED,
                    IncidentState.INVESTIGATING,
                    IncidentState.RECOMMENDATION_READY,
                    IncidentState.AWAITING_APPROVAL,
                    IncidentState.EXECUTING,
                    IncidentState.VERIFYING,
                ]
            ),
            Incident.severity == "CRITICAL",
        )
    )
    critical_incidents = critical_result.scalar_one() or 0

    # Resolved in last 24h
    resolved_24h_result = await session.execute(
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state == IncidentState.RESOLVED,
            Incident.updated_at >= day_ago,
        )
    )
    total_resolved_24h = resolved_24h_result.scalar_one() or 0

    # MTTR: Average time from RECEIVED to RESOLVED
    mttr_result = await session.execute(
        select(
            func.avg(func.extract("epoch", Incident.updated_at - Incident.created_at))
        )
        .select_from(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state == IncidentState.RESOLVED,
            Incident.updated_at >= day_ago,
        )
    )
    mttr_seconds = mttr_result.scalar_one()

    # Auto-resolved: resolved without manual review flags
    resolved_result = await session.execute(
        select(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state == IncidentState.RESOLVED,
            Incident.updated_at >= day_ago,
        )
        .limit(100)  # Sample for performance
    )
    resolved_incidents = resolved_result.scalars().all()
    auto_resolved_count = sum(
        1
        for inc in resolved_incidents
        if not (inc.meta and inc.meta.get("_manual_review_required"))
    )

    # Average investigation duration: time from RECEIVED to RECOMMENDATION_READY
    investigation_durations = []
    for inc in resolved_incidents[:50]:  # Sample for performance
        trans_result = await session.execute(
            select(StateTransition)
            .where(
                StateTransition.tenant_id == tenant_id,
                StateTransition.incident_id == inc.id,
                StateTransition.from_state == IncidentState.RECEIVED,
                StateTransition.to_state == IncidentState.RECOMMENDATION_READY,
            )
            .order_by(StateTransition.created_at)
            .limit(1)
        )
        trans = trans_result.scalar_one_or_none()
        if trans:
            duration = (trans.created_at - inc.created_at).total_seconds()
            if duration > 0:
                investigation_durations.append(duration)

    avg_investigation_seconds = (
        sum(investigation_durations) / len(investigation_durations)
        if investigation_durations
        else None
    )

    # AI confidence average (from recommendations in meta)
    confidences = []
    for inc in resolved_incidents[:50]:
        if inc.meta and "recommendation" in inc.meta:
            rec = inc.meta["recommendation"]
            if isinstance(rec, dict) and "confidence" in rec:
                conf = rec["confidence"]
                if isinstance(conf, (int, float)) and 0 <= conf <= 1:
                    confidences.append(conf)

    ai_confidence_avg = sum(confidences) / len(confidences) if confidences else None

    # Acknowledged active incidents (meta has acknowledged_by key)
    active_states = [
        IncidentState.RECEIVED,
        IncidentState.INVESTIGATING,
        IncidentState.RECOMMENDATION_READY,
        IncidentState.AWAITING_APPROVAL,
        IncidentState.EXECUTING,
        IncidentState.VERIFYING,
    ]
    ack_result = await session.execute(
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state.in_(active_states),
            Incident.meta.has_key("acknowledged_by"),
        )
    )
    acknowledged_count = ack_result.scalar_one() or 0
    pending_ack_count = max(0, active_incidents - acknowledged_count)

    return MetricsResponse(
        mttr_seconds=float(mttr_seconds) if mttr_seconds else None,
        avg_investigation_seconds=avg_investigation_seconds,
        ai_confidence_avg=ai_confidence_avg,
        auto_resolved_count=auto_resolved_count,
        total_resolved_24h=total_resolved_24h,
        active_incidents=active_incidents,
        critical_incidents=critical_incidents,
        acknowledged_count=acknowledged_count,
        pending_ack_count=pending_ack_count,
    )


class AlertHistoryDay(BaseModel):
    date: str  # ISO date string "YYYY-MM-DD"
    alerts: int


class AlertHistoryResponse(BaseModel):
    days: int
    series: list[AlertHistoryDay]
    total_alerts: int
    most_affected_monitor: str | None = None


@router.get("/alert-history", response_model=AlertHistoryResponse)
async def get_alert_history(
    tenant_id: TenantId,
    session: TenantSession,
    days: int = Query(default=7, ge=1, le=90),
) -> AlertHistoryResponse:
    """
    Get daily alert counts (degraded + down) from health_checks for the last N days.

    Used by the AlertHistoryWidget on the dashboard.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Daily alert counts
    day_col = cast(HealthCheck.checked_at, Date).label("day")
    rows = await session.execute(
        select(day_col, func.count().label("alert_count"))
        .where(
            HealthCheck.tenant_id == tenant_id,
            HealthCheck.checked_at >= cutoff,
            HealthCheck.status.in_(["degraded", "down"]),
        )
        .group_by(day_col)
        .order_by(day_col)
    )
    daily: dict[str, int] = {str(r.day): r.alert_count for r in rows}

    # Fill in zeros for days with no alerts
    series: list[AlertHistoryDay] = []
    for i in range(days):
        d = (cutoff + timedelta(days=i + 1)).date()
        series.append(AlertHistoryDay(date=str(d), alerts=daily.get(str(d), 0)))

    total_alerts = sum(s.alerts for s in series)

    # Most affected monitor (highest alert count over the period)
    most_affected: str | None = None
    if total_alerts > 0:
        top_row = await session.execute(
            select(HealthCheck.target_name, func.count().label("cnt"))
            .where(
                HealthCheck.tenant_id == tenant_id,
                HealthCheck.checked_at >= cutoff,
                HealthCheck.status.in_(["degraded", "down"]),
            )
            .group_by(HealthCheck.target_name)
            .order_by(func.count().desc())
            .limit(1)
        )
        top = top_row.first()
        if top:
            most_affected = top.target_name

    return AlertHistoryResponse(
        days=days,
        series=series,
        total_alerts=total_alerts,
        most_affected_monitor=most_affected,
    )
