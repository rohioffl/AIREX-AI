"""
Auto-generate runbooks from resolved incidents (Phase 5 ARE).

When an incident is resolved successfully, this service:
1. Extracts the incident context (alert type, evidence, recommendation, actions)
2. Calls the LLM to synthesize a structured runbook
3. Chunks and embeds the runbook into the RAG vector store

Generated runbooks are stored as RunbookChunk entries with
source_type="auto_generated", making them automatically available
in future RAG similarity searches.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, cast

import structlog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.llm.embeddings import EmbeddingsClient
from app.models.enums import IncidentState
from app.models.incident import Incident
from app.models.runbook_chunk import RunbookChunk
from app.rag.chunker import chunk_text

logger = structlog.get_logger()

RUNBOOK_PROMPT_TEMPLATE = """You are an expert SRE writing an internal runbook based on a real resolved incident.

Generate a structured runbook in Markdown format based on the following incident data.

## Incident Context
- Alert Type: {alert_type}
- Severity: {severity}
- Title: {title}
- Resolution Type: {resolution_type}
- Duration: {duration}

## Root Cause
{root_cause}

## Action Taken
{action_taken}

## Evidence Summary
{evidence_summary}

## Verification
{verification}

---

Write the runbook with these sections:
1. **Title** — clear, actionable title for this runbook
2. **Symptoms** — what alerts/symptoms indicate this issue
3. **Root Cause** — detailed explanation of what causes this
4. **Resolution Steps** — numbered step-by-step resolution procedure
5. **Verification** — how to verify the fix worked
6. **Prevention** — recommendations to prevent recurrence
7. **Related Alert Types** — other alert types that may co-occur

