"""
Post-mortem automation service.

Auto-generates post-mortem documents from resolved incidents with timeline
and root cause analysis.
"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident
from airex_core.models.knowledge_base import KnowledgeBase
from airex_core.llm.client import LLMClient

logger = structlog.get_logger()
llm_client = LLMClient()


POSTMORTEM_TEMPLATE = """Generate a comprehensive post-mortem document for the following resolved incident.

## Incident Summary
- Title: {title}
- Alert Type: {alert_type}
- Severity: {severity}
- Created: {created_at}
- Resolved: {resolved_at}
- Duration: {duration}
- Resolution Type: {resolution_type}

## Timeline
{timeline}

## Root Cause Analysis
{root_cause}

## Action Taken
{action_taken}

## Evidence Collected
{evidence_summary}

## Impact
{impact}

## Lessons Learned
{lessons_learned}

## Prevention Measures
{prevention}

---

Generate a structured post-mortem document with the following sections:
1. **Executive Summary** - Brief overview of the incident
2. **Timeline** - Detailed chronological sequence of events
3. **Root Cause** - Deep analysis of what caused the incident
4. **Resolution** - What was done to fix it
5. **Impact** - Business/technical impact assessment
6. **Contributing Factors** - What made this incident possible
7. **Action Items** - Concrete steps to prevent recurrence
8. **Lessons Learned** - Key takeaways for the team

Output ONLY the markdown post-mortem document, no preamble.
"""


async def generate_postmortem(
    session: AsyncSession,
    incident: Incident,
    redis: Any = None,
) -> str | None:
    """
    Generate a post-mortem document from a resolved incident.

    Returns markdown-formatted post-mortem or None if generation fails.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
    )

    if incident.state != IncidentState.RESOLVED:
        log.warning("postmortem_generation_skipped", reason="incident_not_resolved")
        return None

    if not incident.resolved_at:
        log.warning("postmortem_generation_skipped", reason="no_resolution_timestamp")
        return None

    # Build timeline from state transitions
    timeline_parts = []
    if hasattr(incident, "state_transitions") and incident.state_transitions:
        for trans in sorted(incident.state_transitions, key=lambda t: t.created_at):
            timeline_parts.append(
                f"- **{trans.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}**: "
                f"{trans.from_state.value} → {trans.to_state.value} "
                f"({trans.reason}) - {trans.actor}"
            )
    else:
        timeline_parts.append(f"- **{incident.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}**: Incident created")
        if incident.resolved_at:
            timeline_parts.append(f"- **{incident.resolved_at.strftime('%Y-%m-%d %H:%M:%S UTC')}**: Incident resolved")

    timeline = "\n".join(timeline_parts) if timeline_parts else "No timeline data available"

    # Extract root cause and action
    meta = incident.meta or {}
    recommendation = meta.get("recommendation", {})
    root_cause = recommendation.get("root_cause") or incident.resolution_summary or "Not determined"
    action_taken = recommendation.get("proposed_action") or "Manual resolution"
    
    # Evidence summary
    evidence_lines = []
    if hasattr(incident, "evidence") and incident.evidence:
        for e in incident.evidence[:10]:  # Cap at 10
            snippet = (e.raw_output or "")[:200]
            evidence_lines.append(f"- [{e.tool_name}] {snippet}")
    evidence_summary = "\n".join(evidence_lines) if evidence_lines else "No evidence collected"

    # Duration
    duration = "Unknown"
    if incident.resolution_duration_seconds:
        secs = int(incident.resolution_duration_seconds)
        if secs < 60:
            duration = f"{secs} seconds"
        elif secs < 3600:
            duration = f"{secs // 60} minutes"
        else:
            hours = secs // 3600
            mins = (secs % 3600) // 60
            duration = f"{hours}h {mins}m"

    # Impact assessment
    impact = f"Severity: {incident.severity.value}"
    if incident.resolution_duration_seconds:
        impact += f"\nDuration: {duration}"
    if incident.host_key:
        impact += f"\nAffected Host: {incident.host_key}"

    # Lessons learned and prevention from feedback
    lessons_learned = ""
    prevention = ""
    if incident.feedback_note:
        lessons_learned = incident.feedback_note
    if recommendation.get("prevention_suggestions"):
        prevention = "\n".join(f"- {s}" for s in recommendation.get("prevention_suggestions", []))

    # Generate post-mortem via LLM
    try:
        prompt = POSTMORTEM_TEMPLATE.format(
            title=incident.title,
            alert_type=incident.alert_type,
            severity=incident.severity.value,
            created_at=incident.created_at.isoformat(),
            resolved_at=incident.resolved_at.isoformat() if incident.resolved_at else "Unknown",
            duration=duration,
            resolution_type=incident.resolution_type or "unknown",
            timeline=timeline,
            root_cause=root_cause,
            action_taken=action_taken,
            evidence_summary=evidence_summary,
            impact=impact,
            lessons_learned=lessons_learned or "To be documented",
            prevention=prevention or "To be determined",
        )

        postmortem_content = await llm_client.generate_text(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.3,
            redis=redis,
        )

        if postmortem_content:
            log.info("postmortem_generated", incident_id=str(incident.id))
            return postmortem_content
        else:
            log.warning("postmortem_generation_failed", reason="llm_no_response")
            return None

    except Exception as exc:
        log.error("postmortem_generation_error", error=str(exc), exc_info=True)
        return None


