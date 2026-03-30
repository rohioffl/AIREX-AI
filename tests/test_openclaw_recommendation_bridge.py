"""Focused tests for OpenClaw-backed recommendation generation."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from airex_core.core.openclaw_recommendation_bridge import OpenClawRecommendationBridge
from airex_core.models.evidence import Evidence
from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.incident import Incident
from airex_core.services import confidence_validator
from airex_core.services import recommendation_service


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_openclaw_recommendation_bridge_parses_response():
    bridge = OpenClawRecommendationBridge()

    payload = {
        "id": "resp_123",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": """```json
{
  "root_cause": "High CPU driven by runaway Java process",
  "proposed_action": "kill_process",
  "risk_level": "MED",
  "confidence": 0.84,
  "summary": "Kill the runaway Java process on checkout.",
  "rationale": "Targeted remediation with lower blast radius than restart.",
  "blast_radius": "single_instance"
}
```""",
                    }
                ],
            }
        ],
    }

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=_MockResponse(payload))):
        recommendation = await bridge.generate_recommendation(
            alert_type="cpu_high",
            evidence="[cpu_diagnostics] Overall CPU Usage: 96%",
            severity="HIGH",
            context="Similar incident resolved by kill_process",
        )

    assert recommendation is not None
    assert recommendation.proposed_action == "kill_process"
    assert recommendation.risk_level.value == "MED"
    assert recommendation.summary == "Kill the runaway Java process on checkout."


@pytest.mark.asyncio
async def test_recommendation_service_uses_openclaw_before_litellm(monkeypatch):
    incident = Incident(
        tenant_id=uuid.uuid4(),
        alert_type="cpu_high",
        severity=SeverityLevel.HIGH,
        title="High CPU on checkout-api",
    )
    incident.id = uuid.uuid4()
    incident.state = IncidentState.RECOMMENDATION_READY
    incident.meta = {}
    evidence = Evidence(
        tenant_id=incident.tenant_id,
        incident_id=incident.id,
        tool_name="openclaw",
        raw_output="High CPU driven by PID 1325 (java -jar app.jar)",
    )
    evidence.id = uuid.uuid4()
    incident.evidence = [evidence]

    session = AsyncMock()
    session.flush = AsyncMock()

    monkeypatch.setattr(recommendation_service.settings, "OPENCLAW_ENABLED", True)
    monkeypatch.setattr(recommendation_service, "flag_modified", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        recommendation_service,
        "build_structured_context",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        recommendation_service,
        "_get_confidence_adjustment",
        AsyncMock(return_value=0.0),
    )
    monkeypatch.setattr(
        recommendation_service.openclaw_recommendation_bridge,
        "generate_recommendation",
        AsyncMock(
            return_value=SimpleNamespace(
                root_cause="High CPU driven by PID 1325 (java -jar app.jar)",
                proposed_action="kill_process",
                risk_level=SimpleNamespace(value="MED"),
                confidence=0.85,
                action_type="execute_fix",
                action_id="kill_process",
                target="smoke-host",
                params={"pid": 1325},
                reason="Target the runaway process directly.",
                summary="Kill the runaway Java process on smoke-host.",
                root_cause_category="resource_exhaustion",
                contributing_factors=["runaway process"],
                reasoning_chain=[],
                rationale="Most targeted action available.",
                blast_radius="single_instance",
                alternatives=[],
                evidence_annotations=["PID 1325 at 96% CPU"],
                verification_criteria=["CPU below 70%"],
                model_dump=lambda: {
                    "root_cause": "High CPU driven by PID 1325 (java -jar app.jar)",
                    "proposed_action": "kill_process",
                    "risk_level": "MED",
                    "confidence": 0.85,
                    "action_type": "execute_fix",
                    "action_id": "kill_process",
                    "target": "smoke-host",
                    "params": {"pid": 1325},
                    "reason": "Target the runaway process directly.",
                    "summary": "Kill the runaway Java process on smoke-host.",
                    "root_cause_category": "resource_exhaustion",
                    "contributing_factors": ["runaway process"],
                    "reasoning_chain": [],
                    "rationale": "Most targeted action available.",
                    "blast_radius": "single_instance",
                    "alternatives": [],
                    "evidence_annotations": ["PID 1325 at 96% CPU"],
                    "verification_criteria": ["CPU below 70%"],
                },
            )
        ),
    )
    monkeypatch.setattr(
        recommendation_service.llm_client,
        "generate_recommendation",
        AsyncMock(return_value=None),
    )
    approval_calls = {}

    def _evaluate_approval(**kwargs):
        approval_calls.update(kwargs)
        return SimpleNamespace(
            level=SimpleNamespace(value="operator"),
            reason="Action 'kill_process' requires operator approval",
            confidence_met=True,
            senior_required=False,
            requires_human=True,
        )

    monkeypatch.setattr(recommendation_service, "evaluate_approval", _evaluate_approval)
    monkeypatch.setattr(
        recommendation_service,
        "check_policy",
        lambda *_args, **_kwargs: (True, ""),
    )
    monkeypatch.setattr(
        recommendation_service,
        "emit_recommendation_ready",
        AsyncMock(),
    )
    monkeypatch.setattr(
        recommendation_service,
        "transition_state",
        AsyncMock(),
    )
    monkeypatch.setattr(
        confidence_validator,
        "validate_confidence",
        AsyncMock(
            return_value={
                "valid": True,
                "warning": None,
                "kg_resolution_count": 2,
                "confidence_breakdown": {
                    "model_confidence": 0.85,
                    "evidence_strength_score": 0.8,
                    "tool_grounding_score": 0.75,
                    "kg_match_score": 0.67,
                    "hallucination_penalty": 0.0,
                    "composite_confidence": 0.817,
                    "warning": "",
                },
                "grounding_summary": "2 evidence source(s) considered; grounding checks passed",
            }
        ),
    )

    await recommendation_service.generate_recommendation(session, incident)

    recommendation_service.openclaw_recommendation_bridge.generate_recommendation.assert_awaited_once()
    recommendation_service.llm_client.generate_recommendation.assert_not_awaited()
    assert incident.meta["recommendation_contract"]["action_id"] == "kill_process"
    assert incident.meta["recommendation"]["proposed_action"] == "kill_process"
    assert incident.meta["recommendation_contract"]["confidence_breakdown"]["composite_confidence"] == 0.817
    assert incident.meta["_approval_confidence"] == 0.817
    assert approval_calls["confidence"] == 0.817
