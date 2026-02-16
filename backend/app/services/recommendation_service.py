"""
AI recommendation orchestrator.

Generates structured recommendations via LLM with circuit breaker fallback.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.actions.registry import ACTION_REGISTRY
from app.core.events import emit_recommendation_ready
from app.core.metrics import ai_failure_total, ai_request_total
from app.core.policy import check_policy, requires_approval
from app.core.state_machine import transition_state
from app.llm.client import LLMClient
from app.models.enums import IncidentState
from app.models.incident import Incident
from app.schemas.recommendation import Recommendation

logger = structlog.get_logger()

llm_client = LLMClient()


async def generate_recommendation(
    session: AsyncSession,
    incident: Incident,
    redis=None,
) -> None:
    """
    Generate an AI recommendation for an investigated incident.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
    )

    # Gather evidence text for LLM
    evidence_text = "\n---\n".join(
        f"[{e.tool_name}] {e.raw_output}" for e in incident.evidence
    )

    ai_request_total.labels(model="primary").inc()

    recommendation = await llm_client.generate_recommendation(
        alert_type=incident.alert_type,
        evidence=evidence_text,
        severity=incident.severity.value,
        redis=redis,
    )

    if recommendation is None:
        log.warning("ai_disabled_or_failed")
        ai_failure_total.labels(model="all", error_type="circuit_breaker_or_failure").inc()
        from sqlalchemy.orm.attributes import flag_modified

        meta = dict(incident.meta or {})
        meta["recommendation_note"] = "AI unavailable — manual review required"
        incident.meta = meta
        flag_modified(incident, "meta")

        await transition_state(
            session,
            incident,
            IncidentState.AWAITING_APPROVAL,
            reason="AI circuit breaker open or LLM failure — manual mode",
        )
        return

    # Validate proposed_action is in ACTION_REGISTRY
    if recommendation.proposed_action not in ACTION_REGISTRY:
        log.error(
            "invalid_proposed_action",
            action=recommendation.proposed_action,
        )
        await transition_state(
            session,
            incident,
            IncidentState.ESCALATED,
            reason=f"LLM proposed unregistered action: {recommendation.proposed_action}",
        )
        return

    # Check policy
    allowed, reason = check_policy(
        recommendation.proposed_action, recommendation.risk_level
    )
    if not allowed:
        log.error("policy_rejected", reason=reason)
        await transition_state(
            session,
            incident,
            IncidentState.ESCALATED,
            reason=f"Policy rejected: {reason}",
        )
        return

    # Store recommendation in incident meta
    from sqlalchemy.orm.attributes import flag_modified

    meta = dict(incident.meta or {})
    rec_dict = recommendation.model_dump()
    rec_dict["risk_level"] = rec_dict["risk_level"].value if hasattr(rec_dict["risk_level"], "value") else rec_dict["risk_level"]
    meta["recommendation"] = rec_dict
    incident.meta = meta
    flag_modified(incident, "meta")
    await session.flush()

    log.info(
        "recommendation_generated",
        action=recommendation.proposed_action,
        risk=recommendation.risk_level.value,
        confidence=recommendation.confidence,
    )

    # SSE: recommendation ready
    try:
        await emit_recommendation_ready(
            tenant_id=str(incident.tenant_id),
            incident_id=str(incident.id),
            recommendation=rec_dict,
        )
    except Exception:
        pass

    # Transition based on approval policy
    if requires_approval(recommendation.proposed_action):
        await transition_state(
            session,
            incident,
            IncidentState.AWAITING_APPROVAL,
            reason=f"Recommendation: {recommendation.proposed_action} (confidence={recommendation.confidence:.2f})",
        )
    else:
        await transition_state(
            session,
            incident,
            IncidentState.AWAITING_APPROVAL,
            reason=f"Auto-approvable: {recommendation.proposed_action}",
        )
