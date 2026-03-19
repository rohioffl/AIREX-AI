"""Reviewer agent — Phase 6 Operational Polish.

For HIGH/CRITICAL risk actions, makes a second LLM call with a skeptical
reviewer persona that challenges the primary recommendation.  The result
is stored in incident meta as ``_second_opinion`` and surfaced in the
approval UI so operators have a dissenting view before approving.
"""

from __future__ import annotations

from typing import Any

import structlog

from airex_core.core.config import settings
from airex_core.llm.client import LLMClient
from airex_core.models.enums import RiskLevel
from airex_core.models.incident import Incident
from airex_core.schemas.recommendation import Recommendation

logger = structlog.get_logger()

_REVIEWER_PROMPT = """\
You are a skeptical senior SRE reviewing an AI-generated incident remediation recommendation.
Your role is to challenge assumptions, identify risks, and point out anything the primary
recommendation might have missed.  Be concise but thorough.

Incident details:
  Alert type:  {alert_type}
  Severity:    {severity}
  Title:       {title}

Primary recommendation:
  Root cause:      {root_cause}
  Proposed action: {proposed_action}
  Risk level:      {risk_level}
  Confidence:      {confidence:.0%}
  Rationale:       {rationale}

Please provide:
1. CONCERNS — specific risks or unknowns the primary analysis may have overlooked
2. ALTERNATIVES — any safer/cheaper actions worth considering
3. VERDICT — one of: AGREE | CAUTION | DISAGREE (with one sentence justification)

Keep the total response under 200 words.
"""


async def run_reviewer_agent(
    incident: Incident,
    recommendation: Recommendation,
) -> dict[str, Any] | None:
    """Run the reviewer agent for HIGH/CRITICAL actions.

    Returns a dict with ``verdict``, ``concerns``, ``alternatives`` and
    ``raw_text``, or None if the reviewer is disabled / times out.
    """
    if not settings.REVIEWER_AGENT_ENABLED:
        return None

    if recommendation.risk_level not in (RiskLevel.HIGH,):
        # Only trigger for HIGH risk (there is no CRITICAL in RiskLevel — HIGH is the max)
        return None

    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        proposed_action=recommendation.proposed_action,
    )

    prompt = _REVIEWER_PROMPT.format(
        alert_type=incident.alert_type,
        severity=incident.severity.value if incident.severity else "unknown",
        title=incident.title,
        root_cause=recommendation.root_cause,
        proposed_action=recommendation.proposed_action,
        risk_level=recommendation.risk_level.value,
        confidence=recommendation.confidence,
        rationale=getattr(recommendation, "rationale", "") or "",
    )

    try:
        client = LLMClient()
        raw_text = await client.generate_text(
            prompt=prompt,
            max_tokens=300,
            temperature=0.2,
        )
    except Exception as exc:
        log.warning("reviewer_agent_llm_failed", error=str(exc))
        return None

    if raw_text is None:
        log.warning("reviewer_agent_no_response")
        return None

    verdict = _extract_verdict(raw_text)
    log.info("reviewer_agent_complete", verdict=verdict)

    return {
        "verdict": verdict,
        "raw_text": raw_text,
        "proposed_action": recommendation.proposed_action,
        "risk_level": recommendation.risk_level.value,
    }


def _extract_verdict(text: str) -> str:
    """Extract AGREE / CAUTION / DISAGREE from reviewer text."""
    upper = text.upper()
    for keyword in ("DISAGREE", "CAUTION", "AGREE"):
        if keyword in upper:
            return keyword
    return "UNKNOWN"


__all__ = ["run_reviewer_agent"]
