"""Persist semantic summaries for completed incidents."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.llm.embeddings import EmbeddingsClient
from app.models.incident import Incident
from app.models.incident_embedding import IncidentEmbedding

logger = structlog.get_logger()

_embeddings_client = EmbeddingsClient()


async def upsert_incident_embedding(
    session: AsyncSession,
    incident: Incident,
) -> None:
    """Store or refresh the vector summary for a terminal incident."""

    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        correlation_id=str(incident.id),
    )

    summary = build_incident_summary(incident)
    if not summary:
        return

    try:
        vector = await _embeddings_client.embed_text(summary)
    except RuntimeError as exc:  # pragma: no cover - network errors
        log.warning(
            "incident_embedding_failed",
            error=str(exc),
        )
        return

    expected_dim = settings.LLM_EMBEDDING_DIMENSION
    if expected_dim and len(vector) != expected_dim:
        log.warning(
            "incident_embedding_dim_mismatch",
            expected_dim=expected_dim,
            actual_dim=len(vector),
        )
        return

    existing = await session.execute(
        select(IncidentEmbedding).where(
            IncidentEmbedding.tenant_id == incident.tenant_id,
            IncidentEmbedding.incident_id == incident.id,
        )
    )
    record = existing.scalar_one_or_none()

    if record:
        record.summary = summary
        record.embedding = vector
        session.add(record)
    else:
        session.add(
            IncidentEmbedding(
                tenant_id=incident.tenant_id,
                incident_id=incident.id,
                summary=summary,
                embedding=vector,
            )
        )

    log.info(
        "incident_embedding_upserted",
    )


def build_incident_summary(incident: Incident) -> str:
    """Create a deterministic text summary for vector storage."""

    severity_value = getattr(incident.severity, "value", incident.severity)
    state_value = getattr(incident.state, "value", incident.state)

    lines: list[str] = [
        f"Title: {incident.title}",
        f"Alert Type: {incident.alert_type}",
        f"Severity: {severity_value}",
        f"Final State: {state_value}",
    ]

    meta = incident.meta or {}
    recommendation = meta.get("recommendation", {})
    if recommendation:
        root_cause = recommendation.get("root_cause")
        proposed_action = recommendation.get("proposed_action")
        risk_level = recommendation.get("risk_level")
        confidence = recommendation.get("confidence")
        lines.append("Recommendation:")
        if root_cause:
            lines.append(f"- Root Cause: {root_cause}")
        if proposed_action:
            lines.append(f"- Action: {proposed_action}")
        if risk_level:
            lines.append(f"- Risk Level: {risk_level}")
        if confidence is not None:
            lines.append(f"- Confidence: {confidence}")

    if note := meta.get("recommendation_note"):
        lines.append(f"Recommendation Note: {note}")

    if rag_context := meta.get("rag_context"):
        lines.append("Context Used:")
        lines.append(rag_context)

    summary = "\n".join(lines).strip()
    limit = settings.RAG_INCIDENT_SUMMARY_MAX_CHARS
    if len(summary) > limit:
        summary = summary[:limit].rstrip() + " …"
    return summary


__all__ = ["upsert_incident_embedding", "build_incident_summary"]
