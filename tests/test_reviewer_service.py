"""Tests for Reviewer Agent — Phase 6 Operational Polish."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airex_core.models.enums import RiskLevel, SeverityLevel
from airex_core.services.reviewer_service import _extract_verdict, run_reviewer_agent


def _make_incident() -> MagicMock:
    inc = MagicMock()
    inc.id = uuid.uuid4()
    inc.tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    inc.alert_type = "high_cpu"
    inc.severity = SeverityLevel.HIGH
    inc.title = "High CPU on web-01"
    return inc


def _make_recommendation(risk_level: RiskLevel = RiskLevel.HIGH) -> MagicMock:
    rec = MagicMock()
    rec.proposed_action = "restart_service"
    rec.risk_level = risk_level
    rec.confidence = 0.88
    rec.root_cause = "CPU spike due to runaway process"
    rec.rationale = "Restarting will clear the runaway process"
    return rec


class TestExtractVerdict:
    def test_agree_extracted(self):
        assert _extract_verdict("The recommendation looks good. AGREE with the plan.") == "AGREE"

    def test_caution_extracted(self):
        assert _extract_verdict("I have concerns. CAUTION advised.") == "CAUTION"

    def test_disagree_extracted(self):
        assert _extract_verdict("This is wrong. DISAGREE with this approach.") == "DISAGREE"

    def test_disagree_takes_priority_over_agree(self):
        """DISAGREE should be extracted before AGREE if both present."""
        text = "I AGREE with the diagnosis but DISAGREE with the fix."
        assert _extract_verdict(text) == "DISAGREE"

    def test_caution_takes_priority_over_agree(self):
        """CAUTION should be extracted before AGREE if both present."""
        text = "I AGREE on root cause but CAUTION on the action."
        assert _extract_verdict(text) == "CAUTION"

    def test_case_insensitive(self):
        assert _extract_verdict("verdict: agree") == "AGREE"
        assert _extract_verdict("verdict: caution") == "CAUTION"
        assert _extract_verdict("verdict: disagree") == "DISAGREE"

    def test_no_keyword_returns_unknown(self):
        assert _extract_verdict("This is just some text without keywords.") == "UNKNOWN"

    def test_empty_string_returns_unknown(self):
        assert _extract_verdict("") == "UNKNOWN"


class TestRunReviewerAgent:
    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        """When REVIEWER_AGENT_ENABLED=False, returns None without LLM call."""
        incident = _make_incident()
        rec = _make_recommendation(RiskLevel.HIGH)

        with patch("airex_core.services.reviewer_service.settings") as mock_settings:
            mock_settings.REVIEWER_AGENT_ENABLED = False
            result = await run_reviewer_agent(incident, rec)

        assert result is None

    @pytest.mark.asyncio
    async def test_low_risk_returns_none(self):
        """Only HIGH risk triggers reviewer — LOW risk should return None."""
        incident = _make_incident()
        rec = _make_recommendation(RiskLevel.LOW)

        with patch("airex_core.services.reviewer_service.settings") as mock_settings:
            mock_settings.REVIEWER_AGENT_ENABLED = True
            result = await run_reviewer_agent(incident, rec)

        assert result is None

    @pytest.mark.asyncio
    async def test_med_risk_returns_none(self):
        """MED risk should not trigger reviewer."""
        incident = _make_incident()
        rec = _make_recommendation(RiskLevel.MED)

        with patch("airex_core.services.reviewer_service.settings") as mock_settings:
            mock_settings.REVIEWER_AGENT_ENABLED = True
            result = await run_reviewer_agent(incident, rec)

        assert result is None

    @pytest.mark.asyncio
    async def test_high_risk_triggers_llm(self):
        """HIGH risk with enabled reviewer should call LLM and return result."""
        incident = _make_incident()
        rec = _make_recommendation(RiskLevel.HIGH)

        mock_client = AsyncMock()
        mock_client.generate_text = AsyncMock(
            return_value="CONCERNS: none\nALTERNATIVES: none\nVERDICT: AGREE with the approach."
        )

        with patch("airex_core.services.reviewer_service.settings") as mock_settings, \
             patch("airex_core.services.reviewer_service.LLMClient", return_value=mock_client):
            mock_settings.REVIEWER_AGENT_ENABLED = True
            result = await run_reviewer_agent(incident, rec)

        assert result is not None
        assert result["verdict"] == "AGREE"
        assert "raw_text" in result
        assert result["proposed_action"] == "restart_service"
        assert result["risk_level"] == RiskLevel.HIGH.value

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        """LLM exception should be caught and return None."""
        incident = _make_incident()
        rec = _make_recommendation(RiskLevel.HIGH)

        mock_client = AsyncMock()
        mock_client.generate_text = AsyncMock(side_effect=Exception("LLM timeout"))

        with patch("airex_core.services.reviewer_service.settings") as mock_settings, \
             patch("airex_core.services.reviewer_service.LLMClient", return_value=mock_client):
            mock_settings.REVIEWER_AGENT_ENABLED = True
            result = await run_reviewer_agent(incident, rec)

        assert result is None

    @pytest.mark.asyncio
    async def test_llm_returns_none_returns_none(self):
        """If LLM returns None (circuit open), reviewer returns None."""
        incident = _make_incident()
        rec = _make_recommendation(RiskLevel.HIGH)

        mock_client = AsyncMock()
        mock_client.generate_text = AsyncMock(return_value=None)

        with patch("airex_core.services.reviewer_service.settings") as mock_settings, \
             patch("airex_core.services.reviewer_service.LLMClient", return_value=mock_client):
            mock_settings.REVIEWER_AGENT_ENABLED = True
            result = await run_reviewer_agent(incident, rec)

        assert result is None

    @pytest.mark.asyncio
    async def test_caution_verdict_extracted(self):
        """CAUTION verdict should be correctly parsed from LLM output."""
        incident = _make_incident()
        rec = _make_recommendation(RiskLevel.HIGH)

        mock_client = AsyncMock()
        mock_client.generate_text = AsyncMock(
            return_value="There are issues. VERDICT: CAUTION — monitor closely before approving."
        )

        with patch("airex_core.services.reviewer_service.settings") as mock_settings, \
             patch("airex_core.services.reviewer_service.LLMClient", return_value=mock_client):
            mock_settings.REVIEWER_AGENT_ENABLED = True
            result = await run_reviewer_agent(incident, rec)

        assert result is not None
        assert result["verdict"] == "CAUTION"

    @pytest.mark.asyncio
    async def test_result_contains_expected_keys(self):
        """Result dict must have verdict, raw_text, proposed_action, risk_level."""
        incident = _make_incident()
        rec = _make_recommendation(RiskLevel.HIGH)

        mock_client = AsyncMock()
        mock_client.generate_text = AsyncMock(return_value="AGREE with the plan.")

        with patch("airex_core.services.reviewer_service.settings") as mock_settings, \
             patch("airex_core.services.reviewer_service.LLMClient", return_value=mock_client):
            mock_settings.REVIEWER_AGENT_ENABLED = True
            result = await run_reviewer_agent(incident, rec)

        assert result is not None
        assert set(result.keys()) == {"verdict", "raw_text", "proposed_action", "risk_level"}
