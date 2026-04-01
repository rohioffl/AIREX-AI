"""Tests for the standalone evidence grounding module."""

import uuid
from types import SimpleNamespace

import pytest

from airex_core.core.evidence_grounder import (
    build_fallback_evidence,
    extract_evidence_payload,
    extract_json_text,
    ground_evidence_with_probes,
    parse_evidence_json,
    response_needs_grounding,
)
from airex_core.investigations.base import ProbeCategory, ProbeResult


def _make_incident() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        alert_type="high_cpu",
        title="High CPU on checkout-api",
        raw_alert={"service": "checkout-api"},
        meta={"service_name": "checkout-api"},
    )


class TestResponseNeedsGrounding:
    def test_detects_weak_response(self):
        payload = {
            "summary": "Investigating high CPU usage.",
            "signals": [],
            "root_cause": "Unknown. Requires further investigation.",
            "affected_entities": [],
            "confidence": 0.2,
        }
        assert response_needs_grounding(payload) is True

    def test_accepts_strong_response(self):
        payload = {
            "summary": "CPU saturation isolated to checkout-api pod-123",
            "signals": ["cpu=97%", "queue_depth=high"],
            "root_cause": "Insufficient replicas on checkout-api deployment",
            "affected_entities": ["service:checkout-api", "pod:checkout-api-123"],
            "confidence": 0.88,
        }
        assert response_needs_grounding(payload) is False


class TestGroundEvidenceWithProbes:
    def test_ground_replaces_vague_summary(self):
        incident = _make_incident()
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

        grounded = ground_evidence_with_probes(payload, incident, forensic_results)

        assert grounded["summary"] == "CPU Investigation: checkout-api-01"
        assert grounded["root_cause"] == "High CPU driven by PID 1272 (java -jar checkout.jar)"
        assert grounded["confidence"] == 0.7
        assert grounded["raw_refs"]["forensic_tools"] == ["cpu_diagnostics"]

    def test_ground_replaces_generic_entities(self):
        incident = _make_incident()
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

        grounded = ground_evidence_with_probes(payload, incident, forensic_results)

        assert grounded["summary"] == "CPU Investigation: checkout-api-01"
        assert grounded["root_cause"] == "High CPU driven by PID 1272 (java -jar checkout.jar)"

    def test_ground_replaces_investigating_summary(self):
        incident = _make_incident()
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

        grounded = ground_evidence_with_probes(payload, incident, forensic_results)

        assert grounded["summary"] == "CPU Investigation: checkout-api-01"
        assert grounded["root_cause"] == "High CPU driven by PID 1272 (java -jar checkout.jar)"


class TestBuildFallbackEvidence:
    def test_build_fallback_evidence_from_probes(self):
        incident = _make_incident()
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

        fallback = build_fallback_evidence(incident, forensic_results)

        assert "summary" in fallback
        assert "root_cause" in fallback
        assert "signals" in fallback
        assert "affected_entities" in fallback
        assert fallback["confidence"] == 0.7
        assert "service:checkout-api" in fallback["affected_entities"]


class TestParseEvidenceJson:
    def test_parse_evidence_json_fenced(self):
        payload = extract_evidence_payload(
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

    def test_parse_evidence_json_responses_api(self):
        payload = extract_evidence_payload(
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
