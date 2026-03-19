"""Confidence validator — Phase 6 Operational Polish.

Cross-checks LLM recommendation confidence against Knowledge Graph history.
If confidence is high but KG has no prior resolutions for this alert/action pair,
flags it as a potential hallucination so operators are warned before approval.
"""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.config import settings
from airex_core.core.knowledge_graph import knowledge_graph, make_entity_id
from airex_core.models.incident import Incident

logger = structlog.get_logger()


async def validate_confidence(
    session: AsyncSession,
    incident: Incident,
    proposed_action: str,
    confidence: float,
) -> dict[str, object]:
    """Check whether high LLM confidence is supported by KG history.

    Returns a dict with:
        - ``valid``: True if confidence is supported or below threshold
        - ``warning``: Human-readable warning text if flagged, else None
        - ``kg_resolution_count``: Number of KG resolutions found for this pair
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        proposed_action=proposed_action,
        confidence=confidence,
    )

    if confidence < settings.CONFIDENCE_VALIDATOR_THRESHOLD:
        # Below threshold — no KG check needed
        return {"valid": True, "warning": None, "kg_resolution_count": None}

    # Query KG for how many times this action resolved this alert type
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
        # Cannot validate — treat as valid to avoid false positives
        return {"valid": True, "warning": None, "kg_resolution_count": None}

    if kg_count >= settings.CONFIDENCE_VALIDATOR_MIN_KG_HISTORY:
        log.info(
            "confidence_validated_by_kg",
            kg_count=kg_count,
            confidence=confidence,
        )
        return {"valid": True, "warning": None, "kg_resolution_count": kg_count}

    # High confidence but no KG support — potential hallucination
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
    return {"valid": False, "warning": warning, "kg_resolution_count": kg_count}


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
