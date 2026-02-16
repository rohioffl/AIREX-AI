"""
Retry scheduler — ARQ cron task that picks up retryable incidents
and re-queues investigation/verification tasks with backoff.

Runs every 30 seconds. Only re-queues if retry_count < max_retries.
NEVER re-queues executions (verification retries != execution replays).
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.enums import IncidentState
from app.models.incident import Incident

logger = structlog.get_logger()

RETRYABLE_STATES = {
    IncidentState.FAILED_ANALYSIS: "investigate_incident",
    IncidentState.FAILED_VERIFICATION: "verify_resolution_task",
}


async def retry_failed_incidents(ctx: dict) -> None:
    """
    Cron task: scan for incidents in FAILED_* states that still
    have retries left, and re-queue the appropriate worker task.
    """
    redis = ctx.get("redis")
    if redis is None:
        return

    async with async_session_factory() as session:
        for state, task_name in RETRYABLE_STATES.items():
            max_retries = (
                settings.MAX_INVESTIGATION_RETRIES
                if state == IncidentState.FAILED_ANALYSIS
                else settings.MAX_VERIFICATION_RETRIES
            )

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
            incidents = result.scalars().all()

            for incident in incidents:
                lock_key = f"retry_lock:{incident.tenant_id}:{incident.id}:{state.value}"
                locked = await redis.set(lock_key, "1", nx=True, ex=120)
                if not locked:
                    continue

                logger.info(
                    "retry_scheduled",
                    task=task_name,
                    tenant_id=str(incident.tenant_id),
                    incident_id=str(incident.id),
                    state=state.value,
                )

                try:
                    from arq import create_pool
                    from arq.connections import RedisSettings

                    pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
                    await pool.enqueue_job(
                        task_name,
                        str(incident.tenant_id),
                        str(incident.id),
                    )
                    await pool.aclose()
                except Exception as exc:
                    logger.error("retry_enqueue_failed", error=str(exc))
