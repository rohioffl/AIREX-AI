"""
Alternative-action fallback after verification failure (Phase 3 ARE).

When verification fails and max retries are exhausted, this service selects
the next untried alternative from the recommendation's alternatives list,
re-evaluates approval policy, and routes the incident back through the
approval → execution → verification pipeline with the fallback action.

NEVER creates new states. Uses existing FAILED_VERIFICATION → AWAITING_APPROVAL
transition added in Phase 3.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.actions.registry import ACTION_REGISTRY
from app.core.config import settings
from app.core.policy import check_policy, evaluate_approval
from app.core.state_machine import transition_state
from app.models.enums import IncidentState, RiskLevel
from app.models.incident import Incident

logger = structlog.get_logger()


def select_next_alternative(incident: Incident) -> dict | None:
    """
    Select the next untried alternative action from the recommendation.

    Returns the alternative dict if one is available, None if all exhausted.
    Skips alternatives that:
      - Have already been tried (in _fallback_history)
      - Are not in ACTION_REGISTRY
      - Are the same as the original proposed_action
    """
    meta = incident.meta or {}
    recommendation = meta.get("recommendation", {})
    alternatives = recommendation.get("alternatives", [])
    original_action = recommendation.get("proposed_action", "")

    # Build set of already-tried actions
    fallback_history: list[dict] = meta.get("_fallback_history", [])
    tried_actions: set[str] = {original_action}
    for entry in fallback_history:
        tried_actions.add(entry.get("action", ""))

    # Enforce max fallback limit
    if len(fallback_history) >= settings.MAX_FALLBACK_ALTERNATIVES:
        return None

    for alt in alternatives:
        action = alt.get("action", "")
        if action in tried_actions:
            continue
        if action not in ACTION_REGISTRY:
            continue
        return alt

    return None


async def attempt_fallback(
    session: AsyncSession,
    incident: Incident,
    failed_action: str,
    failure_reason: str,
) -> bool:
    """
    Attempt to fall back to an alternative action after verification failure.

    Returns True if a fallback was initiated, False if no alternatives remain.

    Flow:
    1. Select next untried alternative
    2. Record the failed action in _fallback_history
    3. Swap the recommendation's proposed_action to the alternative
    4. Re-evaluate approval policy
    5. Reset verification_retry_count
    6. Transition FAILED_VERIFICATION → AWAITING_APPROVAL (or auto-approve)
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        failed_action=failed_action,
    )

    alternative = select_next_alternative(incident)
    if alternative is None:
        log.info("no_alternatives_remaining")
        return False

    alt_action = alternative["action"]
    alt_confidence = alternative.get("confidence", 0.0)
    alt_risk_str = alternative.get("risk_level", "MED")

    # Parse risk level safely
    try:
        alt_risk = RiskLevel(alt_risk_str)
    except ValueError:
        alt_risk = RiskLevel.MED

    # Check policy for the alternative action
    allowed, policy_reason = check_policy(alt_action, alt_risk)
    if not allowed:
        log.warning(
            "fallback_policy_rejected",
            action=alt_action,
            reason=policy_reason,
        )
        # Record it as tried but rejected, then try the next one
        meta = dict(incident.meta or {})
        fallback_history = list(meta.get("_fallback_history", []))
        fallback_history.append({
            "action": alt_action,
            "status": "policy_rejected",
            "reason": policy_reason,
            "attempted_at": datetime.now(timezone.utc).isoformat(),
        })
        meta["_fallback_history"] = fallback_history
        incident.meta = meta
        flag_modified(incident, "meta")
        await session.flush()
        # Recurse to try the next alternative
        return await attempt_fallback(
            session, incident, failed_action, failure_reason
        )

    # --- Fallback is viable ---

    meta = dict(incident.meta or {})
    recommendation = dict(meta.get("recommendation", {}))

    # 1. Record the failed action in fallback history
    fallback_history = list(meta.get("_fallback_history", []))
    fallback_history.append({
        "action": failed_action,
        "status": "verification_failed",
        "reason": failure_reason,
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    })
    meta["_fallback_history"] = fallback_history

    # 2. Store original action if this is the first fallback
    if "_original_proposed_action" not in meta:
        meta["_original_proposed_action"] = recommendation.get("proposed_action", "")

    # 3. Swap the proposed action to the alternative
    recommendation["proposed_action"] = alt_action
    recommendation["confidence"] = alt_confidence
    recommendation["risk_level"] = alt_risk.value
    recommendation["rationale"] = alternative.get("rationale", "")
    meta["recommendation"] = recommendation

    # 4. Re-evaluate approval policy
    decision = evaluate_approval(
        action_type=alt_action,
        confidence=alt_confidence,
        risk_level=alt_risk,
    )
    meta["_approval_level"] = decision.level.value
    meta["_approval_reason"] = decision.reason
    meta["_confidence_met"] = decision.confidence_met
    meta["_senior_required"] = decision.senior_required
    meta["_is_fallback"] = True
    meta["_fallback_from"] = failed_action

    incident.meta = meta
    flag_modified(incident, "meta")

    # 5. Reset verification retry count for the new action
    incident.verification_retry_count = 0

    await session.flush()

    log.info(
        "fallback_initiated",
        from_action=failed_action,
        to_action=alt_action,
        confidence=alt_confidence,
        risk=alt_risk.value,
        approval_level=decision.level.value,
        fallback_number=len(fallback_history),
    )

    # 6. Transition to AWAITING_APPROVAL
    if decision.requires_human:
        await transition_state(
            session,
            incident,
            IncidentState.AWAITING_APPROVAL,
            reason=(
                f"Fallback to alternative action '{alt_action}' after "
                f"'{failed_action}' verification failed: {decision.reason}"
            ),
            actor="fallback_engine",
        )
    else:
        # Auto-approve: go through AWAITING_APPROVAL → EXECUTING
        await transition_state(
            session,
            incident,
            IncidentState.AWAITING_APPROVAL,
            reason=(
                f"Fallback to alternative action '{alt_action}' after "
                f"'{failed_action}' verification failed: {decision.reason}"
            ),
            actor="fallback_engine",
        )
        await transition_state(
            session,
            incident,
            IncidentState.EXECUTING,
            reason=f"Auto-approved fallback action: {alt_action}",
            actor="auto_approval",
        )

        # Enqueue execution task
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            await pool.enqueue_job(
                "execute_action_task",
                str(incident.tenant_id),
                str(incident.id),
                alt_action,
            )
            await pool.aclose()
            log.info("fallback_execution_enqueued", action=alt_action)
        except Exception as exc:
            log.error("fallback_execution_enqueue_failed", error=str(exc))

    return True
