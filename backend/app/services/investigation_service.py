"""
Investigation orchestrator.

Runs the appropriate investigation plugin, stores evidence,
handles retries, and transitions state on completion or failure.

Cloud-aware routing:
  When incident meta contains `_cloud` = "gcp" or "aws" (parsed from
  Site24x7 tags), the orchestrator routes to CloudInvestigation which
  connects via SSM / OS Login to run real diagnostics on the server.
  Otherwise, it falls back to the simulated investigation plugins.
"""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.events import emit_evidence_added
from app.core.state_machine import transition_state
from app.models.enums import IncidentState
from app.models.evidence import Evidence
from app.models.incident import Incident
from app.investigations.base import InvestigationResult
from app.investigations import INVESTIGATION_REGISTRY

logger = structlog.get_logger()


def _should_use_cloud_investigation(meta: dict) -> bool:
    """Check if incident meta has enough cloud context for a real investigation."""
    cloud = (meta.get("_cloud") or "").lower()
    has_target = meta.get("_has_cloud_target", False)
    return cloud in ("gcp", "aws") and has_target


async def run_investigation(
    session: AsyncSession,
    incident: Incident,
) -> None:
    """
    Execute the investigation plugin for the incident's alert_type.

    Routing priority:
      1. If meta has _cloud=gcp/aws + target → CloudInvestigation (real SSH/SSM)
      2. If alert_type matches INVESTIGATION_REGISTRY → simulated plugin
      3. Otherwise → ESCALATED

    Timeouts: INVESTIGATION_TIMEOUT seconds.
    Retries: MAX_INVESTIGATION_RETRIES.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        alert_type=incident.alert_type,
    )

    meta = incident.meta or {}

    # Route to cloud-aware or simulated plugin
    if _should_use_cloud_investigation(meta):
        from app.investigations.cloud_investigation import CloudInvestigation
        plugin = CloudInvestigation()
        # Inject alert_type into meta so cloud plugin knows what commands to run
        meta["alert_type"] = incident.alert_type
        log.info(
            "using_cloud_investigation",
            cloud=meta.get("_cloud"),
            target_ip=meta.get("_private_ip"),
            instance_id=meta.get("_instance_id"),
        )
    else:
        plugin_cls = INVESTIGATION_REGISTRY.get(incident.alert_type)
        if plugin_cls is None:
            log.warning("no_investigation_plugin", alert_type=incident.alert_type)
            await transition_state(
                session,
                incident,
                IncidentState.ESCALATED,
                reason=f"No investigation plugin for alert_type: {incident.alert_type}",
            )
            return
        plugin = plugin_cls()
        log.info("using_simulated_investigation", plugin=type(plugin).__name__)

    try:
        result: InvestigationResult = await asyncio.wait_for(
            plugin.investigate(meta),
            timeout=settings.INVESTIGATION_TIMEOUT,
        )

        # Store evidence
        evidence = Evidence(
            tenant_id=incident.tenant_id,
            incident_id=incident.id,
            tool_name=result.tool_name,
            raw_output=result.raw_output,
        )
        session.add(evidence)
        await session.flush()

        log.info("investigation_complete", tool=result.tool_name)

        # SSE: evidence added
        try:
            await emit_evidence_added(
                tenant_id=str(incident.tenant_id),
                incident_id=str(incident.id),
                tool_name=result.tool_name,
                evidence_id=str(evidence.id),
            )
        except Exception:
            pass

        await transition_state(
            session,
            incident,
            IncidentState.RECOMMENDATION_READY,
            reason=f"Investigation complete via {result.tool_name}",
        )

        # Auto-trigger AI recommendation generation
        await _enqueue_recommendation(incident, log)

    except asyncio.TimeoutError:
        await _handle_failure(
            session, incident, log, "Investigation timed out"
        )
    except Exception as exc:
        await _handle_failure(
            session, incident, log, f"Investigation failed: {exc}"
        )


async def _enqueue_recommendation(
    incident: Incident,
    log: structlog.stdlib.BoundLogger,
) -> None:
    """Enqueue the AI recommendation ARQ task after investigation completes."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await pool.enqueue_job(
            "generate_recommendation_task",
            str(incident.tenant_id),
            str(incident.id),
        )
        await pool.aclose()
        log.info("recommendation_task_enqueued")
    except Exception as exc:
        log.error("recommendation_enqueue_failed", error=str(exc))


async def _handle_failure(
    session: AsyncSession,
    incident: Incident,
    log: structlog.stdlib.BoundLogger,
    reason: str,
) -> None:
    """Increment retry counter or escalate if max retries exceeded."""
    incident.investigation_retry_count += 1
    current_retries = incident.investigation_retry_count

    if current_retries >= settings.MAX_INVESTIGATION_RETRIES:
        log.error(
            "investigation_max_retries_exceeded",
            retries=current_retries,
        )
        await transition_state(
            session,
            incident,
            IncidentState.ESCALATED,
            reason=f"Max investigation retries ({current_retries}) exceeded: {reason}",
        )
    else:
        log.warning(
            "investigation_retry",
            retries=current_retries,
            reason=reason,
        )
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_ANALYSIS,
            reason=reason,
        )
