"""Helpers for assembling RAG context for LLM prompts.

Returns both a text string for the LLM prompt and a structured dict
for storage in incident meta (consumed by the frontend).
"""

from __future__ import annotations

from typing import Any, Sequence

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
    """Retrieve semantic context for the LLM recommendation stage.

    Returns the text form for backward compatibility. Use
    build_structured_context() when you also need the structured dict.
    """
    result = await build_structured_context(session, incident, evidence_text)
    return result["text"] if result else None


async def build_structured_context(
    session: AsyncSession,
    incident: Incident,
    evidence_text: str,
) -> dict[str, Any] | None:
    """Retrieve semantic context as both text (for LLM) and structured dict (for meta).

    Returns:
        {
            "text": "... formatted text for LLM prompt ...",
            "runbooks": [ { "title", "source_type", "score", "snippet" } ],
            "similar_incidents": [ { "incident_id", "score", "snippet" } ],
            "pattern_analysis": { ... } | None,
            "runbook_count": int,
            "incident_count": int,
        }
        or None if no context found.
    """
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
    pattern_analysis: PatternAnalysis | None = None
    try:
        from app.services.pattern_analysis import analyze_patterns

        pattern_analysis = await analyze_patterns(session, incident, lookback_days=30)
    except Exception as exc:
        logger.warning("pattern_analysis_failed", error=str(exc))

    text = format_context_sections(runbooks, incidents, pattern_analysis)
    if text is None and not runbooks and not incidents:
        return None

    # Build structured representation for frontend/meta
    structured_runbooks = _structure_runbooks(runbooks)
    structured_incidents = _structure_incidents(incidents)
    structured_patterns = None
    if pattern_analysis:
        structured_patterns = {
            "historical_context": pattern_analysis.historical_context or "",
            "recurrence_count": getattr(pattern_analysis, "recurrence_count", 0),
            "avg_resolution_time_minutes": getattr(
                pattern_analysis, "avg_resolution_time_minutes", 0
            ),
            "most_effective_action": getattr(
                pattern_analysis, "most_effective_action", ""
            ),
        }

    return {
        "text": text or "",
        "runbooks": structured_runbooks,
        "similar_incidents": structured_incidents,
        "pattern_analysis": structured_patterns,
        "runbook_count": len(structured_runbooks),
        "incident_count": len(structured_incidents),
    }


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


def _structure_runbooks(matches: Sequence[RunbookMatch]) -> list[dict[str, Any]]:
    """Convert runbook matches to structured dicts for frontend."""
    result = []
    for match in matches:
        title = match.metadata.get("title") if match.metadata else None
        title = title or match.source_type.replace("_", " ").title()
        result.append(
            {
                "title": title,
                "source_type": match.source_type,
                "chunk_index": match.chunk_index,
                "score": round(match.score, 3),
                "snippet": _trim(match.content, settings.RAG_SNIPPET_MAX_CHARS),
            }
        )
    return result


def _structure_incidents(matches: Sequence[IncidentMatch]) -> list[dict[str, Any]]:
    """Convert incident matches to structured dicts for frontend."""
    return [
        {
            "incident_id": str(match.incident_id),
            "score": round(match.score, 3),
            "snippet": _trim(match.summary, settings.RAG_SNIPPET_MAX_CHARS),
        }
        for match in matches
    ]


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …"


__all__ = [
    "build_recommendation_context",
    "build_structured_context",
    "format_context_sections",
]
