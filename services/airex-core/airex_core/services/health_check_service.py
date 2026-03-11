"""
Proactive health check service (Phase 6 ARE — Proactive Monitoring).

Polls known infrastructure (Site24x7 monitors) on a schedule,
evaluates thresholds, and auto-creates incidents when degradation
is detected. All I/O is async.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import structlog
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.config import settings
from airex_core.models.health_check import HealthCheck, HealthCheckStatus, TargetType
from airex_core.models.enums import SeverityLevel
from airex_core.schemas.health_check import (
    HealthCheckDashboard,
    HealthCheckListResponse,
    HealthCheckResponse,
    HealthCheckSummary,
    TargetStatus,
)

logger = structlog.get_logger()

# ── Threshold definitions ────────────────────────────────────────
# Each threshold maps a metric key to (warning_threshold, critical_threshold).
# Exceeding warning → DEGRADED; exceeding critical → DOWN + incident.

THRESHOLDS: dict[str, tuple[float, float]] = {
    "response_time_ms": (2000.0, 5000.0),
    "cpu_percent": (85.0, 95.0),
    "memory_percent": (85.0, 95.0),
    "disk_percent": (80.0, 90.0),
    "availability_percent": (99.0, 95.0),  # inverted: below threshold = bad
    "error_rate_percent": (5.0, 15.0),
}

# Site24x7 status code mapping
SITE24X7_STATUS_MAP: dict[int, str] = {
    0: HealthCheckStatus.DOWN,  # Down
    1: HealthCheckStatus.HEALTHY,  # Up
    2: HealthCheckStatus.DEGRADED,  # Trouble
    3: HealthCheckStatus.DEGRADED,  # Critical (site24x7 critical = our degraded)
    5: HealthCheckStatus.UNKNOWN,  # Suspended
    7: HealthCheckStatus.UNKNOWN,  # Maintenance
    9: HealthCheckStatus.DOWN,  # Configuration Error
    10: HealthCheckStatus.UNKNOWN,  # Discovery
}

# Alert type mapping for auto-created incidents
STATUS_TO_ALERT_TYPE: dict[str, str] = {
    HealthCheckStatus.DOWN: "healthcheck",
    HealthCheckStatus.DEGRADED: "healthcheck",
}

STATUS_TO_SEVERITY: dict[str, SeverityLevel] = {
    HealthCheckStatus.DOWN: SeverityLevel.CRITICAL,
    HealthCheckStatus.DEGRADED: SeverityLevel.MEDIUM,
}


def evaluate_thresholds(metrics: dict[str, Any]) -> tuple[str, list[dict]]:
    """Evaluate metrics against thresholds.

    Returns (status, anomalies_list).
    """
    anomalies: list[dict[str, Any]] = []
    worst_status = HealthCheckStatus.HEALTHY

    for metric_key, value in metrics.items():
        if metric_key not in THRESHOLDS or not isinstance(value, (int, float)):
            continue

        warn_thresh, crit_thresh = THRESHOLDS[metric_key]
        is_inverted = metric_key == "availability_percent"

        if is_inverted:
            # Lower is worse for availability
            if value < crit_thresh:
                anomalies.append(
                    {
                        "metric": metric_key,
                        "value": value,
                        "threshold": crit_thresh,
                        "severity": "critical",
                        "description": f"{metric_key} at {value}% (critical threshold: {crit_thresh}%)",
                    }
                )
                worst_status = HealthCheckStatus.DOWN
            elif value < warn_thresh:
                anomalies.append(
                    {
                        "metric": metric_key,
                        "value": value,
                        "threshold": warn_thresh,
                        "severity": "warning",
                        "description": f"{metric_key} at {value}% (warning threshold: {warn_thresh}%)",
                    }
                )
                if worst_status != HealthCheckStatus.DOWN:
                    worst_status = HealthCheckStatus.DEGRADED
        else:
            # Higher is worse for response time, CPU, memory, disk, error rate
            if value >= crit_thresh:
                anomalies.append(
                    {
                        "metric": metric_key,
                        "value": value,
                        "threshold": crit_thresh,
                        "severity": "critical",
                        "description": f"{metric_key} at {value} (critical threshold: {crit_thresh})",
                    }
                )
                worst_status = HealthCheckStatus.DOWN
            elif value >= warn_thresh:
                anomalies.append(
                    {
                        "metric": metric_key,
                        "value": value,
                        "threshold": warn_thresh,
                        "severity": "warning",
                        "description": f"{metric_key} at {value} (warning threshold: {warn_thresh})",
                    }
                )
                if worst_status != HealthCheckStatus.DOWN:
                    worst_status = HealthCheckStatus.DEGRADED

    return worst_status, anomalies


async def check_site24x7_monitors(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    redis: Any | None = None,
) -> list[HealthCheck]:
    """Poll all Site24x7 monitors and store health check results.

    Returns list of HealthCheck records created.
    """
    from airex_core.monitoring.site24x7_client import Site24x7Client

    if not settings.SITE24X7_ENABLED or not settings.SITE24X7_REFRESH_TOKEN:
        logger.info("health_check_site24x7_disabled")
        return []

    client = Site24x7Client(redis=redis)
    results: list[HealthCheck] = []
    log = logger.bind(tenant_id=str(tenant_id), target_type=TargetType.SITE24X7)

    try:
        # Fetch current status of all monitors in one call
        all_status = await client._get(
            "/current_status", params={"apm_required": "true"}
        )
        monitors_data = all_status.get("data", {})

        # Site24x7 returns monitors grouped by type
        monitor_groups = monitors_data.get("monitors", [])
        if not monitor_groups and isinstance(monitors_data, list):
            monitor_groups = monitors_data

        flat_monitors: list[dict] = []
        if isinstance(monitor_groups, list):
            for item in monitor_groups:
                if isinstance(item, dict) and "monitors" in item:
                    flat_monitors.extend(item["monitors"])
                elif isinstance(item, dict) and "monitor_id" in item:
                    flat_monitors.append(item)

        log.info("health_check_site24x7_fetched", monitor_count=len(flat_monitors))

        for monitor in flat_monitors[: settings.HEALTH_CHECK_MAX_MONITORS]:
            start_ms = time.monotonic() * 1000
            monitor_id = monitor.get("monitor_id", monitor.get("monitorid", ""))
            monitor_name = monitor.get(
                "name", monitor.get("display_name", f"monitor-{monitor_id}")
            )

            try:
                # Extract metrics from status data
                raw_status = monitor.get("status", 10)  # default to Discovery/unknown
                attribute_value = monitor.get("attribute_value", "")

                metrics: dict[str, Any] = {
                    "site24x7_status_code": raw_status,
                    "attribute_value": attribute_value,
                }

                # Parse response time if present
                if "attribute_value" in monitor:
                    try:
                        resp_time = float(
                            str(attribute_value).replace(" ms", "").strip()
                        )
                        metrics["response_time_ms"] = resp_time
                    except (ValueError, TypeError):
                        pass

                # Map Site24x7 status code to our status
                mapped_status = SITE24X7_STATUS_MAP.get(
                    int(raw_status), HealthCheckStatus.UNKNOWN
                )

                # Apply threshold evaluation on top of status mapping
                threshold_status, anomalies = evaluate_thresholds(metrics)

                # Use the worse of mapped status and threshold status
                final_status = _worst_status(mapped_status, threshold_status)

                duration_ms = time.monotonic() * 1000 - start_ms

                hc = HealthCheck(
                    tenant_id=tenant_id,
                    id=uuid.uuid4(),
                    target_type=TargetType.SITE24X7,
                    target_id=str(monitor_id),
                    target_name=str(monitor_name),
                    status=final_status,
                    metrics=metrics,
                    anomalies=anomalies if anomalies else None,
                    checked_at=datetime.now(timezone.utc),
                    duration_ms=round(duration_ms, 2),
                )
                session.add(hc)
                results.append(hc)

            except (TypeError, ValueError, KeyError) as exc:
                duration_ms = time.monotonic() * 1000 - start_ms
                log.warning(
                    "health_check_monitor_failed",
                    monitor_id=monitor_id,
                    error=str(exc),
                )
                hc = HealthCheck(
                    tenant_id=tenant_id,
                    id=uuid.uuid4(),
                    target_type=TargetType.SITE24X7,
                    target_id=str(monitor_id),
                    target_name=str(monitor_name),
                    status=HealthCheckStatus.ERROR,
                    checked_at=datetime.now(timezone.utc),
                    duration_ms=round(duration_ms, 2),
                    error=str(exc)[:500],
                )
                session.add(hc)
                results.append(hc)

        await session.flush()
        log.info("health_check_site24x7_complete", results=len(results))

    except Exception as exc:
        log.error("health_check_site24x7_bulk_failed", error=str(exc))

    return results


def _worst_status(a: str, b: str) -> str:
    """Return the worse of two health check statuses."""
    order = {
        HealthCheckStatus.HEALTHY: 0,
        HealthCheckStatus.UNKNOWN: 1,
        HealthCheckStatus.DEGRADED: 2,
        HealthCheckStatus.ERROR: 3,
        HealthCheckStatus.DOWN: 4,
    }
    return a if order.get(a, 0) >= order.get(b, 0) else b


async def auto_create_incidents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    checks: list[HealthCheck],
    redis: Any | None = None,
) -> int:
    """Create incidents for health checks that detected degradation.

    Only creates an incident if:
    1. Status is DOWN or DEGRADED
    2. No recent incident already exists for this target (cooldown period)

    Returns count of incidents created.
    """
    from airex_core.services.incident_service import create_incident

    created_count = 0
    cooldown = timedelta(minutes=settings.HEALTH_CHECK_INCIDENT_COOLDOWN_MINUTES)
    now = datetime.now(timezone.utc)

    for hc in checks:
        if hc.status not in (HealthCheckStatus.DOWN, HealthCheckStatus.DEGRADED):
            continue

        # Check if there is an ACTIVE incident for this exact target
        from airex_core.models.incident import Incident
        from airex_core.models.enums import IncidentState

        active_incident_stmt = (
            select(Incident)
            .where(
                and_(
                    Incident.tenant_id == tenant_id,
                    Incident.alert_type
                    == STATUS_TO_ALERT_TYPE.get(hc.status, "healthcheck"),
                    Incident.meta["target_id"].astext == str(hc.target_id),
                    Incident.state.notin_(
                        [
                            IncidentState.RESOLVED,
                            IncidentState.FAILED_ANALYSIS,
                            IncidentState.FAILED_EXECUTION,
                            IncidentState.FAILED_VERIFICATION,
                        ]
                    ),
                    Incident.deleted_at.is_(None),
                )
            )
            .order_by(Incident.created_at.desc())
            .limit(1)
        )
        result = await session.execute(active_incident_stmt)
        active_incident = result.scalar_one_or_none()

        if active_incident:
            from sqlalchemy.orm.attributes import flag_modified

            # Enrich existing incident with latest check info
            m = dict(active_incident.meta) if active_incident.meta else {}
            m["_alert_last_seen_at"] = now.isoformat()
            m["_alert_count"] = int(m.get("_alert_count", 1)) + 1
            m["health_check_status"] = hc.status
            m["health_check_metrics"] = hc.metrics
            if hc.anomalies:
                m["health_check_anomalies"] = hc.anomalies

            active_incident.meta = m
            flag_modified(active_incident, "meta")
            session.add(active_incident)

            logger.debug(
                "health_check_incident_active_dedup",
                target_id=hc.target_id,
                incident_id=str(active_incident.id),
            )
            continue

        # Check cooldown: was an incident created for this target recently?
        cooldown_cutoff = now - cooldown
        recent_stmt = (
            select(func.count())
            .select_from(HealthCheck)
            .where(
                and_(
                    HealthCheck.tenant_id == tenant_id,
                    HealthCheck.target_type == hc.target_type,
                    HealthCheck.target_id == hc.target_id,
                    HealthCheck.incident_created.is_(True),
                    HealthCheck.checked_at >= cooldown_cutoff,
                )
            )
        )
        recent_count_result = await session.execute(recent_stmt)
        recent_count = cast(int, recent_count_result.scalar_one())

        if recent_count > 0:
            logger.debug(
                "health_check_incident_cooldown",
                target_id=hc.target_id,
                recent_count=recent_count,
            )
            continue

        # Create incident
        alert_type = STATUS_TO_ALERT_TYPE.get(hc.status, "healthcheck")
        severity = STATUS_TO_SEVERITY.get(hc.status, SeverityLevel.MEDIUM)
        anomaly_desc = ""
        if hc.anomalies:
            anomaly_desc = "; ".join(a.get("description", "") for a in hc.anomalies[:3])

        title = f"Proactive: {hc.target_name} is {hc.status}" + (
            f" — {anomaly_desc}" if anomaly_desc else ""
        )
        meta = {
            "_source": "proactive_health_check",
            "_health_check_id": str(hc.id),
            "target_type": hc.target_type,
            "target_id": hc.target_id,
            "target_name": hc.target_name,
            "health_check_status": hc.status,
            "health_check_metrics": hc.metrics,
            "health_check_anomalies": hc.anomalies,
        }

        # Add monitor_id for Site24x7 targets so the investigation probe can enrich
        if hc.target_type == TargetType.SITE24X7:
            meta["MONITORID"] = hc.target_id

        try:
            incident = await create_incident(
                session=session,
                tenant_id=tenant_id,
                alert_type=alert_type,
                severity=severity,
                title=title[:500],
                meta=meta,
            )
            hc.incident_created = True
            hc.incident_id = incident.id
            created_count += 1

            logger.info(
                "health_check_incident_created",
                correlation_id=str(incident.id),
                incident_id=str(incident.id),
                target=hc.target_name,
                status=hc.status,
            )

            # Enqueue investigation task
            if redis is not None:
                from arq.connections import ArqRedis

                pool = ArqRedis(pool_or_conn=redis.connection_pool)
                await pool.enqueue_job(
                    "investigate_incident",
                    str(tenant_id),
                    str(incident.id),
                    _defer_by=2,
                )

        except Exception as exc:
            logger.error(
                "health_check_incident_creation_failed",
                target=hc.target_name,
                correlation_id=str(hc.id),
                error=str(exc),
            )

    await session.flush()

    return created_count


async def run_health_checks(
    tenant_id: uuid.UUID,
    redis: Any | None = None,
) -> dict[str, int]:
    """Run all health check probes for a tenant.

    This is the main entry point called by the ARQ cron job.
    Returns summary counts.
    """
    from airex_core.core.database import get_tenant_session

    log = logger.bind(tenant_id=str(tenant_id), correlation_id=str(tenant_id))
    log.info("health_check_run_started")

    summary = {
        "checked": 0,
        "healthy": 0,
        "degraded": 0,
        "down": 0,
        "incidents_created": 0,
    }

    async with get_tenant_session(tenant_id) as session:
        # Phase 6 scope: Site24x7 monitors
        checks = await check_site24x7_monitors(session, tenant_id, redis=redis)
        summary["checked"] = len(checks)

        for hc in checks:
            if hc.status == HealthCheckStatus.HEALTHY:
                summary["healthy"] += 1
            elif hc.status == HealthCheckStatus.DEGRADED:
                summary["degraded"] += 1
            elif hc.status == HealthCheckStatus.DOWN:
                summary["down"] += 1

        # Auto-create incidents for degraded/down targets
        incidents_created = await auto_create_incidents(
            session, tenant_id, checks, redis=redis
        )
        summary["incidents_created"] = incidents_created

    log.info("health_check_run_complete", **summary)
    return summary


async def get_dashboard(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> HealthCheckDashboard:
    """Build the health check dashboard data.

    Returns summary stats, per-target latest status, and recent checks.
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    # Get latest check per target (using DISTINCT ON)
    latest_per_target_stmt = text("""
        SELECT DISTINCT ON (target_type, target_id)
            target_type, target_id, target_name, status,
            checked_at, anomalies, metrics, incident_id
        FROM health_checks
        WHERE tenant_id = :tid
        ORDER BY target_type, target_id, checked_at DESC
    """)
    result = await session.execute(latest_per_target_stmt, {"tid": str(tenant_id)})
    latest_rows = result.fetchall()

    # Build per-target status list
    targets: list[TargetStatus] = []
    status_counts = {"healthy": 0, "degraded": 0, "down": 0, "unknown": 0, "error": 0}

    for row in latest_rows:
        anomaly_list = row.anomalies if row.anomalies else []
        targets.append(
            TargetStatus(
                target_type=row.target_type,
                target_id=row.target_id,
                target_name=row.target_name,
                status=row.status,
                last_checked=row.checked_at,
                anomaly_count=len(anomaly_list),
                latest_metrics=row.metrics,
                incident_id=row.incident_id,
            )
        )
        bucket = row.status if row.status in status_counts else "unknown"
        status_counts[bucket] = status_counts.get(bucket, 0) + 1

    # Count incidents created in last 24h
    incident_count_stmt = (
        select(func.count())
        .select_from(HealthCheck)
        .where(
            and_(
                HealthCheck.tenant_id == tenant_id,
                HealthCheck.incident_created.is_(True),
                HealthCheck.checked_at >= cutoff_24h,
            )
        )
    )
    incident_result = await session.execute(incident_count_stmt)
    incidents_24h = incident_result.scalar_one()

    # Last run time
    last_run_stmt = select(func.max(HealthCheck.checked_at)).where(
        HealthCheck.tenant_id == tenant_id
    )
    last_run_result = await session.execute(last_run_stmt)
    last_run = last_run_result.scalar_one()

    # Recent checks (last 50)
    recent_stmt = (
        select(HealthCheck)
        .where(HealthCheck.tenant_id == tenant_id)
        .order_by(HealthCheck.checked_at.desc())
        .limit(50)
    )
    recent_result = await session.execute(recent_stmt)
    recent_checks = [
        HealthCheckResponse.model_validate(r) for r in recent_result.scalars().all()
    ]

    summary = HealthCheckSummary(
        total_targets=len(targets),
        healthy=status_counts["healthy"],
        degraded=status_counts["degraded"],
        down=status_counts["down"],
        unknown=status_counts["unknown"],
        error=status_counts["error"],
        last_run_at=last_run,
        incidents_created_24h=incidents_24h,
    )

    return HealthCheckDashboard(
        summary=summary,
        targets=sorted(
            targets,
            key=lambda t: (
                {"down": 0, "degraded": 1, "error": 2, "unknown": 3, "healthy": 4}.get(
                    t.status, 5
                ),
                t.target_name,
            ),
        ),
        recent_checks=recent_checks,
    )


async def get_target_history(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    target_type: str,
    target_id: str,
    limit: int = 100,
) -> HealthCheckListResponse:
    """Get health check history for a specific target."""
    stmt = (
        select(HealthCheck)
        .where(
            and_(
                HealthCheck.tenant_id == tenant_id,
                HealthCheck.target_type == target_type,
                HealthCheck.target_id == target_id,
            )
        )
        .order_by(HealthCheck.checked_at.desc())
        .limit(limit + 1)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    has_more = len(rows) > limit
    items = [HealthCheckResponse.model_validate(r) for r in rows[:limit]]

    count_stmt = (
        select(func.count())
        .select_from(HealthCheck)
        .where(
            and_(
                HealthCheck.tenant_id == tenant_id,
                HealthCheck.target_type == target_type,
                HealthCheck.target_id == target_id,
            )
        )
    )
    count_result = await session.execute(count_stmt)
    total = count_result.scalar_one()

    return HealthCheckListResponse(items=items, total=total, has_more=has_more)
