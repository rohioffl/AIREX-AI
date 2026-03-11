"""
Investigation orchestrator.

Runs the appropriate investigation plugin(s), stores evidence,
handles retries, and transitions state on completion or failure.

Multi-probe execution:
  For each incident, runs a primary probe (matched by alert_type) plus
  correlated secondary probes in parallel via asyncio.gather. Each probe
  emits SSE progress events so the frontend can show a live timeline.
  After all probes complete, the anomaly detector annotates results.

Cloud-aware routing:
  When incident meta contains `_cloud` = "gcp" or "aws" (parsed from
  Site24x7 tags), the orchestrator routes to CloudInvestigation which
  connects via SSM / OS Login to run real diagnostics on the server.
  Otherwise, it falls back to the simulated investigation plugins.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from airex_core.core.config import settings
from airex_core.core.events import emit_evidence_added, emit_investigation_progress
from airex_core.core.state_machine import transition_state
from airex_core.investigations import INVESTIGATION_REGISTRY
from airex_core.investigations.base import (
    BaseInvestigation,
    InvestigationResult,
    ProbeResult,
)
from airex_core.investigations.probe_map import get_secondary_probes
from airex_core.models.enums import IncidentState
from airex_core.models.evidence import Evidence
from airex_core.models.incident import Incident
from airex_core.services.anomaly_detector import annotate_probe_results, summarize_anomalies

logger = structlog.get_logger()


def _should_use_cloud_investigation(meta: dict[str, Any]) -> bool:
    """Check if incident meta has enough cloud context for a real investigation."""
    cloud = (meta.get("_cloud") or "").lower()
    has_target = meta.get("_has_cloud_target", False)
    return cloud in ("gcp", "aws") and has_target


async def run_investigation(
    session: AsyncSession,
    incident: Incident,
) -> None:
    """
    Execute investigation probes for the incident's alert_type.

    Execution strategy:
      1. Resolve primary probe (cloud or simulated)
      2. Resolve secondary probes from CORRELATION_MAP
      3. Run all probes in parallel with asyncio.gather
      4. Emit SSE progress events for each probe
      5. Run anomaly detection on all results
      6. Store evidence records for each probe
      7. Transition to RECOMMENDATION_READY

    Timeouts: INVESTIGATION_TIMEOUT seconds (shared across all probes).
    Retries: MAX_INVESTIGATION_RETRIES.
    """
    log = logger.bind(
        tenant_id=str(incident.tenant_id),
        incident_id=str(incident.id),
        correlation_id=str(incident.id),
        alert_type=incident.alert_type,
    )

    meta = incident.meta or {}
    tenant_id = str(incident.tenant_id)
    incident_id = str(incident.id)

    # ── Resolve primary probe ────────────────────────────────────
    use_cloud = _should_use_cloud_investigation(meta)

    if use_cloud:
        from airex_core.investigations.cloud_investigation import CloudInvestigation

        primary_plugin: BaseInvestigation = CloudInvestigation()
        meta["alert_type"] = incident.alert_type
        log.info(
            "using_cloud_investigation",
            cloud=meta.get("_cloud"),
            target_ip=meta.get("_private_ip"),
            instance_id=meta.get("_instance_id"),
        )
    else:
        primary_cls = INVESTIGATION_REGISTRY.get(incident.alert_type)
        if primary_cls is None:
            log.warning("no_investigation_plugin", alert_type=incident.alert_type)
            meta = dict(meta)
            meta.setdefault("_manual_review_required", True)
            meta.setdefault(
                "_manual_review_reason",
                f"No automation plugin for alert_type {incident.alert_type}",
            )
            incident.meta = meta
            flag_modified(incident, "meta")
            session.add(incident)
            await session.flush()
            await transition_state(
                session,
                incident,
                IncidentState.FAILED_ANALYSIS,
                reason=f"Manual review required: no plugin for {incident.alert_type}",
            )
            return
        primary_plugin = primary_cls()
        log.info("using_simulated_investigation", plugin=type(primary_plugin).__name__)

    # ── Resolve secondary probes ─────────────────────────────────
    secondary_plugins: list[tuple[str, BaseInvestigation]] = []
    if not use_cloud:
        # Only run secondary probes for simulated investigations
        # Cloud investigation already does comprehensive checks
        for secondary_type in get_secondary_probes(incident.alert_type):
            sec_cls = INVESTIGATION_REGISTRY.get(secondary_type)
            if sec_cls is not None:
                secondary_plugins.append((secondary_type, sec_cls()))

    # Add Site24x7 enrichment probe when incident originated from Site24x7
    try:
        from airex_core.investigations.site24x7_probe import (
            Site24x7Probe,
            should_run_site24x7_probe,
        )

        if should_run_site24x7_probe(meta):
            secondary_plugins.append(("site24x7_enrichment", Site24x7Probe()))
            log.info("site24x7_probe_added")
    except Exception:
        pass

    # Add Site24x7 outage history probe for pattern analysis
    try:
        from airex_core.investigations.site24x7_outage_probe import (
            Site24x7OutageHistoryProbe,
            should_run_outage_probe,
        )

        if should_run_outage_probe(meta):
            secondary_plugins.append(("site24x7_outage_history", Site24x7OutageHistoryProbe()))
            log.info("site24x7_outage_probe_added")
    except Exception:
        pass

    # Add change detection probe when cloud context is available
    try:
        from airex_core.investigations.change_detection_probe import (
            ChangeDetectionProbe,
            should_run_change_detection,
        )

        if should_run_change_detection(meta):
            secondary_plugins.append(("change_detection", ChangeDetectionProbe()))
            log.info("change_detection_probe_added")
    except Exception:
        pass

    # Add infrastructure state probe when cloud context is available
    try:
        from airex_core.investigations.infra_state_probe import (
            InfraStateProbe,
            should_run_infra_state_probe,
        )

        if should_run_infra_state_probe(meta):
            secondary_plugins.append(("infra_state", InfraStateProbe()))
            log.info("infra_state_probe_added")
    except Exception:
        pass

    # Add enhanced log analysis probe for applicable alert types
    try:
        from airex_core.investigations.log_analysis_probe import (
            LogAnalysisProbe,
            should_run_log_analysis,
        )

        if should_run_log_analysis(meta):
            secondary_plugins.append(("log_analysis", LogAnalysisProbe()))
            log.info("log_analysis_probe_added")
    except Exception:
        pass

    total_probes = 1 + len(secondary_plugins)
    log.info(
        "investigation_plan",
        primary=incident.alert_type,
        secondary_count=len(secondary_plugins),
        secondary_types=[t for t, _ in secondary_plugins],
        total_probes=total_probes,
    )

    # ── Run all probes in parallel ───────────────────────────────
    try:
        all_results = await asyncio.wait_for(
            _run_all_probes(
                primary_plugin=primary_plugin,
                secondary_plugins=secondary_plugins,
                meta=meta,
                tenant_id=tenant_id,
                incident_id=incident_id,
                alert_type=incident.alert_type,
                total_probes=total_probes,
                log=log,
            ),
            timeout=settings.INVESTIGATION_TIMEOUT,
        )
    except asyncio.TimeoutError:
        await _handle_failure(session, incident, log, "Investigation timed out")
        return
    except (RuntimeError, ValueError, TypeError) as exc:
        await _handle_failure(session, incident, log, f"Investigation failed: {exc}")
        return

    if not all_results:
        await _handle_failure(session, incident, log, "All probes returned no results")
        return

    # ── Anomaly detection ────────────────────────────────────────
    probe_results = [r for r in all_results if isinstance(r, ProbeResult)]
    if probe_results:
        annotate_probe_results(probe_results)
        anomaly_summary = summarize_anomalies(probe_results)

        # Emit anomaly SSE event if any detected
        if anomaly_summary["total_count"] > 0:
            try:
                await emit_investigation_progress(
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    probe_name="anomaly_detector",
                    status="anomalies_detected",
                    step=total_probes,
                    total_steps=total_probes,
                    category="analysis",
                    anomaly_count=anomaly_summary["total_count"],
                )
            except Exception:
                pass

        log.info(
            "anomaly_detection_complete",
            total_anomalies=anomaly_summary["total_count"],
            critical=anomaly_summary["critical_count"],
            warning=anomaly_summary["warning_count"],
        )
    else:
        anomaly_summary = None

    # ── Store evidence for each probe ────────────────────────────
    for result in all_results:
        evidence = Evidence(
            tenant_id=incident.tenant_id,
            incident_id=incident.id,
            tool_name=result.tool_name,
            raw_output=result.raw_output,
        )
        session.add(evidence)
        await session.flush()

        log.info("evidence_stored", tool=result.tool_name)

        try:
            await emit_evidence_added(
                tenant_id=tenant_id,
                incident_id=incident_id,
                tool_name=result.tool_name,
                evidence_id=str(evidence.id),
            )
        except Exception:
            pass

    # ── Store structured probe data in incident meta ─────────────
    meta = dict(incident.meta or {})

    # Store probe metrics summary
    probe_summary: list[dict[str, Any]] = []
    for result in all_results:
        entry: dict[str, Any] = {
            "tool_name": result.tool_name,
        }
        if isinstance(result, ProbeResult):
            entry["category"] = result.category.value
            entry["metrics"] = result.metrics
            entry["probe_type"] = result.probe_type
            entry["duration_ms"] = result.duration_ms
            entry["anomaly_count"] = len(result.anomalies)
            entry["anomalies"] = [
                {
                    "metric_name": a.metric_name,
                    "value": a.value,
                    "threshold": a.threshold,
                    "severity": a.severity,
                    "description": a.description,
                }
                for a in result.anomalies
            ]
        probe_summary.append(entry)

    meta["probe_results"] = probe_summary
    meta["probe_count"] = len(all_results)
    if anomaly_summary:
        meta["anomaly_summary"] = anomaly_summary

    incident.meta = meta
    flag_modified(incident, "meta")
    await session.flush()

    # ── Determine investigation summary for transition reason ────
    tool_names = [r.tool_name for r in all_results]
    anomaly_note = ""
    if anomaly_summary and anomaly_summary["total_count"] > 0:
        anomaly_note = (
            f" ({anomaly_summary['total_count']} anomalies: "
            f"{anomaly_summary['critical_count']} critical, "
            f"{anomaly_summary['warning_count']} warning)"
        )

    reason = (
        f"Investigation complete via {len(all_results)} probes: "
        f"{', '.join(tool_names)}{anomaly_note}"
    )

    log.info(
        "investigation_complete",
        probe_count=len(all_results),
        tools=tool_names,
    )

    await transition_state(
        session,
        incident,
        IncidentState.RECOMMENDATION_READY,
        reason=reason,
    )

    # Auto-trigger AI recommendation generation
    await _enqueue_recommendation(incident, log)


async def _run_all_probes(
    primary_plugin: BaseInvestigation,
    secondary_plugins: list[tuple[str, BaseInvestigation]],
    meta: dict,
    tenant_id: str,
    incident_id: str,
    alert_type: str,
    total_probes: int,
    log: structlog.stdlib.BoundLogger,
) -> list[InvestigationResult]:
    """Run primary and secondary probes in parallel, emitting SSE events."""

    async def _run_single_probe(
        plugin: BaseInvestigation,
        probe_meta: dict,
        step: int,
        probe_type: str,
    ) -> InvestigationResult | None:
        """Run a single probe with timing, progress events, and error handling."""
        probe_name = type(plugin).__name__
        category = getattr(plugin, "alert_type", "unknown")

        # Emit "started" event
        try:
            await emit_investigation_progress(
                tenant_id=tenant_id,
                incident_id=incident_id,
                probe_name=probe_name,
                status="started",
                step=step,
                total_steps=total_probes,
                category=category,
            )
        except Exception:
            pass

        start_time = time.monotonic()
        try:
            result = await plugin.investigate(probe_meta)
            duration_ms = round((time.monotonic() - start_time) * 1000, 1)

            # Tag ProbeResult with timing and type
            if isinstance(result, ProbeResult):
                result.duration_ms = duration_ms
                if not result.probe_type:
                    result.probe_type = probe_type

            # Emit "completed" event
            try:
                await emit_investigation_progress(
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    probe_name=probe_name,
                    status="completed",
                    step=step,
                    total_steps=total_probes,
                    category=category,
                    duration_ms=duration_ms,
                )
            except Exception:
                pass

            log.info(
                "probe_completed",
                probe=probe_name,
                probe_type=probe_type,
                duration_ms=duration_ms,
                step=step,
            )
            return result

        except Exception as exc:
            duration_ms = round((time.monotonic() - start_time) * 1000, 1)
            log.warning(
                "probe_failed",
                probe=probe_name,
                probe_type=probe_type,
                error=str(exc),
                duration_ms=duration_ms,
            )

            # Emit "failed" event
            try:
                await emit_investigation_progress(
                    tenant_id=tenant_id,
                    incident_id=incident_id,
                    probe_name=probe_name,
                    status="failed",
                    step=step,
                    total_steps=total_probes,
                    category=category,
                    duration_ms=duration_ms,
                )
            except Exception:
                pass

            # Secondary probe failures are non-fatal
            if probe_type == "secondary":
                return None
            raise

    # Build task list: primary at step 1, secondaries at steps 2+
    tasks = [_run_single_probe(primary_plugin, meta, 1, "primary")]
    for idx, (sec_type, sec_plugin) in enumerate(secondary_plugins, start=2):
        tasks.append(_run_single_probe(sec_plugin, meta, idx, "secondary"))

    # Run all probes in parallel
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results — primary failure is fatal, secondary failures are ignored
    results: list[InvestigationResult] = []
    for i, raw in enumerate(raw_results):
        if isinstance(raw, BaseException):
            if i == 0:
                # Primary probe raised — re-raise
                raise raw
            # Secondary probe failed — skip
            log.warning("secondary_probe_exception", error=str(raw))
            continue
        if raw is not None:
            results.append(raw)

    return results


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
    """Increment retry counter or mark for manual review if retries exhausted."""
    incident.investigation_retry_count += 1
    current_retries = incident.investigation_retry_count

    if current_retries >= settings.MAX_INVESTIGATION_RETRIES:
        log.error(
            "investigation_max_retries_exceeded",
            retries=current_retries,
        )
        meta = dict(incident.meta or {})
        meta.setdefault("_manual_review_required", True)
        meta["_manual_review_reason"] = f"Investigation retries exhausted: {reason}"
        incident.meta = meta
        flag_modified(incident, "meta")
        session.add(incident)
        await session.flush()
        await transition_state(
            session,
            incident,
            IncidentState.FAILED_ANALYSIS,
            reason=f"Investigation retries exhausted ({current_retries}): {reason}",
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
