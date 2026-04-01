"""Tests for Confidence Validator — Phase 6 Operational Polish."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from airex_core.services.confidence_validator import validate_confidence


def _make_incident(alert_type: str = "high_cpu") -> MagicMock:
    inc = MagicMock()
    inc.id = uuid.uuid4()
    inc.tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    inc.alert_type = alert_type
    inc.meta = {}
    inc.evidence = []
    return inc


def _make_session(kg_count: int = 0) -> AsyncMock:
    session = AsyncMock()
    row = (kg_count,) if kg_count > 0 else None

    mock_result = MagicMock()
    mock_result.fetchone.return_value = row
    session.execute = AsyncMock(return_value=mock_result)
    return session


class TestValidateConfidence:
    @pytest.mark.asyncio
    async def test_low_confidence_skips_kg_check(self):
        """Confidence below threshold should pass without querying KG."""
        session = _make_session(kg_count=0)
        incident = _make_incident()

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="restart_service",
            confidence=0.5,
        )

        assert result["valid"] is True
        assert result["warning"] is None
        assert result["kg_resolution_count"] is None
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_at_threshold_still_triggers_kg_check(self):
        """Confidence exactly at threshold should trigger KG lookup."""
        session = _make_session(kg_count=1)
        incident = _make_incident()

        await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="restart_service",
            confidence=0.85,
        )

        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_high_confidence_with_kg_history_passes(self):
        """High confidence backed by KG history should be valid."""
        session = _make_session(kg_count=5)
        incident = _make_incident()

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="restart_service",
            confidence=0.92,
        )

        assert result["valid"] is True
        assert result["warning"] is None
        assert result["kg_resolution_count"] == 5

    @pytest.mark.asyncio
    async def test_high_confidence_no_kg_history_flagged(self):
        """High confidence without KG history should return warning."""
        session = _make_session(kg_count=0)
        incident = _make_incident()

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="restart_service",
            confidence=0.92,
        )

        assert result["valid"] is False
        assert result["warning"] is not None
        assert "restart_service" in result["warning"]
        assert result["kg_resolution_count"] == 0

    @pytest.mark.asyncio
    async def test_warning_mentions_confidence_percentage(self):
        """Warning text should mention the confidence as a percentage."""
        session = _make_session(kg_count=0)
        incident = _make_incident()

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="clear_logs",
            confidence=0.90,
        )

        assert result["warning"] is not None
        assert "90%" in result["warning"]

    @pytest.mark.asyncio
    async def test_warning_mentions_alert_type(self):
        """Warning text should reference the incident alert type."""
        session = _make_session(kg_count=0)
        incident = _make_incident(alert_type="disk_full")

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="clear_logs",
            confidence=0.95,
        )

        assert result["warning"] is not None
        assert "disk_full" in result["warning"]

    @pytest.mark.asyncio
    async def test_kg_lookup_failure_treated_as_valid(self):
        """If KG query raises, validator should not block (returns valid=True)."""
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        incident = _make_incident()

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="restart_service",
            confidence=0.95,
        )

        assert result["valid"] is True
        assert result["warning"] is None

    @pytest.mark.asyncio
    async def test_returns_kg_count_of_zero_when_no_row(self):
        """When KG has no row for the pair, count should be 0."""
        session = _make_session(kg_count=0)
        incident = _make_incident()

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="scale_instances",
            confidence=0.95,
        )

        assert result["kg_resolution_count"] == 0

    @pytest.mark.asyncio
    async def test_result_always_has_required_keys(self):
        """Core keys and composite confidence metadata must always be present."""
        session = _make_session(kg_count=0)
        incident = _make_incident()

        for confidence in [0.5, 0.85, 0.99]:
            result = await validate_confidence(
                session=session,
                incident=incident,
                proposed_action="restart_service",
                confidence=confidence,
            )
            assert "valid" in result
            assert "warning" in result
            assert "kg_resolution_count" in result
            assert "confidence_breakdown" in result
            assert "grounding_summary" in result
            assert "composite_confidence" in result["confidence_breakdown"]

    @pytest.mark.asyncio
    async def test_composite_confidence_penalizes_high_confidence_without_kg_support(self):
        session = _make_session(kg_count=0)
        incident = _make_incident()

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="restart_service",
            confidence=0.92,
        )

        breakdown = result["confidence_breakdown"]
        assert breakdown["model_confidence"] == 0.92
        assert breakdown["composite_confidence"] < breakdown["model_confidence"]
        assert breakdown["hallucination_penalty"] > 0

    @pytest.mark.asyncio
    async def test_composite_confidence_rewards_grounded_investigation_evidence(self):
        session = _make_session(kg_count=2)
        incident = _make_incident()
        incident.meta = {
            "investigation": {
                "affected_entities": ["host:web-01", "service:checkout"],
                "raw_refs": {
                    "forensic_tools": ["cpu_diagnostics", "log_analysis"],
                    "cpu_diagnostics": "PID 1325 java -jar app.jar at 96% CPU",
                },
            }
        }
        incident.evidence = [
            MagicMock(tool_name="investigation", raw_output="CPU investigation complete"),
            MagicMock(tool_name="cpu_diagnostics", raw_output="Overall CPU Usage: 96%"),
        ]

        result = await validate_confidence(
            session=session,
            incident=incident,
            proposed_action="kill_process",
            confidence=0.88,
        )

        breakdown = result["confidence_breakdown"]
        assert breakdown["tool_grounding_score"] > 0.5
        assert breakdown["evidence_strength_score"] > 0.5
        assert breakdown["kg_match_score"] > 0
        assert "forensic tool" in result["grounding_summary"]
