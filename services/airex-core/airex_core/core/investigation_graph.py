"""LangGraph-based investigation orchestrator.

Replaces the OpenClaw gateway with a Python-native StateGraph.
Six nodes mirror the investigation lifecycle:

  resolve_context  ->  plan_probes  ->  execute_probes
       ->  analyze  ->  store  ->  transition

The ``AsyncSession`` is stored in a ``ContextVar`` before the graph runs
so nodes stay as pure functions over ``InvestigationState`` while still
having DB access.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from contextvars import ContextVar
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from airex_core.core.config import settings
from airex_core.core.events import emit_evidence_added, emit_investigation_progress
from airex_core.core.investigation_context_resolver import (
    resolve_investigation_context as _resolve_ctx,
)
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

# ── ContextVar for DB session ─────────────────────────────────────
_session_var: ContextVar[AsyncSession] = ContextVar("investigation_session")
_incident_var: ContextVar[Incident] = ContextVar("investigation_incident")


# ── State schema ──────────────────────────────────────────────────

class InvestigationState(TypedDict, total=False):
    """Typed state flowing through the LangGraph investigation graph."""

    # Identity
    tenant_id: str
    incident_id: str
    alert_type: str
    meta: dict[str, Any]

    # Context resolution
    use_cloud: bool

    # Probe planning
    primary_plugin: Any  # BaseInvestigation instance
    secondary_plugins: list[tuple[str, Any]]
    total_probes: int

    # Execution
    all_results: list[Any]  # list[InvestigationResult]
    anomaly_summary: dict[str, Any] | None

    # Control
    error: str | None
    failed: bool


# ── Node: resolve_context ─────────────────────────────────────────

async def resolve_context_node(state: InvestigationState) -> dict:
    """Enrich incident meta with cloud target info and transition to INVESTIGATING."""
    session = _session_var.get()
    incident = _incident_var.get()

    # Transition RECEIVED -> INVESTIGATING
    if incident.state == IncidentState.RECEIVED:
        await transition_state(
            session,
            incident,
            IncidentState.INVESTIGATING,
            reason="Investigation started",
        )

    meta = dict(incident.meta or {})
    enriched = await _resolve_ctx(meta)

    use_cloud = _should_use_cloud_investigation(enriched)

    return {
        "meta": enriched,
        "use_cloud": use_cloud,
        "tenant_id": str(incident.tenant_id),
        "incident_id": str(incident.id),
        "alert_type": incident.alert_type,
    }


def _should_use_cloud_investigation(meta: dict[str, Any]) -> bool:
    """Check if incident meta has enough cloud context for a real investigation."""
    cloud = (meta.get("_cloud") or "").lower()
    has_target = meta.get("_has_cloud_target", False)
    return cloud in ("gcp", "aws") and has_target


# ── Node: plan_probes ─────────────────────────────────────────────

async def plan_probes_node(state: InvestigationState) -> dict:
    """Select primary and secondary probes based on alert type and meta.

    Extracted from investigation_service.py L151-270.
    """
    session = _session_var.get()
    incident = _incident_var.get()
    log = logger.bind(
        tenant_id=state["tenant_id"],
        incident_id=state["incident_id"],
        alert_type=state["alert_type"],
    )

    meta = state["meta"]
    use_cloud = state["use_cloud"]
    alert_type = state["alert_type"]

    # ── Resolve primary probe ────────────────────────────────────
    if use_cloud:
        from airex_core.investigations.cloud_investigation import CloudInvestigation

        primary_plugin: BaseInvestigation = CloudInvestigation()
        meta["alert_type"] = alert_type
        log.info(
            "using_cloud_investigation",
            cloud=meta.get("_cloud"),
            target_ip=meta.get("_private_ip"),
            instance_id=meta.get("_instance_id"),
        )
    else:
        primary_cls = INVESTIGATION_REGISTRY.get(alert_type)
        if primary_cls is None:
            log.warning("no_investigation_plugin", alert_type=alert_type)
            meta = dict(meta)
            meta.setdefault("_manual_review_required", True)
            meta.setdefault(
                "_manual_review_reason",
                f"No automation plugin for alert_type {alert_type}",
            )
            incident.meta = meta
            flag_modified(incident, "meta")
            session.add(incident)
            await session.flush()
            await transition_state(
                session,
                incident,
                IncidentState.FAILED_ANALYSIS,
                reason=f"Manual review required: no plugin for {alert_type}",
            )
            return {"failed": True, "error": f"No plugin for {alert_type}"}
        primary_plugin = primary_cls()
        log.info("using_simulated_investigation", plugin=type(primary_plugin).__name__)

    # ── Resolve secondary probes ─────────────────────────────────
    secondary_plugins: list[tuple[str, BaseInvestigation]] = []
    if not use_cloud:
        for secondary_type in get_secondary_probes(alert_type):
            sec_cls = INVESTIGATION_REGISTRY.get(secondary_type)
            if sec_cls is not None:
                secondary_plugins.append((secondary_type, sec_cls()))

    # Add Site24x7 enrichment probe
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

    # Add Site24x7 outage history probe
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

    # Add change detection probe
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

    # Add infrastructure state probe
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

    # Add log analysis probe
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
        primary=alert_type,
        secondary_count=len(secondary_plugins),
        secondary_types=[t for t, _ in secondary_plugins],
        total_probes=total_probes,
    )

    return {
        "primary_plugin": primary_plugin,
        "secondary_plugins": secondary_plugins,
        "total_probes": total_probes,
        "meta": meta,
    }


# ── Node: execute_probes ──────────────────────────────────────────

async def execute_probes_node(state: InvestigationState) -> dict:
    """Run all probes in parallel with per-probe timeouts.

    Extracted from investigation_service.py _run_all_probes() L634-756.
    """
    if state.get("failed"):
        return {}

    incident = _incident_var.get()
    session = _session_var.get()
    log = logger.bind(
        tenant_id=state["tenant_id"],
        incident_id=state["incident_id"],
    )

    primary_plugin = state["primary_plugin"]
    secondary_plugins = state["secondary_plugins"]
    meta = state["meta"]
    tenant_id = state["tenant_id"]
    incident_id = state["incident_id"]
    total_probes = state["total_probes"]

    try:
        all_results = await asyncio.wait_for(
            _run_all_probes(
                primary_plugin=primary_plugin,
                secondary_plugins=secondary_plugins,
                meta=meta,
                tenant_id=tenant_id,
                incident_id=incident_id,
                alert_type=state["alert_type"],
                total_probes=total_probes,
                log=log,
            ),
            timeout=settings.INVESTIGATION_TIMEOUT,
        )
    except asyncio.TimeoutError:
        await _handle_failure(session, incident, log, "Investigation timed out")
        return {"failed": True, "error": "Investigation timed out"}
    except (RuntimeError, ValueError, TypeError) as exc:
        await _handle_failure(session, incident, log, f"Investigation failed: {exc}")
        return {"failed": True, "error": str(exc)}

    if not all_results:
        await _handle_failure(session, incident, log, "All probes returned no results")
        return {"failed": True, "error": "All probes returned no results"}

    # ── Dynamic probe chaining ─────────────────────────────────
    use_cloud = state.get("use_cloud", False)
    try:
        probe_results_initial = [r for r in all_results if isinstance(r, ProbeResult)]
        already_running_types = {state["alert_type"]} | {
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
                        alert_type=state["alert_type"],
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

    return {"all_results": all_results}


# ── Node: analyze ─────────────────────────────────────────────────

async def analyze_node(state: InvestigationState) -> dict:
    """Run anomaly detection on probe results.

    Extracted from investigation_service.py L344-373.
    """
    if state.get("failed"):
        return {}

    all_results = state["all_results"]
    tenant_id = state["tenant_id"]
    incident_id = state["incident_id"]
    total_probes = state.get("total_probes", len(all_results))

    probe_results = [r for r in all_results if isinstance(r, ProbeResult)]
    if probe_results:
        annotate_probe_results(probe_results)
        anomaly_summary = summarize_anomalies(probe_results)

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

        logger.info(
            "anomaly_detection_complete",
            tenant_id=tenant_id,
            incident_id=incident_id,
            total_anomalies=anomaly_summary["total_count"],
            critical=anomaly_summary["critical_count"],
            warning=anomaly_summary["warning_count"],
        )
    else:
        anomaly_summary = None

    return {"anomaly_summary": anomaly_summary}


# ── Node: store ───────────────────────────────────────────────────

async def store_node(state: InvestigationState) -> dict:
    """Persist evidence records and update incident meta.

    Extracted from investigation_service.py L375-432.
    """
    if state.get("failed"):
        return {}

    session = _session_var.get()
    incident = _incident_var.get()
    log = logger.bind(
        tenant_id=state["tenant_id"],
        incident_id=state["incident_id"],
    )

    all_results = state["all_results"]
    anomaly_summary = state.get("anomaly_summary")
    tenant_id = state["tenant_id"]
    incident_id = state["incident_id"]

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

    probe_summary: list[dict[str, Any]] = []
    for result in all_results:
        entry: dict[str, Any] = {"tool_name": result.tool_name}
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

    return {}


# ── Node: transition ──────────────────────────────────────────────

async def transition_node(state: InvestigationState) -> dict:
    """Transition to RECOMMENDATION_READY, update KG, and enqueue recommendation.

    Extracted from investigation_service.py L434-492.
    """
    if state.get("failed"):
        return {}

    session = _session_var.get()
    incident = _incident_var.get()
    log = logger.bind(
        tenant_id=state["tenant_id"],
        incident_id=state["incident_id"],
    )

    all_results = state["all_results"]
    anomaly_summary = state.get("anomaly_summary")

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

    # ── Knowledge Graph: upsert observed entities ─────────────────
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

        from airex_core.services.investigation_service import (
            _build_timeline_observations,
            _build_timeline_metrics,
            _extract_config_snapshot,
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

    return {}


# ── Graph builder ─────────────────────────────────────────────────

def _should_continue(state: InvestigationState) -> str:
    """Route to END if a failure occurred, otherwise continue."""
    if state.get("failed"):
        return "end"
    return "continue"


def build_investigation_graph() -> StateGraph:
    """Construct the 6-node investigation StateGraph."""
    graph = StateGraph(InvestigationState)

    graph.add_node("resolve_context", resolve_context_node)
    graph.add_node("plan_probes", plan_probes_node)
    graph.add_node("execute_probes", execute_probes_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("store", store_node)
    graph.add_node("transition", transition_node)

    graph.set_entry_point("resolve_context")
    graph.add_edge("resolve_context", "plan_probes")

    # After plan_probes, check if we failed (no plugin)
    graph.add_conditional_edges(
        "plan_probes",
        _should_continue,
        {"continue": "execute_probes", "end": END},
    )

    # After execute_probes, check if we failed (timeout, no results)
    graph.add_conditional_edges(
        "execute_probes",
        _should_continue,
        {"continue": "analyze", "end": END},
    )

    graph.add_edge("analyze", "store")
    graph.add_edge("store", "transition")
    graph.add_edge("transition", END)

    return graph


# ── Public entry point ────────────────────────────────────────────

_compiled_graph = None


def _get_compiled_graph():
    """Lazily compile the graph once."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_investigation_graph().compile()
    return _compiled_graph


