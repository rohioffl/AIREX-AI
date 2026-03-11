"""
Retry scheduler — ARQ cron task that picks up retryable incidents
and re-queues investigation/verification tasks with backoff.

Runs every 30 seconds. Only re-queues if retry_count < max_retries.
NEVER re-queues executions (verification retries != execution replays).
"""

import uuid
import importlib
from collections.abc import Mapping
from typing import Any, cast

import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident

logger = structlog.get_logger()

RETRYABLE_STATES: dict[IncidentState, str] = {
    IncidentState.FAILED_ANALYSIS: "investigate_incident",
    IncidentState.FAILED_VERIFICATION: "verify_resolution_task",
}


def _build_retry_logger(correlation_id: str) -> structlog.typing.FilteringBoundLogger:
    return logger.bind(task="retry_failed_incidents", correlation_id=correlation_id)


def _get_settings() -> Any:
    module = importlib.import_module("airex_core.core.config")
    return cast(Any, module.settings)


def _get_async_session_factory() -> Any:
    module = importlib.import_module("airex_core.core.database")
    return cast(Any, module.async_session_factory)


async def _enqueue_retry_job(
    task_name: str,
    tenant_id: uuid.UUID,
    incident_id: uuid.UUID,
) -> None:
    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(_get_settings().REDIS_URL))
    try:
        await pool.enqueue_job(task_name, str(tenant_id), str(incident_id))
    finally:
        await pool.aclose()


async def _query_retryable_incidents(
    session: AsyncSession,
    state: IncidentState,
    max_retries: int,
) -> list[Incident]:
    retry_col = (
        Incident.investigation_retry_count
        if state == IncidentState.FAILED_ANALYSIS
        else Incident.verification_retry_count
    )
    result = await session.execute(
        select(Incident).where(
            Incident.state == state,
            retry_col < max_retries,
            Incident.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def retry_failed_incidents(ctx: Mapping[str, object]) -> None:
    """
    Cron task: scan for incidents in FAILED_* states that still
    have retries left, and re-queue the appropriate worker task.
    """
    correlation_id = f"retry-{ctx.get('job_id', 'unknown')}"
    log = _build_retry_logger(correlation_id)
    redis_obj = ctx.get("redis")
    if not isinstance(redis_obj, Redis):
        log.warning("retry_scheduler_redis_missing")
        return
    redis = cast(Any, redis_obj)

    settings = _get_settings()
    async_session_factory = _get_async_session_factory()

    async with async_session_factory() as session:
        try:
            for state, task_name in RETRYABLE_STATES.items():
                max_retries = (
                    settings.MAX_INVESTIGATION_RETRIES
                    if state == IncidentState.FAILED_ANALYSIS
                    else settings.MAX_VERIFICATION_RETRIES
                )

                incidents = await _query_retryable_incidents(
                    session, state, max_retries
                )

                for incident in incidents:
                    lock_key = (
                        f"retry_lock:{incident.tenant_id}:{incident.id}:{state.value}"
                    )
                    locked = await redis.set(lock_key, "1", nx=True, ex=120)
                    if not locked:
                        continue

                    log.info(
                        "retry_scheduled",
                        task=task_name,
                        tenant_id=str(incident.tenant_id),
                        incident_id=str(incident.id),
                        state=state.value,
                    )

                    try:
                        await _enqueue_retry_job(
                            task_name,
                            incident.tenant_id,
                            incident.id,
                        )
                    except (ConnectionError, TimeoutError) as exc:
                        log.error(
                            "retry_enqueue_failed_redis",
                            error=str(exc),
                            task=task_name,
                            tenant_id=str(incident.tenant_id),
                            incident_id=str(incident.id),
                        )
                    except Exception as exc:
                        log.error(
                            "retry_enqueue_failed",
                            error=str(exc),
                            task=task_name,
                            tenant_id=str(incident.tenant_id),
                            incident_id=str(incident.id),
                        )
        except SQLAlchemyError as exc:
            log.error("retry_query_failed", error=str(exc))
