"""
AI recommendation orchestrator.

Generates structured recommendations via LLM with circuit breaker fallback.
"""

import re
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from airex_core.actions.registry import ACTION_REGISTRY
from airex_core.core.config import settings
from airex_core.core.execution_safety import (
    estimate_action_impact,
    evaluate_execution_guard,
)
from airex_core.core.events import emit_recommendation_ready
from airex_core.core.metrics import ai_failure_total, ai_request_total
from airex_core.core.openclaw_recommendation_bridge import OpenClawRecommendationBridge
from airex_core.core.policy import check_policy, evaluate_approval
from airex_core.core.context_resolver import resolve_execution_context
from airex_core.core.state_machine import transition_state
from airex_core.llm.client import LLMClient
from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident
from airex_core.schemas.recommendation_contract import ConfidenceBreakdown, RecommendationContract
from airex_core.services.rag_context import build_structured_context

logger = structlog.get_logger()

llm_client = LLMClient()
openclaw_recommendation_bridge = OpenClawRecommendationBridge()


async def generate_recommendation(
    session: AsyncSession,
    incident: Incident,
    redis: Any = None,
) -> None:
    """
    Generate an AI recommendation for an investigated incident.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        correlation_id=str(incident.id),
    )

    # Gather evidence text for LLM
    evidence_text = "\n---\n".join(
        f"[{e.tool_name}] {e.raw_output}" for e in incident.evidence
    )

    meta = dict(incident.meta or {})

    # Extract Site24x7 outage history from evidence if available
    site24x7_outage_context = None
    for ev in incident.evidence:
        if ev.tool_name == "site24x7_outage_probe" and ev.raw_output:
            total_match = re.search(r"total_outages['\"]?\s*[=:]\s*(\d+)", ev.raw_output)
            if total_match:
                total = int(total_match.group(1))
                if total > 0:
                    site24x7_outage_context = (
                        f"Site24x7 Outage Pattern: This monitor has had {total} outages in the last 30 days. "
                        f"This suggests a recurring issue that may require a systemic fix rather than a one-time remediation."
                    )
                    break

    context: str | None = None
    structured_context = None
    try:
        structured_context = await build_structured_context(
            session, incident, evidence_text
        )
        if structured_context:
            context = structured_context["text"] or None
    except Exception as exc:  # pragma: no cover - defensive logging
        log.warning("rag_context_failed", error=str(exc))

    # Append Site24x7 outage context if available
    if site24x7_outage_context:
        if context:
            context = f"{context}\n\n--- Site24x7 Outage Pattern Analysis ---\n{site24x7_outage_context}"
        else:
            context = (
                f"--- Site24x7 Outage Pattern Analysis ---\n{site24x7_outage_context}"
            )

    if structured_context:
        # Store structured version for frontend (cards, not raw text)
        meta["rag_context"] = structured_context.get("text", "")
        meta["rag_structured"] = {
            "runbooks": structured_context.get("runbooks", []),
            "similar_incidents": structured_context.get("similar_incidents", []),
            "pattern_analysis": structured_context.get("pattern_analysis"),
            "runbook_count": structured_context.get("runbook_count", 0),
            "incident_count": structured_context.get("incident_count", 0),
        }
        incident.meta = meta
        flag_modified(incident, "meta")

    # Adjust confidence based on historical feedback
    base_confidence_adjustment = await _get_confidence_adjustment(
        session, incident.tenant_id, incident.alert_type
    )

    recommendation = None
    if settings.OPENCLAW_ENABLED:
        ai_request_total.labels(model="openclaw").inc()
        try:
            recommendation = await openclaw_recommendation_bridge.generate_recommendation(
                alert_type=incident.alert_type,
                evidence=evidence_text,
                severity=incident.severity.value,
                context=context,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            log.warning("openclaw_recommendation_failed", error=str(exc))
            ai_failure_total.labels(model="openclaw", error_type="call_failed").inc()

    if recommendation is None:
        ai_request_total.labels(model="primary").inc()
        recommendation = await llm_client.generate_recommendation(
            alert_type=incident.alert_type,
            evidence=evidence_text,
            severity=incident.severity.value,
            context=context,
            redis=redis,
        )

    # Apply confidence adjustment from feedback learning
    if recommendation and base_confidence_adjustment != 0:
        original_confidence = recommendation.confidence
        recommendation.confidence = max(
            0.0, min(1.0, recommendation.confidence + base_confidence_adjustment)
        )
        logger.info(
            "confidence_adjusted",
            original=original_confidence,
            adjusted=recommendation.confidence,
            adjustment=base_confidence_adjustment,
            alert_type=incident.alert_type,
        )

    if recommendation is None:
        log.warning("ai_disabled_or_failed")
        ai_failure_total.labels(
            model="all", error_type="circuit_breaker_or_failure"
        ).inc()

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
        meta = dict(meta)
        meta.setdefault("_manual_review_required", True)
        meta["_manual_review_reason"] = (
            f"LLM proposed unregistered action: {recommendation.proposed_action}"
        )
        incident.meta = meta
        flag_modified(incident, "meta")
        await session.flush()
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_ANALYSIS,
            reason=f"Manual review required: invalid action {recommendation.proposed_action}",
        )
        return

    # Check policy
    allowed, reason = check_policy(
        recommendation.proposed_action, recommendation.risk_level
    )
    if not allowed:
        log.error("policy_rejected", reason=reason)
        meta = dict(meta)
        meta.setdefault("_manual_review_required", True)
        meta["_manual_review_reason"] = f"Policy rejected: {reason}"
        incident.meta = meta
        flag_modified(incident, "meta")
        await session.flush()
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_ANALYSIS,
            reason=f"Manual review required: policy rejected ({reason})",
        )
        return

    confidence_breakdown = _default_confidence_breakdown(recommendation.confidence)
    grounding_summary = "Composite confidence unavailable; using model confidence only."

    # ── Phase 6: Confidence Validator ─────────────────────────────
    try:
        from airex_core.services.confidence_validator import validate_confidence

        cv_result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action=recommendation.proposed_action,
            confidence=recommendation.confidence,
        )
        confidence_breakdown = _coerce_confidence_breakdown(
            cv_result.get("confidence_breakdown"),
            fallback_confidence=recommendation.confidence,
        )
        grounding_summary = str(
            cv_result.get("grounding_summary")
            or _default_grounding_summary(confidence_breakdown.composite_confidence)
        )
        meta["confidence_breakdown"] = confidence_breakdown.model_dump()
        meta["grounding_summary"] = grounding_summary
        if not cv_result["valid"] and cv_result.get("warning"):
            meta["_confidence_warning"] = cv_result["warning"]
            log.warning(
                "confidence_validator_flagged",
                warning=cv_result["warning"],
                kg_count=cv_result.get("kg_resolution_count"),
            )
        else:
            meta.pop("_confidence_warning", None)
    except Exception as exc:
        log.warning("confidence_validator_error", error=str(exc))
        meta["confidence_breakdown"] = confidence_breakdown.model_dump()
        meta["grounding_summary"] = grounding_summary

    impact_estimate = estimate_action_impact(
        recommendation.proposed_action,
        recommendation.params,
        risk_level=recommendation.risk_level,
        blast_radius=recommendation.blast_radius,
    )
    execution_guard = await evaluate_execution_guard(
        session,
        incident.tenant_id,
        recommendation.proposed_action,
        recommendation.params,
        exec_ctx=resolve_execution_context(recommendation.params),
    )
    meta["impact_estimate"] = impact_estimate.model_dump()
    meta["execution_guard"] = execution_guard.model_dump()

    # Store the execution-facing contract as the source of truth, while
    # keeping the legacy recommendation view for existing consumers.
    contract = RecommendationContract.from_recommendation(
        recommendation,
        confidence_breakdown=confidence_breakdown,
        grounding_summary=grounding_summary,
        impact_estimate=impact_estimate,
        execution_guard=execution_guard,
    )
    contract_dict = contract.model_dump()
    rec_dict = contract.to_legacy_recommendation()
    rec_dict = _serialize_recommendation(rec_dict)
    meta["recommendation_contract"] = contract_dict
    meta["recommendation"] = rec_dict

    # ── Phase 6: Reviewer Agent ────────────────────────────────────
    try:
        from airex_core.services.reviewer_service import run_reviewer_agent

        second_opinion = await run_reviewer_agent(incident, recommendation)
        if second_opinion:
            meta["_second_opinion"] = second_opinion
    except Exception as exc:
        log.warning("reviewer_agent_error", error=str(exc))

    # Evaluate approval policy (confidence-gated + senior approval)
    approval_confidence = confidence_breakdown.composite_confidence
    decision = evaluate_approval(
        action_type=recommendation.proposed_action,
        confidence=approval_confidence,
        risk_level=recommendation.risk_level,
    )

    # Store approval decision in meta for the approval endpoint to enforce
    meta["_approval_level"] = decision.level.value
    meta["_approval_reason"] = decision.reason
    meta["_confidence_met"] = decision.confidence_met
    meta["_senior_required"] = decision.senior_required
    meta["_approval_confidence"] = approval_confidence
    meta["_approval_confidence_source"] = "composite"

    incident.meta = meta
    flag_modified(incident, "meta")
    await session.flush()

    log.info(
        "recommendation_generated",
        action=recommendation.proposed_action,
        risk=recommendation.risk_level.value,
        confidence=recommendation.confidence,
        composite_confidence=approval_confidence,
        approval_level=decision.level.value,
        requires_human=decision.requires_human,
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

    # All actions require human approval — transition to AWAITING_APPROVAL
    await transition_state(
        session,
        incident,
        IncidentState.AWAITING_APPROVAL,
        reason=decision.reason,
    )


def _serialize_recommendation(rec_dict: dict) -> dict:
    """Recursively convert enum values to strings for JSON storage.

    Handles the top-level risk_level and nested risk_level in alternatives.
    """
    # Top-level risk_level
    if "risk_level" in rec_dict:
        rl = rec_dict["risk_level"]
        rec_dict["risk_level"] = rl.value if hasattr(rl, "value") else rl

    # Alternatives contain nested risk_level enums
    if "alternatives" in rec_dict and isinstance(rec_dict["alternatives"], list):
        for alt in rec_dict["alternatives"]:
            if isinstance(alt, dict) and "risk_level" in alt:
                arl = alt["risk_level"]
                alt["risk_level"] = arl.value if hasattr(arl, "value") else arl

    return rec_dict


def _coerce_confidence_breakdown(
    payload: object,
    *,
    fallback_confidence: float,
) -> ConfidenceBreakdown:
    if isinstance(payload, ConfidenceBreakdown):
        return payload
    if isinstance(payload, dict):
        return ConfidenceBreakdown.model_validate(payload)
    return _default_confidence_breakdown(fallback_confidence)


def _default_confidence_breakdown(confidence: float) -> ConfidenceBreakdown:
    return ConfidenceBreakdown(
        model_confidence=confidence,
        evidence_strength_score=0.0,
        tool_grounding_score=0.0,
        kg_match_score=0.0,
        hallucination_penalty=0.0,
        composite_confidence=confidence,
        warning="",
    )


def _default_grounding_summary(confidence: float) -> str:
    return (
        "Composite confidence unavailable; "
        f"using model confidence {confidence:.0%}."
    )


async def _get_confidence_adjustment(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    alert_type: str,
) -> float:
    """
    Calculate confidence adjustment based on historical approval/rejection patterns.

    Returns a float between -0.2 and +0.2:
    - Positive: more approvals than rejections -> increase confidence
    - Negative: more rejections than approvals -> decrease confidence
    - Zero: no feedback or balanced feedback
    """
    try:
        from airex_core.models.feedback_learning import FeedbackLearning
        from sqlalchemy import func, select
        from datetime import datetime, timedelta, timezone

        # Get recent feedback for this alert type (last 30 days)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        result = await session.execute(
            select(
                FeedbackLearning.action_taken,
                func.count(FeedbackLearning.id).label("count"),
            )
            .where(
                FeedbackLearning.tenant_id == tenant_id,
                FeedbackLearning.created_at >= cutoff,
            )
            .group_by(FeedbackLearning.action_taken)
        )
        feedback_counts = {row.action_taken: row.count for row in result.all()}

        approved = feedback_counts.get("approved", 0)
        rejected = feedback_counts.get("rejected", 0)
        total = approved + rejected

        if total == 0:
            return 0.0

        # Calculate adjustment: (approval_rate - 0.5) * 0.4
        # If 100% approved -> +0.2, if 100% rejected -> -0.2
        approval_rate = approved / total
        adjustment = (approval_rate - 0.5) * 0.4

        logger.debug(
            "confidence_adjustment_calculated",
            alert_type=alert_type,
            approved=approved,
            rejected=rejected,
            approval_rate=approval_rate,
            adjustment=adjustment,
        )

        return adjustment

    except Exception as exc:
        logger.warning("confidence_adjustment_failed", error=str(exc))
        return 0.0
