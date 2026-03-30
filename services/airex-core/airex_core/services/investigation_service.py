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
from collections.abc import Sequence
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from airex_core.core.config import settings
from airex_core.core.events import emit_evidence_added, emit_investigation_progress
from airex_core.core.investigation_bridge import InvestigationBridge
from airex_core.core.knowledge_graph import knowledge_graph
from airex_core.core.state_machine import transition_state
from airex_core.investigations import INVESTIGATION_REGISTRY
from airex_core.investigations.base import (
    BaseInvestigation,
    InvestigationResult,
    ProbeResult,
)
from airex_core.investigations.probe_chainer import get_chained_probes
from airex_core.investigations.probe_map import get_secondary_probes
from airex_core.models.enums import IncidentState
from airex_core.models.evidence import Evidence
from airex_core.models.incident import Incident
from airex_core.services.anomaly_detector import annotate_probe_results, summarize_anomalies

logger = structlog.get_logger()
openclaw_bridge = InvestigationBridge()


def _should_use_cloud_investigation(meta: dict[str, Any]) -> bool:
    """Check if incident meta has enough cloud context for a real investigation."""
    cloud = (meta.get("_cloud") or "").lower()
    has_target = meta.get("_has_cloud_target", False)
    return cloud in ("gcp", "aws") and has_target


def _build_timeline_observations(
    results: Sequence[InvestigationResult],
    anomaly_summary: dict[str, Any] | None = None,
) -> list[str]:
    observations: list[str] = []
    for result in results:
        if isinstance(result, ProbeResult):
            for metric_name, value in result.metrics.items():
                if isinstance(value, (int, float, str, bool)):
                    observations.append(f"{result.tool_name}:{metric_name}={value}")
        raw_output = getattr(result, "raw_output", "")
        if isinstance(raw_output, str):
            first_line = next((line.strip() for line in raw_output.splitlines() if line.strip()), "")
            if first_line:
                observations.append(first_line)

    if anomaly_summary:
        observations.append(
            f"anomalies={anomaly_summary.get('total_count', 0)} critical={anomaly_summary.get('critical_count', 0)}"
        )
    return list(dict.fromkeys(observations))[:12]


