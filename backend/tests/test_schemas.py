"""Tests for Pydantic schema validation."""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.incident import ApproveRequest, IncidentCreatedResponse, IncidentListItem
from app.schemas.recommendation import Recommendation
from app.schemas.webhook import Site24x7Payload, GenericWebhookPayload
from app.models.enums import RiskLevel


class TestRecommendationSchema:
    def test_valid_recommendation(self):
        rec = Recommendation(
            root_cause="High CPU",
            proposed_action="restart_service",
            risk_level=RiskLevel.MED,
            confidence=0.85,
        )
        assert rec.confidence == 0.85

    def test_confidence_too_high(self):
        with pytest.raises(ValidationError):
            Recommendation(
                root_cause="test",
                proposed_action="restart_service",
                risk_level=RiskLevel.LOW,
                confidence=1.5,
            )

    def test_confidence_too_low(self):
        with pytest.raises(ValidationError):
            Recommendation(
                root_cause="test",
                proposed_action="restart_service",
                risk_level=RiskLevel.LOW,
                confidence=-0.1,
            )

    def test_confidence_boundary_values(self):
        rec_low = Recommendation(
            root_cause="test", proposed_action="x",
            risk_level=RiskLevel.LOW, confidence=0.0,
        )
        rec_high = Recommendation(
            root_cause="test", proposed_action="x",
            risk_level=RiskLevel.LOW, confidence=1.0,
        )
        assert rec_low.confidence == 0.0
        assert rec_high.confidence == 1.0


class TestApproveRequest:
    def test_valid_request(self):
        req = ApproveRequest(action="restart_service", idempotency_key="abc123")
        assert req.action == "restart_service"

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            ApproveRequest(action="restart_service")


class TestSite24x7Payload:
    def test_valid_payload(self):
        payload = Site24x7Payload(
            monitor_name="web-01",
            status="DOWN",
            monitor_type="URL",
        )
        assert payload.monitor_name == "web-01"

    def test_extra_fields_allowed(self):
        payload = Site24x7Payload(
            monitor_name="web-01",
            status="DOWN",
            custom_field="extra",
        )
        assert payload.model_dump()["custom_field"] == "extra"


class TestGenericWebhookPayload:
    def test_valid_payload(self):
        payload = GenericWebhookPayload(
            alert_type="cpu_high",
            resource_id="server-01",
            title="High CPU on server-01",
        )
        assert payload.severity == "MEDIUM"

    def test_custom_severity(self):
        payload = GenericWebhookPayload(
            alert_type="disk_full",
            resource_id="db-01",
            title="Disk full",
            severity="CRITICAL",
        )
        assert payload.severity == "CRITICAL"