Output ONLY the markdown runbook content, no preamble or explanation.
"""


def build_runbook_context(incident: Incident) -> dict[str, str]:
    """Extract context from a resolved incident for runbook generation."""
    meta = incident.meta or {}
    recommendation = meta.get("recommendation", {})

    # Evidence summary
    evidence_lines = []
    if hasattr(incident, "evidence") and incident.evidence:
        for e in incident.evidence[:5]:  # Cap at 5 evidence items
            snippet = (e.raw_output or "")[:300]
            evidence_lines.append(f"[{e.tool_name}] {snippet}")
    evidence_summary = (
        "\n".join(evidence_lines) if evidence_lines else "No evidence recorded"
    )

    # Verification criteria
    verification_criteria = recommendation.get("verification_criteria", [])
    verification = (
        "\n".join(f"- {c}" for c in verification_criteria)
        if verification_criteria
        else "Standard post-action verification"
    )

    # Duration
    duration = "Unknown"
    if incident.resolution_duration_seconds is not None:
        secs = int(incident.resolution_duration_seconds)
        if secs < 60:
            duration = f"{secs} seconds"
        elif secs < 3600:
            duration = f"{secs // 60} minutes"
        else:
            duration = f"{secs // 3600}h {(secs % 3600) // 60}m"

    return {
        "alert_type": incident.alert_type,
        "severity": incident.severity.value,
        "title": incident.title,
        "resolution_type": incident.resolution_type or "unknown",
        "duration": duration,
        "root_cause": recommendation.get("root_cause", "Not determined"),
        "action_taken": recommendation.get("proposed_action", "Manual resolution"),
        "evidence_summary": evidence_summary,
        "verification": verification,
    }


async def generate_runbook_content(
    context: dict[str, str],
    redis: Any = None,
) -> str | None:
    """
    Call LLM to generate runbook markdown from incident context.

    Returns the markdown string, or None if LLM is unavailable.
    """
    log = logger.bind(alert_type=context.get("alert_type", "unknown"))

    prompt = RUNBOOK_PROMPT_TEMPLATE.format(**context)
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert SRE technical writer. Generate clear, "
                "actionable runbooks based on real incident data. "
                "Use markdown formatting. Be specific and practical."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        import litellm
        from app.llm import build_llm_headers, configure_litellm

        configure_litellm()

        effective_model = settings.LLM_PRIMARY_MODEL
        call_kwargs: dict[str, Any] = {
            "model": effective_model,
            "messages": messages,
            "temperature": 0.2,
        }

        if settings.LLM_BASE_URL:
            if not effective_model.startswith("openai/"):
                effective_model = f"openai/{effective_model}"
            call_kwargs["model"] = effective_model
            call_kwargs["api_base"] = settings.LLM_BASE_URL
        if settings.LLM_API_KEY:
            call_kwargs["api_key"] = settings.LLM_API_KEY

        headers = build_llm_headers()
        if headers:
            call_kwargs["extra_headers"] = headers

        if (
            settings.LLM_PRIMARY_MODEL.startswith("vertex_ai/")
            and not settings.LLM_BASE_URL
        ):
            call_kwargs["vertex_project"] = settings.VERTEX_PROJECT
            call_kwargs["vertex_location"] = settings.VERTEX_LOCATION

        raw_response = await asyncio.wait_for(
            litellm.acompletion(**call_kwargs),
            timeout=settings.LLM_FALLBACK_TIMEOUT,
        )
        response = cast(dict[str, Any], raw_response)
        content = cast(str, response["choices"][0]["message"]["content"])

        log.info("runbook_content_generated", length=len(content))
        return content

    except asyncio.TimeoutError:
        log.warning("runbook_generation_timeout")
        return None
    except Exception as exc:
        log.warning("runbook_generation_failed", error=str(exc))
        return None


async def store_runbook(
    session: AsyncSession,
    incident: Incident,
    content: str,
) -> uuid.UUID:
    """
    Chunk, embed, and store a generated runbook in the vector store.

    Returns the source_id for the stored runbook.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        correlation_id=str(incident.id),
    )

    # Deterministic source_id: same incident always produces same source
    source_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"auto_runbook:{incident.tenant_id}:{incident.id}",
    )

    # Delete any previous auto-generated runbook for this incident
    await session.execute(
        delete(RunbookChunk).where(
            RunbookChunk.tenant_id == incident.tenant_id,
            RunbookChunk.source_id == source_id,
        )
    )

    chunks = chunk_text(content)
    if not chunks:
        log.warning("runbook_empty_after_chunking")
        return source_id

    # Embed chunks
    embeddings_client = EmbeddingsClient()
    try:
        vectors = await embeddings_client.embed_texts(chunks)
    except RuntimeError as exc:
        log.error("runbook_embedding_failed", error=str(exc))
        raise

    # Store chunks
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        session.add(
            RunbookChunk(
                tenant_id=incident.tenant_id,
                source_type="auto_generated",
                source_id=source_id,
                chunk_index=idx,
                content=chunk,
                meta={
                    "title": f"Auto-Runbook: {incident.alert_type}",
                    "incident_id": str(incident.id),
                    "alert_type": incident.alert_type,
                    "resolution_type": incident.resolution_type or "unknown",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                embedding=vector,
            )
        )

    log.info(
        "runbook_stored",
        source_id=str(source_id),
        chunks=len(chunks),
    )

    return source_id


async def generate_and_store_runbook(
    session: AsyncSession,
    incident: Incident,
    redis: Any = None,
) -> uuid.UUID | None:
    """
    End-to-end: build context → generate via LLM → chunk → embed → store.

    Only generates for RESOLVED incidents (not REJECTED).
    Returns the source_id if successful, None if skipped/failed.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        correlation_id=str(incident.id),
        alert_type=incident.alert_type,
    )

    # Only generate for successfully resolved incidents
    if incident.state != IncidentState.RESOLVED:
        log.debug("runbook_skipped_not_resolved", state=incident.state.value)
        return None

    # Skip if no recommendation (manual resolution without AI)
    meta = incident.meta or {}
    if "recommendation" not in meta:
        log.debug("runbook_skipped_no_recommendation")
        return None

    # Build context and generate
    context = build_runbook_context(incident)
    content = await generate_runbook_content(context, redis=redis)

    if content is None:
        log.warning("runbook_generation_returned_none")
        return None

    # Store the generated runbook
    source_id = await store_runbook(session, incident, content)

    # Record in incident meta that a runbook was generated
    meta = dict(incident.meta or {})
    meta["_auto_runbook_source_id"] = str(source_id)
    meta["_auto_runbook_generated_at"] = datetime.now(timezone.utc).isoformat()
    incident.meta = meta
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(incident, "meta")

    return source_id
