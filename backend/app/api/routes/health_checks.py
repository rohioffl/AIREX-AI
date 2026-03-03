"""Health check API routes (Phase 6 ARE — Proactive Monitoring)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import TenantId, TenantSession, Redis
from app.api.dependencies import require_role
from app.schemas.health_check import (
    HealthCheckDashboard,
    HealthCheckListResponse,
)
from app.services.health_check_service import (
    get_dashboard,
    get_target_history,
    run_health_checks,
)

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=HealthCheckDashboard,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
async def health_check_dashboard(
    tenant_id: TenantId,
    session: TenantSession,
) -> HealthCheckDashboard:
    """Get the health check dashboard: summary + per-target status + recent checks."""
    return await get_dashboard(session, tenant_id)


@router.get(
    "/targets/{target_type}/{target_id}/history",
    response_model=HealthCheckListResponse,
    dependencies=[Depends(require_role("viewer", "operator", "admin"))],
)
async def target_check_history(
    target_type: str,
    target_id: str,
    tenant_id: TenantId,
    session: TenantSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> HealthCheckListResponse:
    """Get health check history for a specific target."""
    return await get_target_history(session, tenant_id, target_type, target_id, limit)


@router.post(
    "/run",
    response_model=dict,
    dependencies=[Depends(require_role("admin"))],
)
async def trigger_health_checks(
    tenant_id: TenantId,
    redis: Redis,
) -> dict:
    """Manually trigger a health check run (admin only)."""
    summary = await run_health_checks(tenant_id, redis=redis)
    return {"status": "completed", **summary}
