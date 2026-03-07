"""
ARQ async worker definitions.

All long-running tasks (investigate, recommend, execute, verify) run here.
Failed tasks after max retries go to DLQ via Redis list.
"""

import json
import importlib
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, cast

import redis.asyncio as aioredis
import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from app.core.events import set_redis
from app.core.logging import setup_logging
from app.core.metrics import dlq_size
from app.core.retry_scheduler import retry_failed_incidents

setup_logging(json_output=False)
logger = structlog.get_logger()

DLQ_KEY = "airex:dlq"


async def _send_to_dlq(
    redis: Any,
    task_name: str,
    tenant_id: str,
    incident_id: str,
    error: str | Exception,
    correlation_id: str | None = None,
) -> None:
    """Push a failed task onto the Dead Letter Queue."""
    entry = json.dumps(
        {
            "task": task_name,
            "tenant_id": tenant_id,
            "incident_id": incident_id,
            "error": str(error),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    await redis.rpush(DLQ_KEY, entry)
    queue_len = await redis.llen(DLQ_KEY)
    dlq_size.labels(tenant_id=tenant_id).set(queue_len)
    logger.error(
        "task_sent_to_dlq",
        task=task_name,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        incident_id=incident_id,
        error=str(error),
    )


def _build_task_logger(
    task_name: str,
    tenant_id: str | None = None,
    incident_id: str | None = None,
    action_type: str | None = None,
    correlation_id: str | None = None,
) -> structlog.typing.FilteringBoundLogger:
    payload: dict[str, str | None] = {
        "task": task_name,
        "tenant_id": tenant_id,
        "incident_id": incident_id,
        "correlation_id": correlation_id,
    }
    if action_type is not None:
        payload["action_type"] = action_type
    return logger.bind(**payload)


def _extract_correlation_id(ctx: Mapping[str, object]) -> str:
    job_id = str(ctx.get("job_id", "unknown"))
    return f"arq-{job_id}"


def _parse_task_ids(
    tenant_id: str,
    incident_id: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.UUID(tenant_id), uuid.UUID(incident_id)


def _get_redis_client(ctx: Mapping[str, object]) -> Any | None:
    redis = ctx.get("redis")
    if redis is not None and hasattr(redis, "rpush"):
        return redis
    return None


def _get_settings() -> Any:
    module = importlib.import_module("app.core.config")
    return cast(Any, module.settings)


def _load_attr(module_path: str, attr_name: str) -> Any:
    module = importlib.import_module(module_path)
    return getattr(module, attr_name)


async def investigate_incident(
    ctx: Mapping[str, object], tenant_id: str, incident_id: str
) -> None:
    """ARQ task: run investigation for an incident."""
    get_incident = _load_attr("app.services.incident_service", "get_incident")
    run_investigation = _load_attr(
        "app.services.investigation_service", "run_investigation"
    )
    get_tenant_session = _load_attr("app.core.database", "get_tenant_session")

    correlation_id = _extract_correlation_id(ctx)
    log = _build_task_logger(
        task_name="investigate",
        tenant_id=tenant_id,
        incident_id=incident_id,
        correlation_id=correlation_id,
    )
    log.info("task_started")

    try:
        tid, iid = _parse_task_ids(tenant_id, incident_id)
    except ValueError as exc:
        log.error("task_failed_invalid_uuid", error=str(exc))
        redis = _get_redis_client(ctx)
        if redis is not None:
            await _send_to_dlq(
                redis,
                "investigate_incident",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )
        return

    try:
        async with get_tenant_session(tid) as session:
            incident = await get_incident(session, tid, iid)
            if incident is None:
                log.error("incident_not_found")
                return
            await run_investigation(session, incident)
        log.info("task_completed")
    except Exception as exc:
        log.error("task_failed", error=str(exc))
        redis = _get_redis_client(ctx)
        if redis is not None:
            await _send_to_dlq(
                redis,
                "investigate_incident",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )


async def generate_recommendation_task(
    ctx: Mapping[str, object], tenant_id: str, incident_id: str
) -> None:
    """ARQ task: generate AI recommendation for an incident."""
    get_incident = _load_attr("app.services.incident_service", "get_incident")
    generate_recommendation = _load_attr(
        "app.services.recommendation_service", "generate_recommendation"
    )
    get_tenant_session = _load_attr("app.core.database", "get_tenant_session")

    correlation_id = _extract_correlation_id(ctx)
    log = _build_task_logger(
        task_name="recommend",
        tenant_id=tenant_id,
        incident_id=incident_id,
        correlation_id=correlation_id,
    )
    log.info("task_started")

    try:
        tid, iid = _parse_task_ids(tenant_id, incident_id)
    except ValueError as exc:
        log.error("task_failed_invalid_uuid", error=str(exc))
        redis = _get_redis_client(ctx)
        if redis is not None:
            await _send_to_dlq(
                redis,
                "generate_recommendation_task",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )
        return

    redis_client = _get_redis_client(ctx)

    try:
        async with get_tenant_session(tid) as session:
            incident = await get_incident(session, tid, iid)
            if incident is None:
                log.error("incident_not_found")
                return
            await generate_recommendation(session, incident, redis=redis_client)
        log.info("task_completed")
    except Exception as exc:
        log.error("task_failed", error=str(exc))
        if redis_client is not None:
            await _send_to_dlq(
                redis_client,
                "generate_recommendation_task",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )


async def execute_action_task(
    ctx: Mapping[str, object], tenant_id: str, incident_id: str, action_type: str
) -> None:
    """ARQ task: execute an approved action."""
    execute_action = _load_attr("app.services.execution_service", "execute_action")
    get_incident = _load_attr("app.services.incident_service", "get_incident")
    get_tenant_session = _load_attr("app.core.database", "get_tenant_session")

    correlation_id = _extract_correlation_id(ctx)
    log = _build_task_logger(
        task_name="execute",
        tenant_id=tenant_id,
        incident_id=incident_id,
        action_type=action_type,
        correlation_id=correlation_id,
    )
    log.info("task_started")

    try:
        tid, iid = _parse_task_ids(tenant_id, incident_id)
    except ValueError as exc:
        log.error("task_failed_invalid_uuid", error=str(exc))
        redis = _get_redis_client(ctx)
        if redis is not None:
            await _send_to_dlq(
                redis,
                "execute_action_task",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )
        return

    redis_client = _get_redis_client(ctx)
    if redis_client is None:
        redis_client = aioredis.from_url(_get_settings().REDIS_URL)

    try:
        async with get_tenant_session(tid) as session:
            incident = await get_incident(session, tid, iid)
            if incident is None:
                log.error("incident_not_found")
                return
            await execute_action(
                session,
                incident,
                action_type,
                redis_client,
                worker_id=correlation_id,
            )
        log.info("task_completed")
    except Exception as exc:
        log.error("task_failed", error=str(exc))
        if redis_client is not None:
            await _send_to_dlq(
                redis_client,
                "execute_action_task",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )


async def verify_resolution_task(
    ctx: Mapping[str, object], tenant_id: str, incident_id: str
) -> None:
    """ARQ task: verify that execution resolved the incident."""
    get_incident = _load_attr("app.services.incident_service", "get_incident")
    verify_resolution = _load_attr(
        "app.services.verification_service", "verify_resolution"
    )
    get_tenant_session = _load_attr("app.core.database", "get_tenant_session")

    correlation_id = _extract_correlation_id(ctx)
    log = _build_task_logger(
        task_name="verify",
        tenant_id=tenant_id,
        incident_id=incident_id,
        correlation_id=correlation_id,
    )
    log.info("task_started")

    try:
        tid, iid = _parse_task_ids(tenant_id, incident_id)
    except ValueError as exc:
        log.error("task_failed_invalid_uuid", error=str(exc))
        redis = _get_redis_client(ctx)
        if redis is not None:
            await _send_to_dlq(
                redis,
                "verify_resolution_task",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )
        return

    try:
        async with get_tenant_session(tid) as session:
            incident = await get_incident(session, tid, iid)
            if incident is None:
                log.error("incident_not_found")
                return
            await verify_resolution(session, incident)
        log.info("task_completed")
    except Exception as exc:
        log.error("task_failed", error=str(exc))
        redis = _get_redis_client(ctx)
        if redis is not None:
            await _send_to_dlq(
                redis,
                "verify_resolution_task",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )


async def generate_runbook_task(
    ctx: Mapping[str, object], tenant_id: str, incident_id: str
) -> None:
    """ARQ task: auto-generate a runbook from a resolved incident (Phase 5 ARE)."""
    get_incident = _load_attr("app.services.incident_service", "get_incident")
    generate_and_store_runbook = _load_attr(
        "app.services.runbook_generator", "generate_and_store_runbook"
    )
    get_tenant_session = _load_attr("app.core.database", "get_tenant_session")

    correlation_id = _extract_correlation_id(ctx)
    log = _build_task_logger(
        task_name="generate_runbook",
        tenant_id=tenant_id,
        incident_id=incident_id,
        correlation_id=correlation_id,
    )
    log.info("task_started")

    try:
        tid, iid = _parse_task_ids(tenant_id, incident_id)
    except ValueError as exc:
        log.error("task_failed_invalid_uuid", error=str(exc))
        redis = _get_redis_client(ctx)
        if redis is not None:
            await _send_to_dlq(
                redis,
                "generate_runbook_task",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )
        return

    redis_client = _get_redis_client(ctx)

    try:
        async with get_tenant_session(tid) as session:
            incident = await get_incident(session, tid, iid)
            if incident is None:
                log.error("incident_not_found")
                return
            source_id = await generate_and_store_runbook(
                session, incident, redis=redis_client
            )
            if source_id:
                log.info("runbook_generated", source_id=str(source_id))
            else:
                log.info("runbook_generation_skipped")
        log.info("task_completed")
    except Exception as exc:
        log.error("task_failed", error=str(exc))
        if redis_client is not None:
            await _send_to_dlq(
                redis_client,
                "generate_runbook_task",
                tenant_id,
                incident_id,
                exc,
                correlation_id=correlation_id,
            )


async def proactive_health_check(ctx: Mapping[str, object]) -> None:
    """ARQ cron: run proactive health checks against known infrastructure (Phase 6 ARE).

    Polls Site24x7 monitors, evaluates thresholds, and auto-creates
    incidents when degradation is detected.
    """
    run_health_checks = _load_attr(
        "app.services.health_check_service", "run_health_checks"
    )

    settings = _get_settings()

    if not settings.HEALTH_CHECK_ENABLED:
        return

    correlation_id = _extract_correlation_id(ctx)
    log = _build_task_logger(
        task_name="proactive_health_check", correlation_id=correlation_id
    )
    log.info("cron_started")

    redis = ctx.get("redis")
    tenant_id = uuid.UUID(settings.DEV_TENANT_ID)

    try:
        summary = await run_health_checks(tenant_id, redis=redis)
        log.info("cron_completed", **summary)
    except Exception as exc:
        log.error("cron_failed", error=str(exc))


async def on_startup(ctx: dict) -> None:
    """ARQ worker startup hook — init Redis for SSE events."""
    redis = aioredis.from_url(_get_settings().REDIS_URL, decode_responses=False)
    ctx["redis"] = redis
    set_redis(redis)
    correlation_id = f"arq-startup-{datetime.now(timezone.utc).isoformat()}"
    logger.info("arq_worker_started", correlation_id=correlation_id)


async def on_shutdown(ctx: dict) -> None:
    """ARQ worker shutdown hook."""
    redis = ctx.get("redis")
    if redis is not None and hasattr(redis, "aclose"):
        await redis.aclose()
    set_redis(None)
    correlation_id = f"arq-shutdown-{datetime.now(timezone.utc).isoformat()}"
    logger.info("arq_worker_stopped", correlation_id=correlation_id)


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [
        investigate_incident,
        generate_recommendation_task,
        execute_action_task,
        verify_resolution_task,
        generate_runbook_task,
    ]
    cron_jobs = [
        cron(retry_failed_incidents, second={0, 30}),
        cron(
            proactive_health_check,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
        ),
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(_get_settings().REDIS_URL)
    max_jobs = 10
    job_timeout = 120
    retry_jobs = True
    max_tries = 3
