"""Incident state transition graph and audited transition helper.

All incident state transitions MUST go through :func:`transition_state`.
Direct mutation of ``incident.state`` is prohibited everywhere else.
"""

import hashlib
import uuid

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IncidentState
from app.models.incident import Incident
from app.models.state_transition import StateTransition

ALLOWED_TRANSITIONS: dict[IncidentState, list[IncidentState]] = {
    IncidentState.RECEIVED: [
        IncidentState.INVESTIGATING,
    ],
    IncidentState.INVESTIGATING: [
        IncidentState.RECOMMENDATION_READY,
        IncidentState.FAILED_ANALYSIS,
        IncidentState.REJECTED,
    ],
    IncidentState.RECOMMENDATION_READY: [
        IncidentState.AWAITING_APPROVAL,
        IncidentState.REJECTED,
    ],
    IncidentState.AWAITING_APPROVAL: [
        IncidentState.EXECUTING,
        IncidentState.REJECTED,
    ],
    IncidentState.EXECUTING: [
        IncidentState.VERIFYING,
        IncidentState.FAILED_EXECUTION,
        IncidentState.REJECTED,
    ],
    IncidentState.VERIFYING: [
        IncidentState.RESOLVED,
        IncidentState.FAILED_VERIFICATION,
        IncidentState.REJECTED,
    ],
    IncidentState.FAILED_VERIFICATION: [
        IncidentState.RESOLVED,  # verification retry succeeds
        IncidentState.FAILED_VERIFICATION,  # verification retry fails again
        IncidentState.AWAITING_APPROVAL,  # fallback to alternative action (Phase 3 ARE)
        IncidentState.REJECTED,
    ],
    IncidentState.FAILED_ANALYSIS: [
        IncidentState.RECOMMENDATION_READY,  # investigation retry succeeds
        IncidentState.FAILED_ANALYSIS,  # investigation retry fails again
        IncidentState.REJECTED,
    ],
    IncidentState.FAILED_EXECUTION: [
        IncidentState.REJECTED,
    ],
}

TERMINAL_STATES: set[IncidentState] = {
    IncidentState.RESOLVED,
    IncidentState.REJECTED,
    # Note: FAILED_ANALYSIS and FAILED_VERIFICATION are NOT terminal
    # They can be retried via the retry scheduler
}


logger = structlog.get_logger()


class IllegalStateTransition(Exception):
    """Raised when an attempted state transition violates the graph."""

    def __init__(self, current: IncidentState, target: IncidentState) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Illegal transition: {current.value} -> {target.value}")


def _compute_hash(
    previous_hash: str, from_state: str, to_state: str, reason: str
) -> str:
    """SHA256 hash chain: H(prev_hash : from : to : reason)."""
    payload = f"{previous_hash}:{from_state}:{to_state}:{reason}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def transition_state(
    session: AsyncSession,
    incident: Incident,
    new_state: IncidentState,
    reason: str,
    actor: str = "system",
) -> StateTransition:
    """
    The ONLY sanctioned way to change incident state.

    1. Validates the transition against ALLOWED_TRANSITIONS.
    2. Computes the hash chain link.
    3. Creates an immutable StateTransition audit record.
    4. Updates the incident state.
    5. Emits SSE event + Prometheus metric.

    Raises IllegalStateTransition if the transition is not allowed.
    """
    correlation_id = str(uuid.uuid4())
    transition_logger = logger.bind(
        correlation_id=correlation_id,
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        actor=actor,
    )

    from app.core.metrics import state_transition_total

    allowed = ALLOWED_TRANSITIONS.get(incident.state, [])
    if new_state not in allowed:
        transition_logger.warning(
            "illegal_state_transition_attempt",
            from_state=incident.state.value,
            to_state=new_state.value,
            reason=reason,
        )
        raise IllegalStateTransition(incident.state, new_state)

    old_state = incident.state

    # Fetch latest transition for hash chain continuity
    result = await session.execute(
        select(StateTransition)
        .where(
            StateTransition.tenant_id == incident.tenant_id,
            StateTransition.incident_id == incident.id,
        )
        .order_by(desc(StateTransition.created_at))
        .limit(1)
    )
    prev = result.scalar_one_or_none()
    previous_hash = prev.hash if prev else "GENESIS"

    # Compute tamper-evident hash
    new_hash = _compute_hash(
        previous_hash, incident.state.value, new_state.value, reason
    )

    # Create immutable audit record
    transition = StateTransition(
        tenant_id=incident.tenant_id,
        incident_id=incident.id,
        from_state=incident.state,
        to_state=new_state,
        reason=reason,
        actor=actor,
        previous_hash=previous_hash,
        hash=new_hash,
    )
    session.add(transition)

    # Mutate state — ONLY allowed inside this function
    incident.state = new_state

    # Prometheus metric
    state_transition_total.labels(
        tenant_id=str(incident.tenant_id),
        from_state=old_state.value,
        to_state=new_state.value,
    ).inc()

    # SSE event (fire-and-forget, don't fail transition if Redis is down)
    try:
        from app.core.events import emit_state_changed

        await emit_state_changed(
            tenant_id=str(incident.tenant_id),
            incident_id=str(incident.id),
            from_state=old_state.value,
            to_state=new_state.value,
            reason=reason,
        )
    except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
        transition_logger.warning(
            "state_changed_event_emit_failed",
            from_state=old_state.value,
            to_state=new_state.value,
            error=str(exc),
            error_type=type(exc).__name__,
        )

    # Send notifications for critical state changes (fire-and-forget)
    try:
        from app.services.notification_service import notify_incident_state_change

        await notify_incident_state_change(
            session=session,
            incident_id=str(incident.id),
            tenant_id=str(incident.tenant_id),
            old_state=old_state,
            new_state=new_state,
            severity=incident.severity,
            title=incident.title,
        )
    except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError) as exc:
        transition_logger.warning(
            "state_change_notification_failed",
            from_state=old_state.value,
            to_state=new_state.value,
            error=str(exc),
            error_type=type(exc).__name__,
        )

    if new_state in TERMINAL_STATES:
        # Record structured resolution outcome (Phase 2 ARE)
        try:
            from app.services.resolution_service import record_resolution

            await record_resolution(session, incident)
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exc:
            transition_logger.warning(
                "resolution_recording_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # Upsert embedding for RAG similarity search
        try:
            from app.services.incident_embedding_service import (
                upsert_incident_embedding,
            )

            await upsert_incident_embedding(session, incident)
        except (
            ConnectionError,
            TimeoutError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exc:
            transition_logger.warning(
                "incident_embedding_upsert_failed",
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # Enqueue runbook auto-generation for resolved incidents (Phase 5 ARE)
        if new_state == IncidentState.RESOLVED:
            try:
                from arq import create_pool
                from arq.connections import RedisSettings
                from app.core.config import settings as _settings

                pool = await create_pool(RedisSettings.from_dsn(_settings.REDIS_URL))
                await pool.enqueue_job(
                    "generate_runbook_task",
                    str(incident.tenant_id),
                    str(incident.id),
                    _defer_by=5,  # slight delay to let resolution recording finish
                )
                await pool.aclose()
            except (
                ConnectionError,
                TimeoutError,
                OSError,
                RuntimeError,
                ValueError,
            ) as exc:
                transition_logger.warning(
                    "runbook_generation_enqueue_failed",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

    transition_logger.info(
        "state_transition_completed",
        from_state=old_state.value,
        to_state=new_state.value,
        reason=reason,
    )

    return transition
