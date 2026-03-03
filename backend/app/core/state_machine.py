"""
The State Machine — THE LAW.

All incident state transitions MUST go through transition_state().
Direct mutation of incident.state is PROHIBITED everywhere else.
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
    from app.core.metrics import state_transition_total

    allowed = ALLOWED_TRANSITIONS.get(incident.state, [])
    if new_state not in allowed:
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
    except Exception:
        pass

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
    except Exception:
        pass  # Don't fail state transition if notifications fail

    if new_state in TERMINAL_STATES:
        # Record structured resolution outcome (Phase 2 ARE)
        try:
            from app.services.resolution_service import record_resolution

            await record_resolution(session, incident)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "resolution_recording_failed",
                incident_id=str(incident.id),
                error=str(exc),
            )

        # Upsert embedding for RAG similarity search
        try:
            from app.services.incident_embedding_service import (
                upsert_incident_embedding,
            )

            await upsert_incident_embedding(session, incident)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "incident_embedding_upsert_failed",
                incident_id=str(incident.id),
                error=str(exc),
            )

    return transition
