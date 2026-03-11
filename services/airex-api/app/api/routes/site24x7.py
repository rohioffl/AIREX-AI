"""
Site24x7 API endpoints for monitor data access.

Provides endpoints to fetch performance, outages, and summary data
from Site24x7 API for use in frontend and investigation plugins.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import Redis, TenantId
from airex_core.core.config import settings
from airex_core.monitoring.site24x7_client import Site24x7Client

logger = structlog.get_logger()

router = APIRouter()


@router.get("/monitors/{monitor_id}/performance")
async def get_monitor_performance(
    monitor_id: str,
    period: int = Query(default=1, ge=1, le=3, description="1=24h, 2=7d, 3=30d"),
    tenant_id: TenantId = None,
    redis: Redis = None,
) -> dict:
    """Get performance metrics for a monitor."""
    if not settings.SITE24X7_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Site24x7 integration is not enabled",
        )

    try:
        client = Site24x7Client(redis=redis)
        perf_data = await client.get_performance_report(monitor_id, period=period)
        return perf_data
    except Exception as exc:
        logger.error("site24x7_performance_fetch_failed", monitor_id=monitor_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch performance data: {str(exc)}",
        ) from exc


@router.get("/monitors/{monitor_id}/outages")
async def get_monitor_outages(
    monitor_id: str,
    period: int = Query(default=3, ge=1, le=3, description="1=24h, 2=7d, 3=30d"),
    tenant_id: TenantId = None,
    redis: Redis = None,
) -> dict:
    """Get outage history for a monitor."""
    if not settings.SITE24X7_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Site24x7 integration is not enabled",
        )

    try:
        client = Site24x7Client(redis=redis)
        outages = await client.get_outage_report(monitor_id, period=period)
        return outages
    except Exception as exc:
        logger.error("site24x7_outages_fetch_failed", monitor_id=monitor_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch outage data: {str(exc)}",
        ) from exc


@router.get("/monitors/{monitor_id}/summary")
async def get_monitor_summary(
    monitor_id: str,
    tenant_id: TenantId = None,
    redis: Redis = None,
) -> dict:
    """Get combined summary: monitor details + current status + performance."""
    if not settings.SITE24X7_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Site24x7 integration is not enabled",
        )

    try:
        client = Site24x7Client(redis=redis)
        summary = await client.get_summary(monitor_id)
        return summary
    except Exception as exc:
        logger.error("site24x7_summary_fetch_failed", monitor_id=monitor_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch summary: {str(exc)}",
        ) from exc
