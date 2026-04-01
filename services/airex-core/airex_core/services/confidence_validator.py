"""Confidence validator — Phase 6 Operational Polish.

Cross-checks recommendation confidence against Knowledge Graph history and
derives a composite score that is safer to use for approval decisions than the
raw model confidence alone.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.config import settings
from airex_core.core.knowledge_graph import make_entity_id
from airex_core.models.incident import Incident
from airex_core.schemas.recommendation_contract import ConfidenceBreakdown

logger = structlog.get_logger()


async def validate_confidence(
    session: AsyncSession,
    incident: Incident,
    proposed_action: str,
    confidence: float,
) -> dict[str, object]:
    """Check whether recommendation confidence is supported by grounded context.

    Returns a dict with:
        - ``valid``: True if confidence is supported or below threshold
        - ``warning``: Human-readable warning text if flagged, else None
        - ``kg_resolution_count``: Number of KG resolutions found for this pair
        - ``confidence_breakdown``: Composite confidence components
        - ``grounding_summary``: Human-readable grounding summary
    """

    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        proposed_action=proposed_action,
        confidence=confidence,
    )

    kg_count: int | None = None
    warning: str | None = None
    valid = True

    if confidence >= settings.CONFIDENCE_VALIDATOR_THRESHOLD:
        try:
            alert_entity_id = make_entity_id("alert_type", incident.alert_type)
            action_entity_id = make_entity_id("action", proposed_action)
            kg_count = await _count_resolutions(
                session,
                incident,
                alert_entity_id,
                action_entity_id,
            )
        except Exception as exc:
            log.warning("confidence_validator_kg_lookup_failed", error=str(exc))
            kg_count = None

        if kg_count is not None and kg_count >= settings.CONFIDENCE_VALIDATOR_MIN_KG_HISTORY:
            log.info(
                "confidence_validated_by_kg",
                kg_count=kg_count,
                confidence=confidence,
            )
        elif kg_count is not None:
            valid = False
            warning = (
                f"High confidence ({confidence:.0%}) but this action "
                f"({proposed_action!r}) has no recorded resolutions for "
                f"{incident.alert_type!r} in the Knowledge Graph. "
                f"Manual review recommended before approving."
            )
            log.warning(
                "confidence_validator_flagged_potential_hallucination",
                confidence=confidence,
                kg_count=kg_count,
                alert_type=incident.alert_type,
                proposed_action=proposed_action,
            )

    breakdown = _build_confidence_breakdown(
        incident=incident,
        model_confidence=confidence,
        kg_resolution_count=kg_count,
        warning=warning,
    )
    grounding_summary = _build_grounding_summary(
        incident=incident,
        kg_resolution_count=kg_count,
        warning=warning,
    )

    return {
        "valid": valid,
        "warning": warning,
        "kg_resolution_count": kg_count,
        "confidence_breakdown": breakdown.model_dump(),
        "grounding_summary": grounding_summary,
    }


def _build_confidence_breakdown(
    *,
    incident: Incident,
    model_confidence: float,
    kg_resolution_count: int | None,
    warning: str | None,
) -> ConfidenceBreakdown:
    evidence_strength_score = _score_evidence_strength(incident)
    tool_grounding_score = _score_tool_grounding(incident)
    kg_match_score = _score_kg_match(kg_resolution_count)
    hallucination_penalty = _score_hallucination_penalty(
        model_confidence=model_confidence,
        evidence_strength_score=evidence_strength_score,
        tool_grounding_score=tool_grounding_score,
        warning=warning,
    )
    composite_confidence = _clamp_score(
        (model_confidence * 0.5)
        + (evidence_strength_score * 0.2)
        + (tool_grounding_score * 0.2)
        + (kg_match_score * 0.1)
        - hallucination_penalty
    )
    return ConfidenceBreakdown(
        model_confidence=model_confidence,
        evidence_strength_score=evidence_strength_score,
        tool_grounding_score=tool_grounding_score,
        kg_match_score=kg_match_score,
        hallucination_penalty=hallucination_penalty,
        composite_confidence=composite_confidence,
        warning=warning or "",
    )


def _score_evidence_strength(incident: Incident) -> float:
    evidence_items = list(getattr(incident, "evidence", []) or [])
    evidence_count = sum(1 for item in evidence_items if getattr(item, "raw_output", ""))
    unique_tools = len(
        {
            str(getattr(item, "tool_name", "")).strip()
            for item in evidence_items
            if str(getattr(item, "tool_name", "")).strip()
        }
    )
    affected_entities = len(_investigation_meta(incident).get("affected_entities", []))
    return _clamp_score(
        0.15
        + min(0.4, evidence_count * 0.15)
        + min(0.25, unique_tools * 0.08)
        + min(0.2, affected_entities * 0.05)
    )


def _score_tool_grounding(incident: Incident) -> float:
    meta = _investigation_meta(incident)
    raw_refs = meta.get("raw_refs", {})
    forensic_tools = raw_refs.get("forensic_tools", [])
    if not isinstance(forensic_tools, list):
        forensic_tools = []
    snippet_count = sum(
        1
        for key, value in raw_refs.items()
        if key != "forensic_tools" and isinstance(value, str) and value.strip()
    )
    has_investigation_evidence = any(
        str(getattr(item, "tool_name", "")).strip() == "investigation"
        for item in (getattr(incident, "evidence", []) or [])
    )
    return _clamp_score(
        (0.35 if has_investigation_evidence or meta else 0.0)
        + min(0.4, len(forensic_tools) * 0.2)
        + min(0.25, snippet_count * 0.08)
    )


def _score_kg_match(kg_resolution_count: int | None) -> float:
    if kg_resolution_count is None or kg_resolution_count <= 0:
        return 0.0
    return _clamp_score(min(1.0, kg_resolution_count / 3.0))


def _score_hallucination_penalty(
    *,
    model_confidence: float,
    evidence_strength_score: float,
    tool_grounding_score: float,
    warning: str | None,
) -> float:
    penalty = 0.0
    if warning:
        penalty += 0.25
    if model_confidence >= settings.CONFIDENCE_VALIDATOR_THRESHOLD and tool_grounding_score < 0.3:
        penalty += 0.1
    if evidence_strength_score < 0.35:
        penalty += 0.05
    return _clamp_score(penalty)


def _build_grounding_summary(
    *,
    incident: Incident,
    kg_resolution_count: int | None,
    warning: str | None,
) -> str:
    evidence_items = list(getattr(incident, "evidence", []) or [])
    meta = _investigation_meta(incident)
    raw_refs = meta.get("raw_refs", {})
    forensic_tools = raw_refs.get("forensic_tools", [])
    if not isinstance(forensic_tools, list):
        forensic_tools = []

    parts = [f"{len(evidence_items)} evidence source(s) considered"]
    if forensic_tools:
        parts.append(f"{len(forensic_tools)} forensic tool(s) grounded")
    if kg_resolution_count is not None:
        parts.append(f"KG matched {kg_resolution_count} prior resolution(s)")
    if warning:
        parts.append("hallucination risk flagged")
    else:
        parts.append("grounding checks passed")
    return "; ".join(parts)


def _investigation_meta(incident: Incident) -> dict[str, Any]:
    meta = getattr(incident, "meta", None)
    if not isinstance(meta, dict):
        return {}
    inv_meta = meta.get("investigation")
    if not isinstance(inv_meta, dict):
        return {}
    return inv_meta


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


async def _count_resolutions(
    session: AsyncSession,
    incident: Incident,
    alert_entity_id: str,
    action_entity_id: str,
) -> int:
    """Query KG edge weight for the what_worked relationship."""
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            SELECT COALESCE(weight, 0)
            FROM kg_edges
            WHERE tenant_id = :tenant_id
              AND src_entity_id = :src
              AND relation = 'what_worked'
              AND dst_entity_id = :dst
            LIMIT 1
            """
        ),
        {
            "tenant_id": str(incident.tenant_id),
            "src": alert_entity_id,
            "dst": action_entity_id,
        },
    )
    row = result.fetchone()
    if row is None:
        return 0
    return int(row[0])


__all__ = ["validate_confidence"]