async def run_investigation_graph(
    session: AsyncSession,
    incident: Incident,
) -> None:
    """Run the LangGraph investigation pipeline.

    Sets session and incident into ContextVars so nodes can access them
    without passing through the state dict.
    """
    session_token = _session_var.set(session)
    incident_token = _incident_var.set(incident)
    try:
        graph = _get_compiled_graph()
        initial_state: InvestigationState = {
            "tenant_id": str(incident.tenant_id),
            "incident_id": str(incident.id),
            "alert_type": incident.alert_type,
            "meta": dict(incident.meta or {}),
            "use_cloud": False,
            "primary_plugin": None,
            "secondary_plugins": [],
            "total_probes": 0,
            "all_results": [],
            "anomaly_summary": None,
            "error": None,
            "failed": False,
        }
        await graph.ainvoke(initial_state)
    finally:
        _session_var.reset(session_token)
        _incident_var.reset(incident_token)


# ── Shared helpers (extracted from investigation_service.py) ──────


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
        probe_name = type(plugin).__name__
        category = getattr(plugin, "alert_type", "unknown")

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

            if isinstance(result, ProbeResult):
                result.duration_ms = duration_ms
                if not result.probe_type:
                    result.probe_type = probe_type

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

            if probe_type == "secondary":
                return None
            raise

    tasks = [_run_single_probe(primary_plugin, meta, 1, "primary")]
    for idx, (sec_type, sec_plugin) in enumerate(secondary_plugins, start=2):
        tasks.append(_run_single_probe(sec_plugin, meta, idx, "secondary"))

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[InvestigationResult] = []
    for i, raw in enumerate(raw_results):
        if isinstance(raw, BaseException):
            if i == 0:
                raise raw
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
