"""OpenClaw-first investigation flow tests."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.incident import Incident
from airex_core.schemas.openclaw import EvidenceContract
from airex_core.services import investigation_service


def _make_incident() -> Incident:
    incident = Incident(
        tenant_id=uuid.uuid4(),
        alert_type="high_cpu",
        severity=SeverityLevel.HIGH,
        title="High CPU on checkout-api",
    )
    incident.id = uuid.uuid4()
    incident.state = IncidentState.RECEIVED
    incident.meta = {"service_name": "checkout-api"}
    return incident


@pytest.mark.asyncio
async def test_run_investigation_uses_openclaw_and_enqueues_recommendation(monkeypatch):
    incident = _make_incident()
    session = AsyncMock()

    added = []

    def _add(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        added.append(instance)

    session.add = MagicMock(side_effect=_add)
    session.flush = AsyncMock()

    monkeypatch.setattr(
        investigation_service.settings,
        "OPENCLAW_ENABLED",
        True,
    )
    monkeypatch.setattr(
        investigation_service,
        "transition_state",
        AsyncMock(),
    )
    monkeypatch.setattr(
        investigation_service,
        "_enqueue_recommendation",
        AsyncMock(),
    )
    monkeypatch.setattr(
        investigation_service,
        "emit_evidence_added",
        AsyncMock(),
    )
    monkeypatch.setattr(
        investigation_service.knowledge_graph,
        "get_context_for_incident",
        AsyncMock(return_value="Historical context"),
    )
    monkeypatch.setattr(
        investigation_service.knowledge_graph,
        "upsert_node",
        AsyncMock(return_value=SimpleNamespace(entity_id="service:checkout-api")),
    )
    monkeypatch.setattr(
        investigation_service.knowledge_graph,
        "add_edge",
        AsyncMock(),
    )
    monkeypatch.setattr(
        investigation_service.openclaw_bridge,
        "run",
        AsyncMock(
            return_value=EvidenceContract(
                summary="Checkout API is CPU saturated",
                signals=["cpu=97%", "replicas=2"],
                root_cause="Insufficient capacity",
                affected_entities=["service:checkout-api", "pod:checkout-api-123"],
                confidence=0.88,
                raw_refs={"run_id": "oc-123"},
            )
        ),
    )

    await investigation_service.run_investigation(session, incident)

    assert any(getattr(item, "tool_name", None) == "openclaw" for item in added)
    assert incident.meta["openclaw"]["summary"] == "Checkout API is CPU saturated"
    assert incident.meta["openclaw_run"]["agent_fallback_used"] is False
    assert incident.meta["probe_count"] == 1
    investigation_service._enqueue_recommendation.assert_awaited_once()
    transition_calls = investigation_service.transition_state.await_args_list
    assert transition_calls[0].args[2] == IncidentState.INVESTIGATING
    assert transition_calls[1].args[2] == IncidentState.RECOMMENDATION_READY


@pytest.mark.asyncio
async def test_openclaw_bridge_failure_records_run_metadata_before_static_fallback(monkeypatch):
    incident = _make_incident()
    session = AsyncMock()
    session.flush = AsyncMock()
    log = MagicMock()

    monkeypatch.setattr(
        investigation_service.knowledge_graph,
        "get_context_for_incident",
        AsyncMock(return_value="Historical context"),
    )
    monkeypatch.setattr(
        investigation_service.openclaw_bridge,
        "run",
        AsyncMock(side_effect=RuntimeError("gateway timed out")),
    )

    used_openclaw = await investigation_service._run_openclaw_investigation(
        session,
        incident,
        log,
    )

    assert used_openclaw is False
    assert incident.meta["openclaw_run"]["agent_fallback_used"] is True
    assert "gateway timed out" in incident.meta["openclaw_run"]["agent_failure_reason"]
