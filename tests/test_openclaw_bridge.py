"""Tests for OpenClaw bridge contracts and fallback-friendly parsing."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from airex_core.core.investigation_bridge import InvestigationBridge
from airex_core.investigations.base import ProbeCategory, ProbeResult
from airex_core.schemas.openclaw import EvidenceContract


def _make_incident() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        alert_type="high_cpu",
        title="High CPU on checkout-api",
        raw_alert={"service": "checkout-api"},
        meta={"service_name": "checkout-api"},
    )


class TestEvidenceContract:
    def test_normalizes_affected_entities(self):
        contract = EvidenceContract(
            summary="CPU is saturated on checkout-api",
            signals=["cpu=97%", "replicas=2"],
            root_cause="Insufficient capacity",
            affected_entities=[" checkout-api ", "pod:checkout-api-123 "],
            confidence=0.82,
        )

        assert contract.affected_entities == [
            "service:checkout-api",
            "pod:checkout-api-123",
        ]


class TestInvestigationBridge:
    @pytest.mark.asyncio
    async def test_run_parses_gateway_response(self):
        incident = _make_incident()
        bridge = InvestigationBridge()

        with patch.object(
            bridge,
            "_call_openclaw",
            AsyncMock(
                return_value={
                    "summary": "CPU saturation isolated to checkout-api",
                    "signals": ["cpu=97%", "queue_depth=high"],
                    "root_cause": "Insufficient replicas",
                    "affected_entities": ["checkout-api", "pod:checkout-api-123"],
                    "confidence": 0.88,
                    "raw_refs": {"agent_run_id": "run-123"},
                }
            ),
        ), patch.object(
            bridge,
            "_gather_fallback_forensic_results",
            AsyncMock(),
        ):
            result = await bridge.run(incident, kg_context="Known similar incident")

        assert result.summary == "CPU saturation isolated to checkout-api"
        assert result.affected_entities == [
            "service:checkout-api",
            "pod:checkout-api-123",
        ]
        assert result.raw_refs == {
            "agent_run_id": "run-123",
            "agent_fallback_used": False,
        }

    @pytest.mark.asyncio
    async def test_run_accepts_nested_gateway_payload(self):
        incident = _make_incident()
        bridge = InvestigationBridge()

        with patch.object(
            bridge,
            "_call_openclaw",
            AsyncMock(
                return_value={
                    "evidence": {
                        "summary": "Nested payload",
                        "signals": ["signal-a"],
                        "root_cause": "Nested cause",
                        "affected_entities": ["checkout-api"],
                        "confidence": 0.7,
                    }
                }
            ),
        ), patch.object(
            bridge,
            "_gather_fallback_forensic_results",
            AsyncMock(),
        ):
            result = await bridge.run(incident)

        assert result.summary == "Nested payload"
        assert result.affected_entities == ["service:checkout-api"]

    def test_extracts_evidence_from_chat_completion(self):
        bridge = InvestigationBridge()

        payload = bridge._extract_evidence_payload(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"CPU saturation isolated","signals":["cpu=97%"],'
                                '"root_cause":"Replica imbalance",'
                                '"affected_entities":["checkout-api"],'
                                '"confidence":0.81}'
                            )
                        }
                    }
                ]
            }
        )

        assert payload["summary"] == "CPU saturation isolated"
        assert payload["affected_entities"] == ["checkout-api"]

    def test_extracts_evidence_from_fenced_json_chat_completion(self):
        bridge = InvestigationBridge()

        payload = bridge._extract_evidence_payload(
            {
                "choices": [
                    {
                        "message": {
                            "content": """```json
{
  "summary": "High CPU utilization detected",
  "signals": ["cpu_high"],
  "root_cause": "Unknown. Requires further investigation.",
  "affected_entities": ["Unknown"],
  "confidence": 0.5
}
```"""
                        }
                    }
                ]
            }
        )

        assert payload["summary"] == "High CPU utilization detected"
        assert payload["affected_entities"] == ["Unknown"]

    def test_extracts_evidence_from_openresponses_output_text(self):
        bridge = InvestigationBridge()

        payload = bridge._extract_evidence_payload(
            {
                "id": "resp_123",
                "output_text": (
                    '{"summary":"CPU saturation isolated","signals":["cpu=97%"],'
                    '"root_cause":"Replica imbalance",'
                    '"affected_entities":["checkout-api"],'
                    '"confidence":0.81}'
                ),
                "output": [],
            }
        )

        assert payload["summary"] == "CPU saturation isolated"
        assert payload["affected_entities"] == ["checkout-api"]

    def test_extracts_evidence_from_openresponses_message_output(self):
        bridge = InvestigationBridge()

        payload = bridge._extract_evidence_payload(
            {
                "id": "resp_456",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": """```json
{
  "summary": "High CPU utilization detected",
  "signals": ["cpu_high"],
  "root_cause": "Unknown. Requires further investigation.",
  "affected_entities": ["Unknown"],
  "confidence": 0.5
}
```""",
                            }
                        ],
                    }
                ],
            }
        )

        assert payload["summary"] == "High CPU utilization detected"
        assert payload["affected_entities"] == ["Unknown"]

    def test_grounding_uses_forensic_probe_when_model_answer_is_vague(self):
        incident = _make_incident()
        bridge = InvestigationBridge()

        payload = {
            "summary": "High CPU detected. Further investigation is required.",
            "signals": ["cpu_high"],
            "root_cause": "Unknown. Requires further investigation.",
            "affected_entities": [],
            "confidence": 0.2,
            "raw_refs": {},
        }
        forensic_results = [
            ProbeResult(
                tool_name="cpu_diagnostics",
                raw_output=(
                    "=== CPU Investigation: checkout-api-01 ===\n"
                    "Overall CPU Usage: 96.2%\n"
                    "Load Average (1m/5m/15m): 4.8 / 4.2 / 3.1\n"
                    "Diagnosis: High CPU driven by PID 1272 (java -jar checkout.jar)\n"
                ),
                category=ProbeCategory.SYSTEM,
                probe_type="primary",
                metrics={"cpu_percent": 96.2},
            )
        ]

        grounded = bridge._ground_payload_with_forensics(payload, incident, forensic_results)

        assert grounded["summary"] == "CPU Investigation: checkout-api-01"
        assert grounded["root_cause"] == "High CPU driven by PID 1272 (java -jar checkout.jar)"
        assert "process:java -jar checkout.jar".lower() in grounded["affected_entities"]
        assert grounded["confidence"] == 0.7
        assert grounded["raw_refs"]["forensic_tools"] == ["cpu_diagnostics"]

    def test_grounding_replaces_generic_entities_with_concrete_forensic_entities(self):
        incident = _make_incident()
        bridge = InvestigationBridge()

        payload = {
            "summary": "Investigation initiated for high CPU.",
            "signals": ["cpu_high"],
            "root_cause": "Pending investigation.",
            "affected_entities": ["service:checkout service"],
            "confidence": 0.3,
            "raw_refs": {},
        }
        forensic_results = [
            ProbeResult(
                tool_name="cpu_diagnostics",
                raw_output=(
                    "=== CPU Investigation: checkout-api-01 ===\n"
                    "Diagnosis: High CPU driven by PID 1272 (java -jar checkout.jar)\n"
                ),
                category=ProbeCategory.SYSTEM,
                probe_type="primary",
                metrics={"cpu_percent": 96.2},
            )
        ]

        grounded = bridge._ground_payload_with_forensics(payload, incident, forensic_results)

        assert grounded["summary"] == "CPU Investigation: checkout-api-01"
        assert grounded["root_cause"] == "High CPU driven by PID 1272 (java -jar checkout.jar)"
        assert "process:java -jar checkout.jar".lower() in grounded["affected_entities"]

    def test_grounding_replaces_investigating_summary_with_forensic_summary(self):
        incident = _make_incident()
        bridge = InvestigationBridge()

        payload = {
            "summary": "Investigating high CPU usage on host checkout-api-01.",
            "signals": ["cpu_high"],
            "root_cause": "Awaiting data from diagnostics tools.",
            "affected_entities": ["host:checkout-api-01"],
            "confidence": 0.4,
            "raw_refs": {},
        }
        forensic_results = [
            ProbeResult(
                tool_name="cpu_diagnostics",
                raw_output=(
                    "=== CPU Investigation: checkout-api-01 ===\n"
                    "Overall CPU Usage: 96.2%\n"
                    "Diagnosis: High CPU driven by PID 1272 (java -jar checkout.jar)\n"
                ),
                category=ProbeCategory.SYSTEM,
                probe_type="primary",
                metrics={"cpu_percent": 96.2},
            )
        ]

        grounded = bridge._ground_payload_with_forensics(payload, incident, forensic_results)

        assert grounded["summary"] == "CPU Investigation: checkout-api-01"
        assert grounded["root_cause"] == "High CPU driven by PID 1272 (java -jar checkout.jar)"

    @pytest.mark.asyncio
    async def test_invoke_openclaw_tool_parses_probe_result(self):
        bridge = InvestigationBridge()

        with patch("httpx.AsyncClient.post", new=AsyncMock()) as mock_post:
            mock_post.return_value = AsyncMock(
                raise_for_status=lambda: None,
                json=lambda: {
                    "ok": True,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": """```json
{
  "tool_name": "cpu_diagnostics",
  "raw_output": "Diagnosis: High CPU driven by PID 1254 (java -jar app.jar)",
  "category": "system",
  "metrics": {"cpu_percent": 93.9},
  "anomalies": [],
  "duration_ms": 0,
  "probe_type": "primary"
}
```""",
                            }
                        ]
                    },
                },
            )

            result = await bridge._invoke_openclaw_tool(
                "run_host_diagnostics",
                args={
                    "tenant_id": "00000000-0000-0000-0000-000000000000",
                    "incident_meta": {"host": "checkout-api-01"},
                    "alert_type": "cpu_high",
                },
            )

        assert result is not None
        assert result.tool_name == "cpu_diagnostics"
        assert result.metrics["cpu_percent"] == 93.9

    @pytest.mark.asyncio
    async def test_gather_fallback_forensic_results_prefers_openclaw_tool_runtime(self):
        incident = _make_incident()
        bridge = InvestigationBridge()

        openclaw_probe = ProbeResult(
            tool_name="cpu_diagnostics",
            raw_output="Diagnosis: High CPU driven by PID 1254 (java -jar app.jar)",
            category=ProbeCategory.SYSTEM,
            probe_type="primary",
            metrics={"cpu_percent": 93.9},
        )

        with patch.object(
            bridge,
            "_invoke_openclaw_tool",
            AsyncMock(side_effect=[openclaw_probe, None]),
        ) as invoke_tool, patch.object(
            bridge,
            "_run_primary_forensic_probe",
            AsyncMock(),
        ) as run_primary:
            results = await bridge._gather_fallback_forensic_results(incident)

        assert [result.tool_name for result in results] == ["cpu_diagnostics"]
        assert invoke_tool.await_count >= 1
        run_primary.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_includes_incident_context_from_tool(self):
        incident = _make_incident()
        bridge = InvestigationBridge()

        with patch.object(
            bridge,
            "_read_incident_context",
            AsyncMock(return_value={"pattern_context": "Seen before"}),
        ), patch.object(
            bridge,
            "_gather_fallback_forensic_results",
            AsyncMock(return_value=[]),
        ), patch.object(
            bridge,
            "_call_openclaw",
            AsyncMock(
                return_value={
                    "summary": "CPU saturation isolated",
                    "signals": ["cpu=97%"],
                    "root_cause": "Replica imbalance",
                    "affected_entities": ["checkout-api"],
                    "confidence": 0.81,
                }
            ),
        ) as call_openclaw:
            await bridge.run(incident)

        payload = call_openclaw.await_args.args[0]
        assert payload["incident_context"] == {"pattern_context": "Seen before"}

    @pytest.mark.asyncio
    async def test_run_does_not_prefetch_fallback_forensics_when_agent_response_is_strong(self):
        incident = _make_incident()
        bridge = InvestigationBridge()

        with patch.object(
            bridge,
            "_call_openclaw",
            AsyncMock(
                return_value=(
                    {
                        "summary": "CPU saturation isolated to checkout-api",
                        "signals": ["cpu=97%", "queue_depth=high"],
                        "root_cause": "Insufficient replicas on checkout-api",
                        "affected_entities": ["service:checkout-api", "pod:checkout-api-123"],
                        "confidence": 0.88,
                        "raw_refs": {"agent_run_id": "run-123"},
                    },
                    bridge._extract_run_metadata(
                        {
                            "output": [
                                {
                                    "type": "tool_call",
                                    "name": "run_host_diagnostics",
                                    "id": "tool-1",
                                    "status": "completed",
                                }
                            ]
                        }
                    ),
                )
            ),
        ), patch.object(
            bridge,
            "_gather_fallback_forensic_results",
            AsyncMock(return_value=[]),
        ) as gather_fallback:
            result = await bridge.run(incident)

        gather_fallback.assert_not_awaited()
        assert result.raw_refs["agent_used_tools"] == ["run_host_diagnostics"]
        assert result.raw_refs["agent_fallback_used"] is False

    @pytest.mark.asyncio
    async def test_run_uses_fallback_forensics_only_when_agent_response_is_weak(self):
        incident = _make_incident()
        bridge = InvestigationBridge()
        forensic_results = [
            ProbeResult(
                tool_name="cpu_diagnostics",
                raw_output=(
                    "=== CPU Investigation: checkout-api-01 ===\n"
                    "Diagnosis: High CPU driven by PID 1272 (java -jar checkout.jar)\n"
                ),
                category=ProbeCategory.SYSTEM,
                probe_type="primary",
                metrics={"cpu_percent": 96.2},
            )
        ]

        with patch.object(
            bridge,
            "_call_openclaw",
            AsyncMock(
                return_value=(
                    {
                        "summary": "Investigating high CPU usage on host checkout-api-01.",
                        "signals": ["cpu_high"],
                        "root_cause": "Awaiting data from diagnostics tools.",
                        "affected_entities": ["unknown"],
                        "confidence": 0.4,
                        "raw_refs": {},
                    },
                    bridge._extract_run_metadata({"output": []}),
                )
            ),
        ), patch.object(
            bridge,
            "_gather_fallback_forensic_results",
            AsyncMock(return_value=forensic_results),
        ) as gather_fallback:
            result = await bridge.run(incident)

        gather_fallback.assert_awaited_once()
        assert result.summary == "CPU Investigation: checkout-api-01"
        assert result.raw_refs["forensic_tools"] == ["cpu_diagnostics"]
        assert result.raw_refs["agent_fallback_used"] is True
        assert result.raw_refs["agent_failure_reason"] == "weak_or_under_grounded_agent_response"