def _build_timeline_metrics(results: Sequence[InvestigationResult]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for result in results:
        if not isinstance(result, ProbeResult):
            continue
        for metric_name, value in result.metrics.items():
            if isinstance(value, (int, float, str, bool)):
                metrics[f"{result.tool_name}.{metric_name}"] = value
    return metrics


def _extract_config_snapshot(results: Sequence[InvestigationResult]) -> tuple[str | None, dict[str, Any] | None]:
    for result in results:
        if not isinstance(result, ProbeResult):
            continue
        if result.tool_name not in {"change_detection_aws", "change_detection_gcp", "change_detection"}:
            continue
        metrics = dict(result.metrics or {})
        if not metrics:
            continue
        config_name = (
            str(metrics.get("resource_name") or metrics.get("service_name") or metrics.get("instance_id") or "deployment")
            .strip()
        )
        return config_name, metrics
    return None, None


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

    # ── Transition RECEIVED → INVESTIGATING ──────────────────────
    # The state machine requires RECEIVED → INVESTIGATING before any probe
    # can run. Retry attempts come in as FAILED_ANALYSIS which transitions
    # directly to RECOMMENDATION_READY or FAILED_ANALYSIS — both valid.
    if incident.state == IncidentState.RECEIVED:
        await transition_state(
            session,
            incident,
            IncidentState.INVESTIGATING,
            reason="Investigation started",
        )

    if settings.OPENCLAW_ENABLED:
        used_openclaw = await _run_openclaw_investigation(session, incident, log)
        if used_openclaw:
            return

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

    # ── Phase 5: Dynamic probe chaining ─────────────────────────
    # After initial probes complete, examine actual metric values to decide
    # if follow-up probes are warranted based on what was actually found.
    try:
        probe_results_initial = [r for r in all_results if isinstance(r, ProbeResult)]
        already_running_types = {incident.alert_type} | {
            t for t, _ in secondary_plugins
        }
        chained = get_chained_probes(probe_results_initial, already_running_types)

        if chained and not use_cloud:
            chained_plugins: list[tuple[str, BaseInvestigation]] = []
            for probe_type, chain_reason in chained:
                cls = INVESTIGATION_REGISTRY.get(probe_type)
                if cls is not None:
                    chained_plugins.append((probe_type, cls()))
                    log.info(
                        "chained_probe_queued",
                        probe_type=probe_type,
                        reason=chain_reason,
                    )

            if chained_plugins:
                chained_results = await asyncio.wait_for(
                    _run_all_probes(
                        primary_plugin=chained_plugins[0][1],
                        secondary_plugins=chained_plugins[1:],
                        meta=meta,
                        tenant_id=tenant_id,
                        incident_id=incident_id,
                        alert_type=incident.alert_type,
                        total_probes=len(chained_plugins),
                        log=log,
                    ),
                    timeout=settings.INVESTIGATION_TIMEOUT,
                )
                all_results = list(all_results) + chained_results
                log.info(
                    "chained_probes_complete",
                    chained_count=len(chained_plugins),
                    new_results=len(chained_results),
                )
    except Exception as exc:
        log.warning("probe_chaining_failed", error=str(exc))

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

    # ── Knowledge Graph: upsert observed entities (Phase 4) ───────
    try:
        current_meta = incident.meta or {}
        host = current_meta.get("_private_ip") or current_meta.get("_instance_id")
        service_name = current_meta.get("service_name") or current_meta.get("_service_name")
        await knowledge_graph.upsert_alert_entities(
            session=session,
            tenant_id=incident.tenant_id,
            incident_id=incident.id,
            alert_type=incident.alert_type,
            host=host,
            service_name=service_name,
        )
        config_name, config_snapshot = _extract_config_snapshot(all_results)
        await knowledge_graph.record_incident_timeline(
            session=session,
            tenant_id=incident.tenant_id,
            incident_id=incident.id,
            alert_type=incident.alert_type,
            service_name=service_name,
            host=host,
            observations=_build_timeline_observations(all_results, anomaly_summary),
            metrics=_build_timeline_metrics(all_results),
            config_name=config_name,
            config_snapshot=config_snapshot,
        )
    except Exception as exc:
        log.warning("kg_entity_upsert_failed", error=str(exc))

    # Auto-trigger AI recommendation generation
    await _enqueue_recommendation(incident, log)


async def _run_openclaw_investigation(
    session: AsyncSession,
    incident: Incident,
    log: structlog.stdlib.BoundLogger,
) -> bool:
    """Try OpenClaw first and fall back to static probes on any bridge failure."""
    meta = incident.meta or {}
    service_name = meta.get("service_name") or meta.get("_service_name")

    try:
        kg_context = await knowledge_graph.get_context_for_incident(
            session,
            incident.tenant_id,
            incident.alert_type,
            service_name=service_name,
        )
    except Exception as exc:
        log.warning("openclaw_kg_context_failed", error=str(exc))
        kg_context = None

    try:
        contract = await openclaw_bridge.run(
            incident,
            timeout=settings.OPENCLAW_REQUEST_TIMEOUT,
            kg_context=kg_context,
        )
    except Exception as exc:
        failure_meta = dict(incident.meta or {})
        failure_meta["openclaw_run"] = {
            "agent_tool_calls": [],
            "agent_used_tools": [],
            "agent_fallback_used": True,
            "agent_failure_reason": str(exc),
        }
        incident.meta = failure_meta
        flag_modified(incident, "meta")
        await session.flush()
        log.warning("openclaw_bridge_failed_falling_back", error=str(exc))
        return False

    await persist_openclaw_evidence_contract(
        session=session,
        incident=incident,
        contract=contract,
        log=log,
    )

    await transition_state(
        session,
        incident,
        IncidentState.RECOMMENDATION_READY,
        reason=f"OpenClaw investigation complete: {contract.summary}",
    )
    await _enqueue_recommendation(incident, log)
    return True


async def _upsert_openclaw_entities(
    *,
    session: AsyncSession,
    incident: Incident,
    affected_entities: Sequence[str],
) -> None:
    if not affected_entities:
        return

    incident_entity_id = f"incident:{incident.id}"
    await knowledge_graph.upsert_node(
        session=session,
        tenant_id=incident.tenant_id,
        entity_id=incident_entity_id,
        entity_type="incident",
        label=str(incident.id),
        properties={"alert_type": incident.alert_type},
    )

    for entity in affected_entities:
        entity_type, _, entity_name = entity.partition(":")
        if not entity_type or not entity_name:
            continue
        await knowledge_graph.upsert_node(
            session=session,
            tenant_id=incident.tenant_id,
            entity_id=entity,
            entity_type=entity_type,
            label=entity_name,
            properties={"source": "openclaw"},
        )
        await knowledge_graph.add_edge(
            session=session,
            tenant_id=incident.tenant_id,
            src_entity_id=incident_entity_id,
            relation="affected",
            dst_entity_id=entity,
            meta={"incident_id": str(incident.id)},
        )


async def persist_openclaw_evidence_contract(
    *,
    session: AsyncSession,
    incident: Incident,
    contract: Any,
    log: structlog.stdlib.BoundLogger | None = None,
) -> Evidence:
    """Persist a normalized OpenClaw evidence contract onto an incident."""

    evidence = Evidence(
        tenant_id=incident.tenant_id,
        incident_id=incident.id,
        tool_name="openclaw",
        raw_output=contract.model_dump_json(),
    )
    session.add(evidence)
    await session.flush()

    meta = dict(incident.meta or {})
    meta["openclaw"] = contract.model_dump()
    meta["openclaw_run"] = _extract_openclaw_run_meta(contract.raw_refs)
    meta["probe_results"] = [
        {
            "tool_name": "openclaw",
            "signals": contract.signals,
            "affected_entities": contract.affected_entities,
            "confidence": contract.confidence,
        }
    ]
    meta["probe_count"] = 1
    meta["investigation_summary"] = contract.summary
    incident.meta = meta
    flag_modified(incident, "meta")
    await session.flush()

    try:
        await emit_evidence_added(
            tenant_id=str(incident.tenant_id),
            incident_id=str(incident.id),
            tool_name="openclaw",
            evidence_id=str(evidence.id),
        )
    except Exception:
        pass

    try:
        await _upsert_openclaw_entities(
            session=session,
            incident=incident,
            affected_entities=contract.affected_entities,
        )
        current_meta = incident.meta or {}
        host = current_meta.get("_private_ip") or current_meta.get("_instance_id")
        service_name = current_meta.get("service_name") or current_meta.get("_service_name")
        await knowledge_graph.record_incident_timeline(
            session=session,
            tenant_id=incident.tenant_id,
            incident_id=incident.id,
            alert_type=incident.alert_type,
            service_name=service_name,
            host=host,
            observations=contract.signals,
            metrics={
                "openclaw.confidence": contract.confidence,
                "openclaw.affected_entity_count": len(contract.affected_entities),
            },
        )
    except Exception as exc:
        if log is not None:
            log.warning("openclaw_kg_entity_upsert_failed", error=str(exc))

    return evidence


def _extract_openclaw_run_meta(raw_refs: Any) -> dict[str, Any]:
    if not isinstance(raw_refs, dict):
        return {
            "agent_tool_calls": [],
            "agent_used_tools": [],
            "agent_fallback_used": False,
            "agent_failure_reason": "",
        }

    agent_tool_calls = raw_refs.get("agent_tool_calls")
    agent_used_tools = raw_refs.get("agent_used_tools")
    return {
        "agent_tool_calls": agent_tool_calls if isinstance(agent_tool_calls, list) else [],
        "agent_used_tools": agent_used_tools if isinstance(agent_used_tools, list) else [],
        "agent_fallback_used": bool(raw_refs.get("agent_fallback_used", False)),
        "agent_failure_reason": str(raw_refs.get("agent_failure_reason") or ""),
        "forensic_tools": (
            raw_refs.get("forensic_tools")
            if isinstance(raw_refs.get("forensic_tools"), list)
            else []
        ),
    }


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
