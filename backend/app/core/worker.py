"""
ARQ async worker definitions.

All long-running tasks (investigate, recommend, execute, verify) run here.
Failed tasks after max retries go to DLQ via Redis list.
"""

import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import settings
from app.core.events import set_redis
from app.core.logging import setup_logging
from app.core.metrics import dlq_size
from app.core.retry_scheduler import retry_failed_incidents

setup_logging(json_output=False)
logger = structlog.get_logger()

DLQ_KEY = "airex:dlq"


async def _send_to_dlq(redis, task_name: str, tenant_id: str, incident_id: str, error: str) -> None:
    """Push a failed task onto the Dead Letter Queue."""
    entry = json.dumps({
        "task": task_name,
        "tenant_id": tenant_id,
        "incident_id": incident_id,
        "error": str(error),
        "failed_at": datetime.now(timezone.utc).isoformat(),
    })
    await redis.rpush(DLQ_KEY, entry)
    queue_len = await redis.llen(DLQ_KEY)
    dlq_size.labels(tenant_id=tenant_id).set(queue_len)
    logger.error("task_sent_to_dlq", task=task_name, tenant_id=tenant_id, incident_id=incident_id, error=str(error))


async def investigate_incident(
    ctx: dict, tenant_id: str, incident_id: str
) -> None:
    """ARQ task: run investigation for an incident."""
    from app.services.incident_service import get_incident
    from app.services.investigation_service import run_investigation
    from app.core.database import get_tenant_session

    log = logger.bind(task="investigate", tenant_id=tenant_id, incident_id=incident_id)
    log.info("task_started")

    tid = uuid.UUID(tenant_id)
    iid = uuid.UUID(incident_id)

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
        redis = ctx.get("redis")
        if redis:
            await _send_to_dlq(redis, "investigate_incident", tenant_id, incident_id, exc)


async def generate_recommendation_task(
    ctx: dict, tenant_id: str, incident_id: str
) -> None:
    """ARQ task: generate AI recommendation for an incident."""
    from app.services.incident_service import get_incident
    from app.services.recommendation_service import generate_recommendation
    from app.core.database import get_tenant_session

    log = logger.bind(task="recommend", tenant_id=tenant_id, incident_id=incident_id)
    log.info("task_started")

    tid = uuid.UUID(tenant_id)
    iid = uuid.UUID(incident_id)

    redis = ctx.get("redis")

    try:
        async with get_tenant_session(tid) as session:
            incident = await get_incident(session, tid, iid)
            if incident is None:
                log.error("incident_not_found")
                return
            await generate_recommendation(session, incident, redis=redis)
        log.info("task_completed")
    except Exception as exc:
        log.error("task_failed", error=str(exc))
        if redis:
            await _send_to_dlq(redis, "generate_recommendation_task", tenant_id, incident_id, exc)


async def execute_action_task(
    ctx: dict, tenant_id: str, incident_id: str, action_type: str
) -> None:
    """ARQ task: execute an approved action."""
    from app.services.execution_service import execute_action
    from app.services.incident_service import get_incident
    from app.core.database import get_tenant_session

    log = logger.bind(task="execute", tenant_id=tenant_id, incident_id=incident_id, action_type=action_type)
    log.info("task_started")

    tid = uuid.UUID(tenant_id)
    iid = uuid.UUID(incident_id)

    redis = ctx.get("redis")
    if redis is None:
        redis = aioredis.from_url(settings.REDIS_URL)

    try:
        async with get_tenant_session(tid) as session:
            incident = await get_incident(session, tid, iid)
            if incident is None:
                log.error("incident_not_found")
                return
            await execute_action(
                session, incident, action_type, redis,
                worker_id=f"arq-{ctx.get('job_id', 'unknown')}",
            )
        log.info("task_completed")
    except Exception as exc:
        log.error("task_failed", error=str(exc))
        if redis:
            await _send_to_dlq(redis, "execute_action_task", tenant_id, incident_id, exc)


async def verify_resolution_task(
    ctx: dict, tenant_id: str, incident_id: str
) -> None:
    """ARQ task: verify that execution resolved the incident."""
    from app.services.incident_service import get_incident
    from app.services.verification_service import verify_resolution
    from app.core.database import get_tenant_session

    log = logger.bind(task="verify", tenant_id=tenant_id, incident_id=incident_id)
    log.info("task_started")

    tid = uuid.UUID(tenant_id)
    iid = uuid.UUID(incident_id)

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
        redis = ctx.get("redis")
        if redis:
            await _send_to_dlq(redis, "verify_resolution_task", tenant_id, incident_id, exc)


async def generate_runbook_task(
    ctx: dict, tenant_id: str, incident_id: str
) -> None:
    """ARQ task: auto-generate a runbook from a resolved incident (Phase 5 ARE)."""
    from app.services.incident_service import get_incident
    from app.services.runbook_generator import generate_and_store_runbook
    from app.core.database import get_tenant_session

    log = logger.bind(task="generate_runbook", tenant_id=tenant_id, incident_id=incident_id)
    log.info("task_started")

    tid = uuid.UUID(tenant_id)
    iid = uuid.UUID(incident_id)
    redis = ctx.get("redis")

    try:
        async with get_tenant_session(tid) as session:
            incident = await get_incident(session, tid, iid)
            if incident is None:
                log.error("incident_not_found")
                return
            source_id = await generate_and_store_runbook(session, incident, redis=redis)
            if source_id:
                log.info("runbook_generated", source_id=str(source_id))
            else:
                log.info("runbook_generation_skipped")
        log.info("task_completed")
    except Exception as exc:
        log.error("task_failed", error=str(exc))
        if redis:
            await _send_to_dlq(redis, "generate_runbook_task", tenant_id, incident_id, exc)


async def on_startup(ctx: dict) -> None:
    """ARQ worker startup hook — init Redis for SSE events."""
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    ctx["redis"] = redis
    set_redis(redis)
    logger.info("arq_worker_started")


async def on_shutdown(ctx: dict) -> None:
    """ARQ worker shutdown hook."""
    redis = ctx.get("redis")
    if redis:
        await redis.aclose()
    set_redis(None)
    logger.info("arq_worker_stopped")


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
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 120
    retry_jobs = True
    max_tries = 3
