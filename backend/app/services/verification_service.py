"""
Post-execution verification.

Runs verification checks after action execution.
Retries verification only — NEVER re-runs execution.
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.actions.registry import get_action
from app.core.config import settings
from app.core.events import emit_verification_result
from app.core.state_machine import transition_state
from app.models.enums import IncidentState
from app.models.incident import Incident

logger = structlog.get_logger()

VERIFICATION_BACKOFF = [30, 60]


async def verify_resolution(
    session: AsyncSession,
    incident: Incident,
) -> None:
    """
    Verify that execution actually resolved the incident.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
    )

    action_type = None
    if incident.meta and "recommendation" in incident.meta:
        action_type = incident.meta["recommendation"].get("proposed_action")

    if action_type is None:
        log.error("no_action_type_for_verification")
        from sqlalchemy.orm.attributes import flag_modified

        meta = dict(incident.meta or {})
        meta.setdefault("_manual_review_required", True)
        meta["_manual_review_reason"] = "Cannot verify — missing action context"
        incident.meta = meta
        flag_modified(incident, "meta")
        await session.flush()
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_VERIFICATION,
            reason="Cannot verify — no action type found",
        )
        return

    try:
        action = get_action(action_type)

        is_resolved = await asyncio.wait_for(
            action.verify(incident.meta or {}),
            timeout=settings.VERIFICATION_TIMEOUT,
        )

        if is_resolved:
            log.info("verification_passed")

            try:
                await emit_verification_result(
                    str(incident.tenant_id),
                    str(incident.id),
                    "RESOLVED",
                )
            except Exception:
                pass

            await transition_state(
                session,
                incident,
                IncidentState.RESOLVED,
                reason=f"Verification passed for {action_type}",
            )
        else:
            await _handle_verification_failure(
                session,
                incident,
                log,
                f"Verification check returned False for {action_type}",
            )

    except asyncio.TimeoutError:
        await _handle_verification_failure(
            session,
            incident,
            log,
            f"Verification timed out after {settings.VERIFICATION_TIMEOUT}s",
        )
    except Exception as exc:
        await _handle_verification_failure(
            session,
            incident,
            log,
            f"Verification exception: {exc}",
        )


async def _handle_verification_failure(
    session: AsyncSession,
    incident: Incident,
    log: structlog.stdlib.BoundLogger,
    reason: str,
) -> None:
    """Increment retry or fall back to manual review. Never re-run execution."""
    incident.verification_retry_count += 1
    current_retries = incident.verification_retry_count

    result_state = "FAILED_VERIFICATION"

    if current_retries >= settings.MAX_VERIFICATION_RETRIES:
        log.error(
            "verification_max_retries_exceeded",
            retries=current_retries,
        )
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_VERIFICATION,
            reason=f"Max verification retries ({current_retries}) exceeded: {reason}",
        )
    else:
        log.warning(
            "verification_retry_scheduled",
            retries=current_retries,
            reason=reason,
        )
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_VERIFICATION,
            reason=reason,
        )

    try:
        await emit_verification_result(
            str(incident.tenant_id),
            str(incident.id),
            result_state,
        )
    except Exception:
        pass