async def auto_create_knowledge_base_entry(
    session: AsyncSession,
    incident: Incident,
    postmortem_content: str | None = None,
) -> KnowledgeBase | None:
    """
    Automatically create a knowledge base entry from a resolved incident.

    Optionally includes post-mortem content if provided.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
    )

    if incident.state != IncidentState.RESOLVED:
        return None

    # Check if entry already exists
    result = await session.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == incident.tenant_id,
            KnowledgeBase.incident_id == incident.id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        log.debug("knowledge_base_entry_exists", entry_id=str(existing.id))
        return existing

    meta = incident.meta or {}
    recommendation = meta.get("recommendation", {})

    # Build summary
    summary_parts = [
        f"Incident: {incident.title}",
        f"Alert Type: {incident.alert_type}",
        f"Severity: {incident.severity.value}",
    ]
    if recommendation.get("root_cause"):
        summary_parts.append(f"Root Cause: {recommendation['root_cause']}")
    if recommendation.get("proposed_action"):
        summary_parts.append(f"Resolution: {recommendation['proposed_action']}")
    if incident.resolution_summary:
        summary_parts.append(f"Summary: {incident.resolution_summary}")

    summary = "\n".join(summary_parts)

    # Extract resolution steps from post-mortem or recommendation
    resolution_steps = None
    if postmortem_content:
        # Try to extract action items from post-mortem
        lines = postmortem_content.split("\n")
        in_action_items = False
        action_items = []
        for line in lines:
            if "Action Items" in line or "Prevention Measures" in line:
                in_action_items = True
                continue
            if in_action_items and line.strip().startswith("-"):
                action_items.append(line.strip())
            elif in_action_items and line.strip() and not line.startswith("#"):
                break
        if action_items:
            resolution_steps = "\n".join(action_items)
    elif recommendation.get("verification_criteria"):
        resolution_steps = "\n".join(f"- {c}" for c in recommendation["verification_criteria"])

    # Create knowledge base entry
    entry = KnowledgeBase(
        tenant_id=incident.tenant_id,
        incident_id=incident.id,
        title=f"Resolved: {incident.title}",
        summary=summary,
        root_cause=recommendation.get("root_cause"),
        resolution_steps=resolution_steps,
        alert_type=incident.alert_type,
        category="auto-generated",
        tags=["auto-generated", incident.alert_type],
    )

    session.add(entry)
    await session.flush()
    await session.refresh(entry)

    log.info("knowledge_base_entry_auto_created", entry_id=str(entry.id))

    return entry
