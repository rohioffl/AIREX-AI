"""
Execution orchestrator.

Runs deterministic actions from ACTION_REGISTRY with distributed locking.
"""

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.actions.registry import get_action
from app.core.config import settings
from app.core.events import (
    emit_execution_completed,
    emit_execution_log,
    emit_execution_started,
)
from app.core.metrics import execution_duration_seconds, execution_total
from app.core.state_machine import transition_state
from app.models.enums import ExecutionStatus, IncidentState
from app.models.execution import Execution
from app.models.incident import Incident
from app.models.incident_lock import IncidentLock

logger = structlog.get_logger()


async def execute_action(
    session: AsyncSession,
    incident: Incident,
    action_type: str,
    redis,
    worker_id: str = "default_worker",
) -> None:
    """
    Execute an approved action.

    - Acquires Redis distributed lock (TTL = LOCK_TTL).
    - Runs the action from ACTION_REGISTRY.
    - Records execution log.
    - Transitions to VERIFYING on success, FAILED_EXECUTION on failure.
    - NEVER replays execution during verification retries.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        action_type=action_type,
        worker_id=worker_id,
    )

    lock_key = f"lock:exec:{incident.tenant_id}:{incident.id}"
    lock_acquired = await redis.set(
        lock_key, f"{worker_id}:{datetime.now(timezone.utc).isoformat()}",
        nx=True, ex=settings.LOCK_TTL,
    )
    if not lock_acquired:
        log.warning("execution_lock_contention")
        return

    # Write audit lock record
    lock_record = IncidentLock(
        tenant_id=incident.tenant_id,
        incident_id=incident.id,
        worker_id=worker_id,
        locked_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
    )
    session.add(lock_record)

    # Create execution record
    execution = Execution(
        tenant_id=incident.tenant_id,
        incident_id=incident.id,
        action_type=action_type,
        attempt=incident.execution_retry_count + 1,
        status=ExecutionStatus.RUNNING,
    )
    session.add(execution)
    await session.flush()

    # SSE: execution started
    try:
        await emit_execution_started(
            tenant_id=str(incident.tenant_id),
            incident_id=str(incident.id),
            action_type=action_type,
            execution_id=str(execution.id),
        )
    except Exception:
        pass

    start_time = datetime.now(timezone.utc)

    try:
        action = get_action(action_type)

        # SSE: log line
        try:
            await emit_execution_log(
                str(incident.tenant_id), str(incident.id),
                f"[{action_type}] Starting execution (attempt #{execution.attempt})...",
            )
        except Exception:
            pass

        result = await asyncio.wait_for(
            action.execute(incident.meta or {}),
            timeout=settings.EXECUTION_TIMEOUT,
        )

        execution.status = (
            ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
        )
        execution.logs = result.logs
        execution.completed_at = datetime.now(timezone.utc)

        duration = (execution.completed_at - start_time).total_seconds()
        execution_duration_seconds.labels(action_type=action_type).observe(duration)

        if result.success:
            log.info("execution_success")
            execution_total.labels(
                tenant_id=str(incident.tenant_id),
                action_type=action_type,
                status="success",
            ).inc()

            try:
                await emit_execution_completed(
                    str(incident.tenant_id), str(incident.id),
                    action_type, "COMPLETED", duration,
                )
            except Exception:
                pass

            await transition_state(
                session,
                incident,
                IncidentState.VERIFYING,
                reason=f"Action {action_type} executed successfully",
            )
        else:
            log.error("execution_failed", logs=result.logs)
            execution_total.labels(
                tenant_id=str(incident.tenant_id),
                action_type=action_type,
                status="failed",
            ).inc()
            incident.execution_retry_count += 1

            try:
                await emit_execution_completed(
                    str(incident.tenant_id), str(incident.id),
                    action_type, "FAILED", duration,
                )
            except Exception:
                pass

            await transition_state(
                session,
                incident,
                IncidentState.FAILED_EXECUTION,
                reason=f"Action {action_type} failed: {result.logs}",
            )

    except asyncio.TimeoutError:
        execution.status = ExecutionStatus.FAILED
        execution.logs = f"Execution timed out after {settings.EXECUTION_TIMEOUT}s"
        execution.completed_at = datetime.now(timezone.utc)
        incident.execution_retry_count += 1
        log.error("execution_timeout")
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_EXECUTION,
            reason=f"Execution timed out after {settings.EXECUTION_TIMEOUT}s",
        )

    except Exception as exc:
        execution.status = ExecutionStatus.FAILED
        execution.logs = str(exc)
        execution.completed_at = datetime.now(timezone.utc)
        incident.execution_retry_count += 1
        log.error("execution_exception", error=str(exc))
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_EXECUTION,
            reason=f"Execution exception: {exc}",
        )

    finally:
        await redis.delete(lock_key)
