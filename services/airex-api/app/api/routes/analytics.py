"""
Analytics API endpoints for incident trends.

Note: LLM cost tracking is handled by Langfuse, not this API.
"""

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select, cast, Date, Float, Integer

from app.api.dependencies import TenantId, TenantSession, RequireAdmin
from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident

logger = structlog.get_logger()

router = APIRouter()


class MTTRTrendPoint(BaseModel):
    date: str  # ISO date "YYYY-MM-DD"
    mttr_seconds: float | None
    incident_count: int


class ResolutionRatePoint(BaseModel):
    alert_type: str
    total_incidents: int
    resolved_count: int
    resolution_rate: float  # 0.0-1.0


class AIConfidenceTrendPoint(BaseModel):
    date: str  # ISO date "YYYY-MM-DD"
    avg_confidence: float | None
    incident_count: int


class AnalyticsTrendsResponse(BaseModel):
    mttr_trends: list[MTTRTrendPoint]
    resolution_rates: list[ResolutionRatePoint]
    ai_confidence_trends: list[AIConfidenceTrendPoint]


@router.get("/trends", response_model=AnalyticsTrendsResponse)
async def get_analytics_trends(
    tenant_id: TenantId,
    session: TenantSession,
    _admin: RequireAdmin,
    days: int = Query(default=30, ge=1, le=90),
) -> AnalyticsTrendsResponse:
    """
    Get analytics trends: MTTR over time, resolution rates by alert type, AI confidence trends.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # MTTR trends (daily)
    mttr_trends: list[MTTRTrendPoint] = []
    date_col = cast(Incident.updated_at, Date).label("date")
    mttr_result = await session.execute(
        select(
            date_col,
            func.avg(
                func.extract("epoch", Incident.updated_at - Incident.created_at)
            ).label("avg_mttr"),
            func.count().label("incident_count"),
        )
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state == IncidentState.RESOLVED,
            Incident.updated_at >= cutoff,
        )
        .group_by(date_col)
        .order_by(date_col)
    )
    for row in mttr_result:
        mttr_trends.append(
            MTTRTrendPoint(
                date=str(row.date),
                mttr_seconds=float(row.avg_mttr) if row.avg_mttr else None,
                incident_count=int(row.incident_count or 0),
            )
        )

    # Resolution rates by alert type
    resolution_rates: list[ResolutionRatePoint] = []
    resolution_result = await session.execute(
        select(
            Incident.alert_type,
            func.count().label("total"),
            func.sum(
                cast(Incident.state == IncidentState.RESOLVED, Integer)
            ).label("resolved"),
        )
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.created_at >= cutoff,
        )
        .group_by(Incident.alert_type)
    )
    for row in resolution_result:
        total = int(row.total or 0)
        resolved = int(row.resolved or 0)
        resolution_rates.append(
            ResolutionRatePoint(
                alert_type=row.alert_type or "unknown",
                total_incidents=total,
                resolved_count=resolved,
                resolution_rate=resolved / total if total > 0 else 0.0,
            )
        )

    # AI confidence trends (daily)
    ai_confidence_trends: list[AIConfidenceTrendPoint] = []
    confidence_result = await session.execute(
        select(
            date_col,
            func.avg(
                cast(Incident.meta["recommendation"]["confidence"], Float)
            ).label("avg_confidence"),
            func.count().label("incident_count"),
        )
        .where(
            Incident.tenant_id == tenant_id,
            Incident.deleted_at.is_(None),
            Incident.state == IncidentState.RESOLVED,
            Incident.updated_at >= cutoff,
            Incident.meta.has_key("recommendation"),
        )
        .group_by(date_col)
        .order_by(date_col)
    )
    for row in confidence_result:
        ai_confidence_trends.append(
            AIConfidenceTrendPoint(
                date=str(row.date),
                avg_confidence=float(row.avg_confidence) if row.avg_confidence else None,
                incident_count=int(row.incident_count or 0),
            )
        )

    return AnalyticsTrendsResponse(
        mttr_trends=mttr_trends,
        resolution_rates=resolution_rates,
        ai_confidence_trends=ai_confidence_trends,
    )


