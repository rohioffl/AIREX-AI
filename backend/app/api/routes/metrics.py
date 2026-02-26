"""
Metrics API endpoints for dashboard statistics.

Provides aggregated metrics for the frontend dashboard.
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import TenantId, TenantSession
from app.models.enums import IncidentState
from app.models.incident import Incident
from app.models.state_transition import StateTransition

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
    active_incidents = active_result.scalar_one() or 0
    
    # Critical incidents
    critical_result = await session.execute(
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
            Incident.severity == "CRITICAL",
        )
    )
    critical_incidents = critical_result.scalar_one() or 0
    
    # Resolved in last 24h
    resolved_24h_result = await session.execute(
        select(func.count()).select_from(Incident).where(
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
            func.avg(
                func.extract('epoch', Incident.updated_at - Incident.created_at)
            )
        ).select_from(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state == IncidentState.RESOLVED,
            Incident.updated_at >= day_ago,
        )
    )
    mttr_seconds = mttr_result.scalar_one()
    
    # Auto-resolved: resolved without manual review flags
    resolved_result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state == IncidentState.RESOLVED,
            Incident.updated_at >= day_ago,
        ).limit(100)  # Sample for performance
    )
    resolved_incidents = resolved_result.scalars().all()
    auto_resolved_count = sum(
        1 for inc in resolved_incidents
        if not (inc.meta and inc.meta.get("_manual_review_required"))
    )
    
    # Average investigation duration: time from RECEIVED to RECOMMENDATION_READY
    investigation_durations = []
    for inc in resolved_incidents[:50]:  # Sample for performance
        trans_result = await session.execute(
            select(StateTransition).where(
                StateTransition.tenant_id == tenant_id,
                StateTransition.incident_id == inc.id,
                StateTransition.from_state == IncidentState.RECEIVED,
                StateTransition.to_state == IncidentState.RECOMMENDATION_READY,
            ).order_by(StateTransition.created_at).limit(1)
        )
        trans = trans_result.scalar_one_or_none()
        if trans:
            duration = (trans.created_at - inc.created_at).total_seconds()
            if duration > 0:
                investigation_durations.append(duration)
    
    avg_investigation_seconds = (
        sum(investigation_durations) / len(investigation_durations)
        if investigation_durations else None
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
    
    ai_confidence_avg = (
        sum(confidences) / len(confidences)
        if confidences else None
    )
    
    return MetricsResponse(
        mttr_seconds=float(mttr_seconds) if mttr_seconds else None,
        avg_investigation_seconds=avg_investigation_seconds,
        ai_confidence_avg=ai_confidence_avg,
        auto_resolved_count=auto_resolved_count,
        total_resolved_24h=total_resolved_24h,
        active_incidents=active_incidents,
        critical_incidents=critical_incidents,
    )
