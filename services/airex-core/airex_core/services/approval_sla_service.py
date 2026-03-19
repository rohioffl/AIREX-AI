"""Approval SLA enforcement — Phase 6 Operational Polish.

Scans incidents in AWAITING_APPROVAL and escalates those that have exceeded
the per-severity SLA threshold.  Called from the ARQ cron job every minute.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from airex_core.core.config import settings
from airex_core.core.events import emit_state_changed
from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.incident import Incident

logger = structlog.get_logger()

# Map severity → SLA threshold in seconds
_SLA_SECONDS: dict[SeverityLevel, int] = {
    SeverityLevel.CRITICAL: settings.APPROVAL_SLA_CRITICAL_SECONDS,
    SeverityLevel.HIGH: settings.APPROVAL_SLA_HIGH_SECONDS,
    SeverityLevel.MEDIUM: settings.APPROVAL_SLA_MEDIUM_SECONDS,
    SeverityLevel.LOW: settings.APPROVAL_SLA_LOW_SECONDS,
}


async def check_approval_slas(session: AsyncSession) -> int:
    """Check all AWAITING_APPROVAL incidents and escalate SLA breaches.

    Returns the number of incidents escalated.
    """
    result = await session.execute(
        select(Incident).where(Incident.state == IncidentState.AWAITING_APPROVAL)
    )
    pending: list[Incident] = list(result.scalars().all())

    escalated = 0
    now = datetime.now(timezone.utc)

    for incident in pending:
        log = logger.bind(
            tenant_id=str(incident.tenant_id),
            incident_id=str(incident.id),
            severity=incident.severity.value if incident.severity else None,
        )

        meta: dict[str, Any] = dict(incident.meta or {})
        if meta.get("_sla_breached"):
            # Already flagged — skip
            continue

        sla_seconds = _SLA_SECONDS.get(incident.severity)
        if sla_seconds is None:
            continue

        # Use updated_at as the time the incident entered AWAITING_APPROVAL
        # (state machine sets updated_at on every transition)
        entered_at = incident.updated_at
        if entered_at is None:
            continue

        if entered_at.tzinfo is None:
            entered_at = entered_at.replace(tzinfo=timezone.utc)

        elapsed = (now - entered_at).total_seconds()
        if elapsed < sla_seconds:
            continue

        # SLA breached — set flag and emit escalation event
        meta["_sla_breached"] = True
        meta["_sla_breach_elapsed_seconds"] = round(elapsed)
        meta["_sla_threshold_seconds"] = sla_seconds
        incident.meta = meta
        flag_modified(incident, "meta")
        await session.flush()

        log.warning(
            "approval_sla_breached",
            elapsed_seconds=round(elapsed),
            threshold_seconds=sla_seconds,
            severity=incident.severity.value if incident.severity else None,
        )

        # Emit SSE so the frontend can highlight the overdue card
        try:
            await emit_state_changed(
                str(incident.tenant_id),
                str(incident.id),
                incident.state.value,
                incident.state.value,
                reason="Approval SLA breached — escalation required",
            )
        except Exception:
            pass

        # Slack notification if configured
        if settings.SLACK_WEBHOOK_URL:
            try:
                await _notify_slack(incident, elapsed, sla_seconds)
            except Exception:
                pass

        escalated += 1

    return escalated


async def _notify_slack(
    incident: Incident,
    elapsed: float,
    threshold: int,
) -> None:
    """Post a Slack notification for a breached SLA."""
    import httpx

    minutes_elapsed = round(elapsed / 60, 1)
    minutes_threshold = round(threshold / 60, 1)

    payload = {
        "text": (
            f":alarm_clock: *Approval SLA Breached*\n"
            f"Incident `{incident.id}` — *{incident.title}*\n"
            f"Severity: `{incident.severity.value if incident.severity else 'unknown'}`  |  "
            f"Elapsed: `{minutes_elapsed}m` / SLA: `{minutes_threshold}m`\n"
            f"Action required immediately."
        )
    }
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(settings.SLACK_WEBHOOK_URL, json=payload)


__all__ = ["check_approval_slas"]
