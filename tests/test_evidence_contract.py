"""Tests for EvidenceContract schema validation (preserved from test_openclaw_bridge.py)."""

from airex_core.schemas.evidence import EvidenceContract


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
