import uuid

from app.models.enums import IncidentState, SeverityLevel
from app.models.incident import Incident
from app.services.incident_embedding_service import build_incident_summary


def _make_incident() -> Incident:
    incident = Incident(
        tenant_id=uuid.uuid4(),
        alert_type="cpu_high",
        severity=SeverityLevel.CRITICAL,
        title="CPU saturation on web-1",
    )
    incident.state = IncidentState.RESOLVED
    return incident


class TestBuildIncidentSummary:
    def test_includes_recommendation_fields(self):
        incident = _make_incident()
        incident.meta = {
            "recommendation": {
                "root_cause": "Runaway process",
                "proposed_action": "restart_service",
                "risk_level": "MED",
                "confidence": 0.82,
            },
            "rag_context": "Scaling guide",
        }

        summary = build_incident_summary(incident)
        assert "restart_service" in summary
        assert "Scaling guide" in summary
        assert "RESOLVED" in summary

    def test_truncates_when_exceeding_limit(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.incident_embedding_service.settings.RAG_INCIDENT_SUMMARY_MAX_CHARS",
            10,
        )
        incident = _make_incident()
        incident.meta = {"recommendation_note": "x" * 100}
        summary = build_incident_summary(incident)
        assert summary.endswith(" …")
