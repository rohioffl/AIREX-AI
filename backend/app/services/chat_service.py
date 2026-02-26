"""
Incident AI Chat service (Phase 7).

Manages conversation history in Redis (TTL 24h) and delegates
to the LLM client for response generation.
"""

import json
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient
from app.models.incident import Incident

logger = structlog.get_logger()

# Redis key prefix and TTL for chat history
CHAT_KEY_PREFIX = "airex:chat:"
CHAT_TTL_SECONDS = 86400  # 24 hours
MAX_HISTORY_MESSAGES = 40  # Keep last 40 messages (20 exchanges)

llm_client = LLMClient()


def _chat_key(tenant_id: str, incident_id: str) -> str:
    """Build the Redis key for a chat session."""
    return f"{CHAT_KEY_PREFIX}{tenant_id}:{incident_id}"


def _build_incident_context(incident: Incident) -> str:
    """Format incident data into a text context block for the LLM.

    Includes: basic info, evidence, recommendation, state history,
    anomalies, and probe results from meta.
    """
    parts: list[str] = []

    # Basic incident info
    parts.append(
        f"Incident ID: {incident.id}\n"
        f"Alert Type: {incident.alert_type}\n"
        f"Severity: {incident.severity.value}\n"
        f"Current State: {incident.state.value}\n"
        f"Title: {incident.title}\n"
        f"Host: {incident.host_key or 'unknown'}\n"
        f"Created: {incident.created_at}"
    )

    # Evidence from investigation probes
    if incident.evidence:
        parts.append("--- Investigation Evidence ---")
        for ev in incident.evidence:
            parts.append(f"[{ev.tool_name}]\n{ev.raw_output}")
        parts.append("--- End Evidence ---")

    # AI recommendation (if generated)
    meta = incident.meta or {}
    if "recommendation" in meta:
        rec = meta["recommendation"]
        rec_text = (
            f"Root Cause: {rec.get('root_cause', 'N/A')}\n"
            f"Proposed Action: {rec.get('proposed_action', 'N/A')}\n"
            f"Risk Level: {rec.get('risk_level', 'N/A')}\n"
            f"Confidence: {rec.get('confidence', 'N/A')}"
        )
        if rec.get("summary"):
            rec_text += f"\nSummary: {rec['summary']}"
        if rec.get("rationale"):
            rec_text += f"\nRationale: {rec['rationale']}"
        if rec.get("blast_radius"):
            rec_text += f"\nBlast Radius: {rec['blast_radius']}"
        if rec.get("contributing_factors"):
            rec_text += (
                f"\nContributing Factors: {', '.join(rec['contributing_factors'])}"
            )
        if rec.get("reasoning_chain"):
            chain_lines = []
            for step in rec["reasoning_chain"]:
                if isinstance(step, dict):
                    chain_lines.append(
                        f"  Step {step.get('step', '?')}: "
                        f"{step.get('description', '')} "
                        f"(evidence: {step.get('evidence_used', '')})"
                    )
            if chain_lines:
                rec_text += "\nReasoning Chain:\n" + "\n".join(chain_lines)
        if rec.get("alternatives"):
            alt_lines = []
            for alt in rec["alternatives"]:
                if isinstance(alt, dict):
                    alt_lines.append(
                        f"  - {alt.get('action', '?')}: "
                        f"{alt.get('rationale', '')} "
                        f"(confidence: {alt.get('confidence', '?')}, "
                        f"risk: {alt.get('risk_level', '?')})"
                    )
            if alt_lines:
                rec_text += "\nAlternatives:\n" + "\n".join(alt_lines)
        if rec.get("verification_criteria"):
            rec_text += "\nVerification Criteria:\n" + "\n".join(
                f"  - {c}" for c in rec["verification_criteria"]
            )

        parts.append(
            f"--- AI Recommendation ---\n{rec_text}\n--- End Recommendation ---"
        )

    # RAG context (structured)
    if "rag_structured" in meta:
        rag = meta["rag_structured"]
        rag_lines = []
        if rag.get("runbooks"):
            rag_lines.append(
                f"Matching Runbooks: {rag.get('runbook_count', len(rag['runbooks']))}"
            )
            for rb in rag["runbooks"][:5]:
                if isinstance(rb, dict):
                    rag_lines.append(f"  - {rb.get('title', 'Untitled')}")
        if rag.get("similar_incidents"):
            rag_lines.append(
                f"Similar Past Incidents: {rag.get('incident_count', len(rag['similar_incidents']))}"
            )
        if rag.get("pattern_analysis"):
            rag_lines.append(f"Pattern Analysis: {rag['pattern_analysis']}")
        if rag_lines:
            parts.append(
                "--- Historical Context ---\n"
                + "\n".join(rag_lines)
                + "\n--- End Historical Context ---"
            )

    # State transitions
    if incident.state_transitions:
        transition_lines = []
        for t in incident.state_transitions:
            transition_lines.append(
                f"  {t.from_state.value} -> {t.to_state.value}: "
                f"{t.reason or 'no reason'} (by {t.actor})"
            )
        parts.append(
            "--- State Transitions ---\n"
            + "\n".join(transition_lines)
            + "\n--- End State Transitions ---"
        )

    # Execution results
    if incident.executions:
        exec_lines = []
        for ex in incident.executions:
            exec_lines.append(
                f"  [{ex.action_type}] attempt={ex.attempt} "
                f"status={ex.status.value} duration={ex.duration_seconds}s"
            )
            if ex.logs:
                # Truncate long logs
                log_preview = ex.logs[:500]
                exec_lines.append(f"    logs: {log_preview}")
        parts.append(
            "--- Execution Results ---\n"
            + "\n".join(exec_lines)
            + "\n--- End Execution Results ---"
        )

    # Probe anomalies from meta
    if meta.get("anomalies"):
        anomaly_lines = []
        for a in meta["anomalies"]:
            if isinstance(a, dict):
                anomaly_lines.append(
                    f"  [{a.get('severity', '?')}] {a.get('metric', '?')}: "
                    f"{a.get('description', '')}"
                )
        if anomaly_lines:
            parts.append(
                "--- Detected Anomalies ---\n"
                + "\n".join(anomaly_lines)
                + "\n--- End Anomalies ---"
            )

    return "\n\n".join(parts)


