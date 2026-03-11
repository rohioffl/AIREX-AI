"""Health check API routes (Phase 6 ARE — Proactive Monitoring)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import TenantId, TenantSession, Redis, require_permission
from airex_core.models.enums import Permission
from airex_core.core.config import settings
from airex_core.schemas.health_check import (
    HealthCheckDashboard,
    HealthCheckListResponse,
    MonitorInventoryResponse,
    MonitorItem,
)
from airex_core.services.health_check_service import (
    get_dashboard,
    get_target_history,
    run_health_checks,
)

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=HealthCheckDashboard,
    dependencies=[Depends(require_permission(Permission.INCIDENT_VIEW))],
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
    dependencies=[Depends(require_permission(Permission.INCIDENT_VIEW))],
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
    dependencies=[Depends(require_permission(Permission.SYSTEM_METRICS))],
)
async def trigger_health_checks(
    tenant_id: TenantId,
    redis: Redis,
) -> dict[str, Any]:
    """Manually trigger a health check run (admin only)."""
    summary = await run_health_checks(tenant_id, redis=redis)
    return {"status": "completed", **summary}


_MONITOR_CACHE_TTL = 300  # 5 minutes


@router.get(
    "/monitors",
    response_model=MonitorInventoryResponse,
    dependencies=[Depends(require_permission(Permission.INCIDENT_VIEW))],
)
async def list_monitors(
    tenant_id: TenantId,
    session: TenantSession,
    redis: Redis,
    refresh: bool = Query(default=False),
) -> MonitorInventoryResponse:
    """List Site24x7 monitors with their latest health check status from DB."""
    import structlog
    from sqlalchemy import select
    from airex_core.models.health_check import HealthCheck

    log = structlog.get_logger().bind(tenant_id=str(tenant_id))

    if not settings.SITE24X7_ENABLED:
        return MonitorInventoryResponse(site24x7_enabled=False)

    cache_key = f"airex:s247:monitors:{tenant_id}"

    # Try cache unless refresh requested
    if not refresh and redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached if isinstance(cached, str) else cached.decode())
                return MonitorInventoryResponse(**data)
        except Exception as exc:
            log.warning("monitor_inventory_cache_read_failed", error=str(exc))

    # Fetch monitor list from Site24x7
    try:
        from airex_core.monitoring.site24x7_client import Site24x7Client
        client = Site24x7Client(redis=redis)
        raw_monitors = await client.list_monitors()
    except Exception as exc:
        log.warning("monitor_inventory_fetch_failed", error=str(exc))
        raw_monitors = []

    # Fetch latest HealthCheck per target_id from DB
    monitor_ids = [
        str(m.get("monitor_id", m.get("id", "")))
        for m in raw_monitors
        if m.get("monitor_id") or m.get("id")
    ]
    latest_checks: dict[str, HealthCheck | None] = {}
    if monitor_ids:
        from sqlalchemy import func
        subq = (
            select(
                HealthCheck.target_id,
                func.max(HealthCheck.checked_at).label("max_checked_at"),
            )
            .where(
                HealthCheck.tenant_id == tenant_id,
                HealthCheck.target_id.in_(monitor_ids),
            )
            .group_by(HealthCheck.target_id)
            .subquery()
        )
        rows = await session.execute(
            select(HealthCheck).join(
                subq,
                (HealthCheck.target_id == subq.c.target_id)
                & (HealthCheck.checked_at == subq.c.max_checked_at),
            )
        )
        for hc in rows.scalars().all():
            latest_checks[hc.target_id] = hc

    monitors = []
    for m in raw_monitors:
        mid = str(m.get("monitor_id") or m.get("id") or "")
        latest: HealthCheck | None = latest_checks.get(mid)
        monitors.append(
            MonitorItem(
                monitor_id=mid,
                monitor_name=m.get("display_name") or m.get("name") or mid,
                monitor_type=str(m.get("type_name") or m.get("type") or ""),
                current_status=latest.status if latest else "unknown",
                last_checked_at=latest.checked_at if latest else None,
                last_incident_id=latest.incident_id if latest else None,
            )
        )

    now = datetime.now(timezone.utc)
    response = MonitorInventoryResponse(
        monitors=monitors,
        total=len(monitors),
        last_synced_at=now,
        site24x7_enabled=True,
    )

    # Cache result
    if redis is not None:
        try:
            await redis.set(
                cache_key,
                json.dumps(response.model_dump(mode="json")),
                ex=_MONITOR_CACHE_TTL,
            )
        except Exception as exc:
            log.warning("monitor_inventory_cache_write_failed", error=str(exc))

    return response
