"""Tests for the LangGraph investigation orchestrator."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airex_core.core.investigation_graph import (
    InvestigationState,
    _should_use_cloud_investigation,
    analyze_node,
    build_investigation_graph,
    plan_probes_node,
    resolve_context_node,
    run_investigation_graph,
    store_node,
    _session_var,
    _incident_var,
)
from airex_core.investigations.base import ProbeCategory, ProbeResult
from airex_core.models.enums import IncidentState


def _make_incident(**overrides) -> SimpleNamespace:
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        alert_type="high_cpu",
        title="High CPU on checkout-api",
        raw_alert={"service": "checkout-api"},
        meta={"service_name": "checkout-api"},
        state=IncidentState.RECEIVED,
        evidence=[],
        investigation_retry_count=0,
        severity=SimpleNamespace(value="high"),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _base_state(**overrides) -> InvestigationState:
    defaults: InvestigationState = {
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "incident_id": str(uuid.uuid4()),
        "alert_type": "high_cpu",
        "meta": {"service_name": "checkout-api"},
        "use_cloud": False,
        "primary_plugin": None,
        "secondary_plugins": [],
        "total_probes": 0,
        "all_results": [],
        "anomaly_summary": None,
        "error": None,
        "failed": False,
    }
    defaults.update(overrides)
    return defaults


class TestResolveContext:
    def test_extracts_cloud_target_from_meta(self):
        meta = {"_cloud": "aws", "_instance_id": "i-abc123", "_has_cloud_target": True}
        assert _should_use_cloud_investigation(meta) is True

    def test_no_cloud_target_without_flag(self):
        meta = {"_cloud": "aws", "_instance_id": "i-abc123"}
        assert _should_use_cloud_investigation(meta) is False

    def test_no_cloud_target_without_cloud(self):
        meta = {"_has_cloud_target": True}
        assert _should_use_cloud_investigation(meta) is False


class TestPlanProbes:
    @pytest.mark.asyncio
    async def test_selects_correct_probes_for_known_alert_type(self):
        session = _make_session()
        incident = _make_incident(alert_type="cpu_high")
        state = _base_state(alert_type="cpu_high", meta={"service_name": "checkout-api"})

        token_s = _session_var.set(session)
        token_i = _incident_var.set(incident)
        try:
            result = await plan_probes_node(state)
        finally:
            _session_var.reset(token_s)
            _incident_var.reset(token_i)

        assert result.get("primary_plugin") is not None
        assert result.get("failed") is not True

    @pytest.mark.asyncio
    async def test_fails_for_unknown_alert_type(self):
        session = _make_session()
        incident = _make_incident(alert_type="nonexistent_type_xyz")
        state = _base_state(alert_type="nonexistent_type_xyz")

        token_s = _session_var.set(session)
        token_i = _incident_var.set(incident)
        try:
            with patch(
                "airex_core.core.investigation_graph.transition_state",
                new=AsyncMock(),
            ), patch("airex_core.core.investigation_graph.flag_modified"):
                result = await plan_probes_node(state)
        finally:
            _session_var.reset(token_s)
            _incident_var.reset(token_i)

        assert result.get("failed") is True
        assert "No plugin" in result.get("error", "")


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_runs_anomaly_detection(self):
        probe = ProbeResult(
            tool_name="cpu_diagnostics",
            raw_output="CPU: 96.2%\nDiagnosis: High CPU",
            category=ProbeCategory.SYSTEM,
            probe_type="primary",
            metrics={"cpu_percent": 96.2},
        )
        state = _base_state(all_results=[probe], total_probes=1)

        result = await analyze_node(state)

        assert "anomaly_summary" in result


class TestStore:
    @pytest.mark.asyncio
    async def test_store_persists_evidence_and_meta(self):
        session = _make_session()
        incident = _make_incident()
        probe = ProbeResult(
            tool_name="cpu_diagnostics",
            raw_output="CPU: 96.2%",
            category=ProbeCategory.SYSTEM,
            probe_type="primary",
            metrics={"cpu_percent": 96.2},
        )
        state = _base_state(all_results=[probe])

        token_s = _session_var.set(session)
        token_i = _incident_var.set(incident)
        try:
            with patch("airex_core.core.investigation_graph.Evidence") as MockEvidence, \
                 patch("airex_core.core.investigation_graph.flag_modified"):
                MockEvidence.return_value = SimpleNamespace(id=uuid.uuid4())
                await store_node(state)
        finally:
            _session_var.reset(token_s)
            _incident_var.reset(token_i)

        session.add.assert_called()
        session.flush.assert_awaited()
        assert "probe_results" in (incident.meta or {})


class TestGraphStructure:
    def test_graph_builds_successfully(self):
        graph = build_investigation_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_should_continue_routes_on_failure(self):
        from airex_core.core.investigation_graph import _should_continue

        assert _should_continue({"failed": True}) == "end"
        assert _should_continue({"failed": False}) == "continue"
        assert _should_continue({}) == "continue"


class TestFeatureFlag:
    @pytest.mark.asyncio
    async def test_feature_flag_routes_to_langgraph(self):
        session = _make_session()
        incident = _make_incident()

        with patch(
            "airex_core.services.investigation_service.settings"
        ) as mock_settings, patch(
            "airex_core.core.investigation_graph.run_investigation_graph",
            new=AsyncMock(),
        ) as mock_graph:
            mock_settings.USE_LANGGRAPH_INVESTIGATION = True
            from airex_core.services.investigation_service import run_investigation

            await run_investigation(session, incident)
            mock_graph.assert_awaited_once_with(session, incident)

    @pytest.mark.asyncio
    async def test_feature_flag_routes_to_legacy(self):
        session = _make_session()
        incident = _make_incident()

        with patch(
            "airex_core.services.investigation_service.settings"
        ) as mock_settings, patch(
            "airex_core.services.investigation_service._run_investigation_legacy",
            new=AsyncMock(),
        ) as mock_legacy:
            mock_settings.USE_LANGGRAPH_INVESTIGATION = False
            from airex_core.services.investigation_service import run_investigation

            await run_investigation(session, incident)
            mock_legacy.assert_awaited_once_with(session, incident)
