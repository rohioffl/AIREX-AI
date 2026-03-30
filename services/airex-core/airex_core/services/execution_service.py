"""
Execution orchestrator.

Runs deterministic actions from ACTION_REGISTRY with distributed locking.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.actions.registry import get_action
from airex_core.core.config import settings
from airex_core.core.context_resolver import resolve_execution_context
from airex_core.core.execution_safety import evaluate_execution_guard
from airex_core.core.events import (
    emit_execution_completed,
    emit_execution_log,
    emit_execution_started,
)
from airex_core.core.metrics import execution_duration_seconds, execution_total
from airex_core.core.policy import check_bounds, check_scope
from airex_core.core.state_machine import transition_state
from airex_core.models.enums import ExecutionStatus, IncidentState
from airex_core.models.execution import Execution
from airex_core.models.incident import Incident
from airex_core.models.incident_lock import IncidentLock

logger = structlog.get_logger()


async def execute_action(
    session: AsyncSession,
    incident: Incident,
    action_type: str,
    redis: Any,
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
        correlation_id=str(incident.id),
        action_type=action_type,
        worker_id=worker_id,
    )

    lock_key = f"lock:exec:{incident.tenant_id}:{incident.id}"
    lock_acquired = await redis.set(
        lock_key,
        f"{worker_id}:{datetime.now(timezone.utc).isoformat()}",
        nx=True,
        ex=settings.LOCK_TTL,
    )
    if not lock_acquired:
        log.warning("execution_lock_contention")
        return

    # Phase 3b: Idempotency protection — prevent replay of the same approved action.
    # Key is scoped to (tenant, incident, action_type, snapshot_hash) so that
    # a re-approval with different params generates a distinct key.
    snapshot_meta = (incident.meta or {}).get("execution_snapshot") or {}
    snapshot_hash = snapshot_meta.get("snapshot_hash", "")
    idempotency_key = (
        f"idempotent:{incident.tenant_id}:{incident.id}:{action_type}:{snapshot_hash}"
    )
    if snapshot_hash:
        previous = await redis.get(idempotency_key)
        if previous:
            log.warning(
                "execution_idempotency_skip",
                idempotency_key=idempotency_key,
                previous_run=previous.decode() if isinstance(previous, bytes) else previous,
            )
            await redis.delete(lock_key)
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

    # Check tenant daily execution limit
    from airex_core.core.tenant_limits import check_daily_executions

    allowed, current, max_allowed = await check_daily_executions(
        session, incident.tenant_id
    )
    if not allowed:
        log.warning(
            "execution_limit_exceeded",
            current=current,
            max=max_allowed,
        )
        # Still allow execution but log warning
        # In strict mode, you might want to raise an exception here

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
                str(incident.tenant_id),
                str(incident.id),
                f"[{action_type}] Starting execution (attempt #{execution.attempt})...",
            )
        except Exception:
            pass

        # Read params from frozen snapshot (set at approval time) to prevent
        # approval drift — never read live incident.meta during execution.
        snapshot = (incident.meta or {}).get("execution_snapshot")
        exec_params = snapshot["params"] if snapshot else (incident.meta or {})
        if snapshot:
            log.info(
                "execution_snapshot_loaded",
                snapshot_hash=snapshot.get("snapshot_hash"),
                approved_by=snapshot.get("approved_by"),
                approved_at=snapshot.get("approved_at"),
            )
        else:
            log.warning("execution_snapshot_missing", fallback="live_meta")

        # Phase 3a: Bounds enforcement — replica caps + environment guards.
        bounds_ok, bounds_reason = check_bounds(
            action_type, exec_params, str(incident.id)
        )
        if not bounds_ok:
            raise ValueError(f"Bounds violation: {bounds_reason}")

        # Phase 3c: Action scoping — required targeting fields must be present.
        scope_ok, scope_reason = check_scope(
            action_type, exec_params, str(incident.id)
        )
        if not scope_ok:
            raise ValueError(f"Scope violation: {scope_reason}")

        # Phase 3e: Execution Context Resolver — enrich params with resolved context.
        exec_ctx = resolve_execution_context(exec_params)
        exec_params = {
            **exec_params,
            "_exec_context": {
                "cloud": exec_ctx.cloud,
                "instance_id": exec_ctx.instance_id,
                "region": exec_ctx.region,
                "zone": exec_ctx.zone,
                "exec_mode": exec_ctx.exec_mode,
                "environment": exec_ctx.environment,
                "namespace": exec_ctx.namespace,
                "cluster": exec_ctx.cluster,
                "service_name": exec_ctx.service_name,
                "tenant_name": exec_ctx.tenant_name,
            },
        }
        log.info(
            "execution_context_ready",
            exec_mode=exec_ctx.exec_mode,
            cloud=exec_ctx.cloud,
            environment=exec_ctx.environment,
        )

        execution_guard = await evaluate_execution_guard(
            session,
            incident.tenant_id,
            action_type,
            exec_params,
            exec_ctx=exec_ctx,
        )
        if not execution_guard.valid:
            raise ValueError(f"Execution guard failed: {execution_guard.reason}")
        exec_params["_execution_guard"] = execution_guard.model_dump()

        result = await asyncio.wait_for(
            action.execute(exec_params),
            timeout=settings.EXECUTION_TIMEOUT,
        )

        execution.status = (
            ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
        )
        execution.logs = result.logs
        completed_at = datetime.now(timezone.utc)
        execution.completed_at = completed_at

        duration = (completed_at - start_time).total_seconds()
        execution_duration_seconds.labels(action_type=action_type).observe(duration)

        if result.success:
            log.info("execution_success")
            execution_total.labels(
                tenant_id=str(incident.tenant_id),
                action_type=action_type,
                status="success",
            ).inc()

            # Phase 3b: Stamp idempotency key so this action cannot replay.
            # TTL = 24 h — long enough to cover any retry/verification window.
            if snapshot_hash:
                await redis.set(
                    idempotency_key,
                    datetime.now(timezone.utc).isoformat(),
                    ex=86400,
                )

            try:
                await emit_execution_completed(
                    str(incident.tenant_id),
                    str(incident.id),
                    action_type,
                    "COMPLETED",
                    duration,
                )
            except Exception:
                pass

            await transition_state(
                session,
                incident,
                IncidentState.VERIFYING,
                reason=f"Action {action_type} executed successfully",
            )

            # Auto-enqueue verification task
            await _enqueue_verification(incident, log)
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
                    str(incident.tenant_id),
                    str(incident.id),
                    action_type,
                    "FAILED",
                    duration,
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

    except (RuntimeError, ValueError, TypeError) as exc:
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


async def _enqueue_verification(
    incident: Incident, log: structlog.stdlib.BoundLogger
) -> None:
    """Enqueue the verification ARQ task after successful execution."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await pool.enqueue_job(
            "verify_resolution_task",
            str(incident.tenant_id),
            str(incident.id),
            _defer_by=30,  # wait 30s before verifying
        )
        await pool.aclose()
        log.info("verification_task_enqueued")
    except Exception as exc:
        log.error("verification_enqueue_failed", error=str(exc))
