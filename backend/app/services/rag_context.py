"""Helpers for assembling RAG context strings for LLM prompts."""

from __future__ import annotations

from typing import Sequence

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from typing import TYPE_CHECKING

from app.core.config import settings
from app.models.incident import Incident
from app.rag.vector_store import IncidentMatch, RunbookMatch, VectorStore

if TYPE_CHECKING:
    from app.services.pattern_analysis import PatternAnalysis

logger = structlog.get_logger()

_vector_store = VectorStore()


async def build_recommendation_context(
    session: AsyncSession,
    incident: Incident,
    evidence_text: str,
) -> str | None:
    """Retrieve semantic context for the LLM recommendation stage."""

    query_seed = _build_query_seed(incident, evidence_text)
    runbooks = await _vector_store.search_runbook_chunks(
        session=session,
        tenant_id=incident.tenant_id,
        query=query_seed,
        limit=settings.RAG_RUNBOOK_LIMIT,
    )

    incidents = await _vector_store.search_incident_history(
        session=session,
        tenant_id=incident.tenant_id,
        query=query_seed,
        limit=settings.RAG_INCIDENT_LIMIT,
    )

    # Add pattern analysis for human-like insights
    try:
        from app.services.pattern_analysis import analyze_patterns
        pattern_analysis = await analyze_patterns(session, incident, lookback_days=30)
    except Exception as exc:
        logger.warning("pattern_analysis_failed", error=str(exc))
        pattern_analysis = None

    return format_context_sections(runbooks, incidents, pattern_analysis)


def format_context_sections(
    runbooks: Sequence[RunbookMatch],
    incidents: Sequence[IncidentMatch],
    pattern_analysis: PatternAnalysis | None = None,
) -> str | None:
    """Convert matches into a bounded text block for prompts."""

    sections: list[str] = []

    # Pattern analysis first (most important for human-like analysis)
    if pattern_analysis and pattern_analysis.historical_context:
        sections.append(pattern_analysis.historical_context)

    if runbooks:
        sections.append(_format_runbook_section(runbooks))
    if incidents:
        sections.append(_format_incident_section(incidents))

    if not sections:
        return None

    combined = "\n\n".join(sections)
    max_chars = settings.RAG_CONTEXT_MAX_CHARS
    if len(combined) <= max_chars:
        return combined
    return combined[:max_chars].rstrip() + " …"


def _build_query_seed(incident: Incident, evidence_text: str) -> str:
    snippet = evidence_text[: settings.RAG_QUERY_MAX_CHARS]
    return (
        f"Title: {incident.title}\n"
        f"Alert: {incident.alert_type}\n"
        f"Severity: {incident.severity.value}\n\n"
        f"Evidence Snapshot:\n{snippet}"
    )


def _format_runbook_section(matches: Sequence[RunbookMatch]) -> str:
    lines: list[str] = ["Relevant Runbooks:"]
    for match in matches:
        title = match.metadata.get("title") if match.metadata else None
        title = title or match.source_type.replace("_", " ").title()
        snippet = _trim(match.content, settings.RAG_SNIPPET_MAX_CHARS)
        lines.append(
            f"- {title} (score={match.score:.2f}, chunk={match.chunk_index})\n"
            f"  {snippet}"
        )
    return "\n".join(lines)


def _format_incident_section(matches: Sequence[IncidentMatch]) -> str:
    lines: list[str] = ["Similar Incidents:"]
    for match in matches:
        snippet = _trim(match.summary, settings.RAG_SNIPPET_MAX_CHARS)
        lines.append(
            f"- Incident {match.incident_id} (score={match.score:.2f})\n  {snippet}"
        )
    return "\n".join(lines)


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …"


__all__ = ["build_recommendation_context", "format_context_sections"]
