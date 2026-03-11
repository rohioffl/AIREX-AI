"""
Resolution outcome tracking service.

Populates resolution metadata when an incident reaches a terminal state
(RESOLVED or REJECTED). Computes duration, determines resolution type,
and stores a structured summary for analytics and learning.
"""

from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident

logger = structlog.get_logger()


class ResolutionType:
    """Resolution type constants."""

    AUTO = "auto"  # Fully autonomous: auto-approved + executed + verified
    OPERATOR = "operator"  # Operator-approved execution
    SENIOR = "senior"  # Senior/admin-approved execution
    REJECTED = "rejected"  # Operator rejected the incident
    FAILED = "failed"  # Reached terminal failure state
    MANUAL = "manual"  # Manual intervention outside automation


def determine_resolution_type(incident: Incident) -> str:
    """Determine how the incident was resolved based on meta and state."""
    meta = incident.meta or {}

    if incident.state == IncidentState.REJECTED:
        return ResolutionType.REJECTED

    if incident.state in (
        IncidentState.FAILED_EXECUTION,
        IncidentState.FAILED_VERIFICATION,
    ):
        return ResolutionType.FAILED

    # Check approval level from Phase 1 meta
    approval_level = meta.get("_approval_level", "operator")

    if approval_level == "auto":
        return ResolutionType.AUTO
    elif approval_level == "senior":
        return ResolutionType.SENIOR
    else:
        return ResolutionType.OPERATOR


def compute_resolution_duration(incident: Incident) -> float | None:
    """Compute total seconds from created_at to now (terminal state)."""
    if incident.created_at is None:
        return None
    now = datetime.now(timezone.utc)
    created = incident.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = now - created
    return round(delta.total_seconds(), 2)


def build_resolution_summary(incident: Incident) -> str:
    """Build a concise resolution summary from incident data."""
    meta = incident.meta or {}
    parts: list[str] = []

    # State outcome
    parts.append(f"Outcome: {incident.state.value}")

    # Action taken
    rec = meta.get("recommendation", {})
    if isinstance(rec, dict) and rec.get("proposed_action"):
        parts.append(f"Action: {rec['proposed_action']}")
        if rec.get("root_cause"):
            parts.append(f"Root cause: {rec['root_cause']}")

    # Approval info
    approval_level = meta.get("_approval_level")
    if approval_level:
        parts.append(f"Approval: {approval_level}")

    # Rejection note
    if incident.state == IncidentState.REJECTED:
        reason = meta.get("_manual_review_reason", "")
        if reason:
            parts.append(f"Rejection reason: {reason}")

    # Retry info
    retries = []
    investigation_retries = incident.investigation_retry_count or 0
    execution_retries = incident.execution_retry_count or 0
    verification_retries = incident.verification_retry_count or 0

    if investigation_retries > 0:
        retries.append(f"investigation={investigation_retries}")
    if execution_retries > 0:
        retries.append(f"execution={execution_retries}")
    if verification_retries > 0:
        retries.append(f"verification={verification_retries}")
    if retries:
        parts.append(f"Retries: {', '.join(retries)}")

    return " | ".join(parts)


async def record_resolution(
    session: AsyncSession,
    incident: Incident,
) -> None:
    """
    Record structured resolution outcome on a terminal incident.

    Called from the state machine when transitioning to a terminal state.
    Must be idempotent — safe to call multiple times.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        correlation_id=str(incident.id),
        state=incident.state.value,
    )

    # Skip if already recorded
    if incident.resolved_at is not None:
        log.debug("resolution_already_recorded")
        return

    now = datetime.now(timezone.utc)

    incident.resolution_type = determine_resolution_type(incident)
    incident.resolution_summary = build_resolution_summary(incident)
    incident.resolution_duration_seconds = compute_resolution_duration(incident)
    incident.resolved_at = now

    log.info(
        "resolution_recorded",
        resolution_type=incident.resolution_type,
        duration_seconds=incident.resolution_duration_seconds,
    )