async def get_conversation_history(
    redis,
    tenant_id: str,
    incident_id: str,
) -> list[dict[str, str]]:
    """Load conversation history from Redis.

    Returns list of {role, content} dicts.
    """
    key = _chat_key(tenant_id, incident_id)
    try:
        raw = await redis.get(key)
        if raw:
            messages = json.loads(raw)
            if isinstance(messages, list):
                return messages
    except Exception as exc:
        logger.warning(
            "chat_history_load_failed",
            key=key,
            error=str(exc),
        )
    return []


async def save_conversation_history(
    redis,
    tenant_id: str,
    incident_id: str,
    messages: list[dict[str, str]],
) -> None:
    """Save conversation history to Redis with TTL.

    Trims to MAX_HISTORY_MESSAGES to prevent unbounded growth.
    """
    key = _chat_key(tenant_id, incident_id)
    # Keep only the most recent messages
    trimmed = messages[-MAX_HISTORY_MESSAGES:]
    try:
        await redis.set(key, json.dumps(trimmed), ex=CHAT_TTL_SECONDS)
    except Exception as exc:
        logger.warning(
            "chat_history_save_failed",
            key=key,
            error=str(exc),
        )


async def chat_with_incident(
    session: AsyncSession,
    incident_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_message: str,
    redis,
) -> tuple[str, int]:
    """Process a chat message for an incident.

    Args:
        session: Async DB session.
        incident_id: The incident being discussed.
        tenant_id: Tenant owning the incident.
        user_message: Operator's question.
        redis: Redis connection for history and circuit breaker.

    Returns:
        Tuple of (ai_reply, conversation_length).

    Raises:
        ValueError: If incident not found.
        RuntimeError: If LLM fails to generate a response.
    """
    log = logger.bind(
        tenant_id=str(tenant_id),
        incident_id=str(incident_id),
    )

    # Fetch incident with relationships
    result = await session.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.id == incident_id,
        )
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    # Build context from incident data
    incident_context = _build_incident_context(incident)

    # Load existing conversation
    tid = str(tenant_id)
    iid = str(incident_id)
    history = await get_conversation_history(redis, tid, iid)

    log.info(
        "chat_request",
        message_length=len(user_message),
        history_length=len(history),
    )

    # Call LLM
    ai_reply = await llm_client.chat(
        incident_context=incident_context,
        conversation_history=history,
        user_message=user_message,
        redis=redis,
    )

    if ai_reply is None:
        log.warning("chat_llm_failed")
        raise RuntimeError(
            "AI assistant is temporarily unavailable. Please try again shortly."
        )

    # Append this exchange to history
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": ai_reply})

    # Persist updated history
    await save_conversation_history(redis, tid, iid, history)

    log.info(
        "chat_response",
        reply_length=len(ai_reply),
        conversation_length=len(history),
    )

    return ai_reply, len(history)
