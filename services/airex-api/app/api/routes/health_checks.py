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
    Site24x7StatusSummary,
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

_SITE24X7_RAW_STATUS_LABELS: dict[int, str] = {
    0: "down",
    1: "up",
    2: "trouble",
    3: "critical",
    5: "suspended",
    7: "maintenance",
    9: "configuration_error",
    10: "discovery_in_progress",
}


def _map_site24x7_status(raw_status: int) -> str:
    if raw_status == 1:
        return "healthy"
    if raw_status in (2, 3):
        return "degraded"
    if raw_status in (0, 9):
        return "down"
    return "unknown"


def _extract_monitor_anomaly_flag(monitor: dict[str, Any]) -> int:
    for key in (
        "confirmed_anomaly",
        "confirmed_anomalies",
        "is_anomaly",
        "has_anomaly",
        "anomaly",
    ):
        value = monitor.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, (int, float)):
            return 1 if value > 0 else 0
        if isinstance(value, str):
            if value.strip().lower() in {"1", "true", "yes", "y"}:
                return 1
            if value.strip().lower() in {"0", "false", "no", "n"}:
                return 0
    return 0


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
                data = json.loads(
                    cached if isinstance(cached, str) else cached.decode()
                )
                return MonitorInventoryResponse(**data)
        except Exception as exc:
            log.warning("monitor_inventory_cache_read_failed", error=str(exc))

    from airex_core.monitoring.site24x7_client import Site24x7Client

    client = Site24x7Client(redis=redis)
    raw_monitors: list[dict[str, Any]] = []
    live_status_monitors: list[dict[str, Any]] = []

    # Inventory endpoint is the most reliable and should never be skipped.
    try:
        raw_monitors = await client.list_monitors()
    except Exception as exc:
        log.warning("monitor_inventory_fetch_failed", error=str(exc))

    # Live status endpoint may be unavailable for some Site24x7 tokens/plans.
    try:
        live_status_monitors = await client.get_all_current_status()
    except Exception as exc:
        log.warning("monitor_inventory_live_status_fetch_failed", error=str(exc))

    monitor_meta_by_id: dict[str, dict[str, Any]] = {}
    for monitor in raw_monitors:
        monitor_id = str(monitor.get("monitor_id") or monitor.get("id") or "")
        if monitor_id:
            monitor_meta_by_id[monitor_id] = monitor

    live_status_by_id: dict[str, dict[str, Any]] = {}
    for monitor in live_status_monitors:
        monitor_id = str(monitor.get("monitor_id") or monitor.get("monitorid") or "")
        if monitor_id and monitor_id not in live_status_by_id:
            live_status_by_id[monitor_id] = monitor

    for monitor_id in monitor_meta_by_id:
        live_status_by_id.setdefault(monitor_id, {})

    # Fetch latest HealthCheck per target_id from DB
    monitor_ids = [mid for mid in live_status_by_id.keys() if mid]
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

    summary_counts = {
        "down": 0,
        "critical": 0,
        "trouble": 0,
        "up": 0,
        "maintenance": 0,
        "discovery_in_progress": 0,
        "configuration_error": 0,
        "suspended": 0,
        "confirmed_anomalies": 0,
    }

    monitors = []
    for mid, live in live_status_by_id.items():
        meta = monitor_meta_by_id.get(mid, {})
        raw_status = live.get("status")
        if raw_status is None:
            raw_status = meta.get("status")
        if raw_status is None:
            state_value = meta.get("state")
            try:
                state_int = int(state_value) if state_value is not None else None
            except (TypeError, ValueError):
                state_int = None

            # In /monitors payload, state=0 indicates active/available.
            # Use UP as fallback when current_status did not include this monitor.
            if state_int == 0:
                raw_status = 1
            elif state_int in _SITE24X7_RAW_STATUS_LABELS:
                raw_status = state_int
        if raw_status is None:
            raw_status = 10
        try:
            raw_status_int = int(raw_status)
        except (TypeError, ValueError):
            raw_status_int = 10
        raw_status_label = _SITE24X7_RAW_STATUS_LABELS.get(raw_status_int, "unknown")
        if raw_status_label in summary_counts:
            summary_counts[raw_status_label] += 1
        summary_counts["confirmed_anomalies"] += _extract_monitor_anomaly_flag(live)

        latest: HealthCheck | None = latest_checks.get(mid)
        current_status = (
            latest.status if latest else _map_site24x7_status(raw_status_int)
        )
        monitors.append(
            MonitorItem(
                monitor_id=mid,
                monitor_name=(
                    live.get("display_name")
                    or live.get("name")
                    or meta.get("display_name")
                    or meta.get("name")
                    or mid
                ),
                monitor_type=str(
                    live.get("type_name")
                    or live.get("type")
                    or meta.get("type_name")
                    or meta.get("type")
                    or ""
                ),
                current_status=current_status,
                site24x7_status_code=raw_status_int,
                site24x7_status_label=raw_status_label,
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
        status_summary=Site24x7StatusSummary(
            total_monitors=len(monitors),
            down=summary_counts["down"],
            critical=summary_counts["critical"],
            trouble=summary_counts["trouble"],
            up=summary_counts["up"],
            maintenance=summary_counts["maintenance"],
            discovery_in_progress=summary_counts["discovery_in_progress"],
            configuration_error=summary_counts["configuration_error"],
            suspended=summary_counts["suspended"],
            confirmed_anomalies=summary_counts["confirmed_anomalies"],
        ),
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
