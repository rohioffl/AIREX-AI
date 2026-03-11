"""
Tests for alternative-action fallback service (Phase 3 ARE).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airex_core.models.enums import IncidentState, RiskLevel, SeverityLevel
from airex_core.services.fallback_service import attempt_fallback, select_next_alternative


def _make_incident(
    state=IncidentState.FAILED_VERIFICATION,
    meta=None,
    verification_retry_count=3,
):
    """Create a mock incident for testing."""
    incident = MagicMock()
    incident.id = uuid.uuid4()
    incident.tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    incident.state = state
    incident.severity = SeverityLevel.HIGH
    incident.title = "Test incident"
    incident.alert_type = "high_cpu"
    incident.meta = meta or {}
    incident.verification_retry_count = verification_retry_count
    incident.investigation_retry_count = 0
    incident.execution_retry_count = 0
    incident.created_at = datetime.now(timezone.utc)
    incident.updated_at = datetime.now(timezone.utc)
    incident.evidence = []
    incident.state_transitions = []
    incident.executions = []
    return incident


# ── select_next_alternative ──────────────────────────────────────


class TestSelectNextAlternative:
    def test_returns_first_valid_alternative(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [
                    {"action": "scale_up_instances", "confidence": 0.7, "risk_level": "LOW", "rationale": "Scale first"},
                    {"action": "restart_container", "confidence": 0.6, "risk_level": "MED", "rationale": "Restart container"},
                ],
            },
        })
        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
            "restart_container": MagicMock(),
        }):
            result = select_next_alternative(incident)
        assert result is not None
        assert result["action"] == "scale_up_instances"

    def test_skips_already_tried_actions(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [
                    {"action": "scale_up_instances", "confidence": 0.7, "risk_level": "LOW", "rationale": "Scale first"},
                    {"action": "restart_container", "confidence": 0.6, "risk_level": "MED", "rationale": "Restart container"},
                ],
            },
            "_fallback_history": [
                {"action": "scale_up_instances", "status": "verification_failed"},
            ],
        })
        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
            "restart_container": MagicMock(),
        }):
            result = select_next_alternative(incident)
        assert result is not None
        assert result["action"] == "restart_container"

    def test_returns_none_when_all_tried(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [
                    {"action": "scale_up_instances", "confidence": 0.7, "risk_level": "LOW", "rationale": "Scale"},
                ],
            },
            "_fallback_history": [
                {"action": "scale_up_instances", "status": "verification_failed"},
            ],
        })
        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
        }):
            result = select_next_alternative(incident)
        assert result is None

    def test_returns_none_when_no_alternatives(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [],
            },
        })
        result = select_next_alternative(incident)
        assert result is None

    def test_returns_none_when_no_recommendation(self):
        incident = _make_incident(meta={})
        result = select_next_alternative(incident)
        assert result is None

    def test_skips_unregistered_actions(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [
                    {"action": "unknown_action", "confidence": 0.9, "risk_level": "LOW", "rationale": "Unknown"},
                    {"action": "scale_up_instances", "confidence": 0.7, "risk_level": "LOW", "rationale": "Scale"},
                ],
            },
        })
        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
        }):
            result = select_next_alternative(incident)
        assert result is not None
        assert result["action"] == "scale_up_instances"

    def test_skips_same_as_original_action(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [
                    {"action": "restart_service", "confidence": 0.9, "risk_level": "LOW", "rationale": "Same action"},
                    {"action": "scale_up_instances", "confidence": 0.7, "risk_level": "LOW", "rationale": "Scale"},
                ],
            },
        })
        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
        }):
            result = select_next_alternative(incident)
        assert result is not None
        assert result["action"] == "scale_up_instances"

    def test_respects_max_fallback_limit(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [
                    {"action": "scale_up_instances", "confidence": 0.7, "risk_level": "LOW", "rationale": "Scale"},
                    {"action": "restart_container", "confidence": 0.6, "risk_level": "MED", "rationale": "Container"},
                    {"action": "clear_cache", "confidence": 0.5, "risk_level": "LOW", "rationale": "Cache"},
                ],
            },
            "_fallback_history": [
                {"action": "scale_up_instances", "status": "verification_failed"},
                {"action": "restart_container", "status": "verification_failed"},
            ],
        })
        with patch("airex_core.services.fallback_service.settings") as mock_settings:
            mock_settings.MAX_FALLBACK_ALTERNATIVES = 2
            with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
                "restart_service": MagicMock(),
                "clear_cache": MagicMock(),
            }):
                result = select_next_alternative(incident)
        assert result is None  # max 2 fallbacks already used

    def test_returns_none_with_none_meta(self):
        incident = _make_incident(meta=None)
        result = select_next_alternative(incident)
        assert result is None


# ── attempt_fallback ─────────────────────────────────────────────


class TestAttemptFallback:
    @pytest.mark.asyncio
    async def test_initiates_fallback_with_human_approval(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "confidence": 0.9,
                "risk_level": "LOW",
                "alternatives": [
                    {"action": "scale_up_instances", "confidence": 0.6, "risk_level": "MED", "rationale": "Scale up"},
                ],
            },
        })
        session = AsyncMock()

        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
        }), patch("airex_core.services.fallback_service.transition_state", new_callable=AsyncMock) as mock_ts, \
             patch("airex_core.services.fallback_service.check_policy", return_value=(True, "ok")), \
             patch("airex_core.services.fallback_service.evaluate_approval") as mock_eval:
            # Below threshold → requires human
            mock_eval.return_value = MagicMock(
                level=MagicMock(value="operator"),
                reason="Confidence 0.60 below threshold",
                confidence_met=False,
                senior_required=False,
                requires_human=True,
            )
            result = await attempt_fallback(
                session, incident, "restart_service", "Verification check returned False"
            )

        assert result is True
        assert incident.meta["_is_fallback"] is True
        assert incident.meta["_fallback_from"] == "restart_service"
        assert incident.meta["recommendation"]["proposed_action"] == "scale_up_instances"
        assert incident.meta["_original_proposed_action"] == "restart_service"
        assert len(incident.meta["_fallback_history"]) == 1
        assert incident.meta["_fallback_history"][0]["action"] == "restart_service"
        assert incident.meta["_fallback_history"][0]["status"] == "verification_failed"
        assert incident.verification_retry_count == 0
        # Should transition to AWAITING_APPROVAL only (human required)
        mock_ts.assert_called_once()
        assert mock_ts.call_args[0][2] == IncidentState.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_auto_approves_high_confidence_fallback(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "confidence": 0.9,
                "risk_level": "LOW",
                "alternatives": [
                    {"action": "scale_up_instances", "confidence": 0.95, "risk_level": "LOW", "rationale": "Scale up"},
                ],
            },
        })
        session = AsyncMock()

        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
        }), patch("airex_core.services.fallback_service.transition_state", new_callable=AsyncMock) as mock_ts, \
             patch("airex_core.services.fallback_service.check_policy", return_value=(True, "ok")), \
             patch("airex_core.services.fallback_service.evaluate_approval") as mock_eval, \
             patch("airex_core.services.fallback_service.settings") as mock_settings:
            mock_settings.MAX_FALLBACK_ALTERNATIVES = 2
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_eval.return_value = MagicMock(
                level=MagicMock(value="auto"),
                reason="Auto-approved: high confidence",
                confidence_met=True,
                senior_required=False,
                requires_human=False,
            )

            with patch("arq.create_pool", new_callable=AsyncMock) as mock_pool_factory:
                mock_pool = AsyncMock()
                mock_pool_factory.return_value = mock_pool
                result = await attempt_fallback(
                    session, incident, "restart_service", "Verification failed"
                )

        assert result is True
        # Should transition AWAITING_APPROVAL then EXECUTING (auto-approve)
        assert mock_ts.call_count == 2
        calls = mock_ts.call_args_list
        assert calls[0][0][2] == IncidentState.AWAITING_APPROVAL
        assert calls[1][0][2] == IncidentState.EXECUTING

    @pytest.mark.asyncio
    async def test_returns_false_when_no_alternatives(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [],
            },
        })
        session = AsyncMock()

        result = await attempt_fallback(
            session, incident, "restart_service", "Verification failed"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_skips_policy_rejected_and_tries_next(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [
                    {"action": "dangerous_action", "confidence": 0.9, "risk_level": "HIGH", "rationale": "Dangerous"},
                    {"action": "safe_action", "confidence": 0.7, "risk_level": "LOW", "rationale": "Safe"},
                ],
            },
        })
        session = AsyncMock()

        call_count = 0

        def mock_check_policy(action, risk):
            nonlocal call_count
            call_count += 1
            if action == "dangerous_action":
                return (False, "Policy blocked: too dangerous")
            return (True, "ok")

        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "dangerous_action": MagicMock(),
            "safe_action": MagicMock(),
        }), patch("airex_core.services.fallback_service.transition_state", new_callable=AsyncMock), \
             patch("airex_core.services.fallback_service.check_policy", side_effect=mock_check_policy), \
             patch("airex_core.services.fallback_service.evaluate_approval") as mock_eval:
            mock_eval.return_value = MagicMock(
                level=MagicMock(value="operator"),
                reason="Requires approval",
                confidence_met=False,
                senior_required=False,
                requires_human=True,
            )
            result = await attempt_fallback(
                session, incident, "restart_service", "Verification failed"
            )

        assert result is True
        assert incident.meta["recommendation"]["proposed_action"] == "safe_action"
        # First entry is the policy-rejected one, second is the original failed action
        history = incident.meta["_fallback_history"]
        assert len(history) == 2
        assert history[0]["action"] == "dangerous_action"
        assert history[0]["status"] == "policy_rejected"
        assert history[1]["action"] == "restart_service"
        assert history[1]["status"] == "verification_failed"

    @pytest.mark.asyncio
    async def test_preserves_original_action_on_second_fallback(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "scale_up_instances",  # already swapped from original
                "alternatives": [
                    {"action": "scale_up_instances", "confidence": 0.7, "risk_level": "LOW", "rationale": "Scale"},
                    {"action": "restart_container", "confidence": 0.6, "risk_level": "MED", "rationale": "Container"},
                ],
            },
            "_original_proposed_action": "restart_service",  # original is preserved
            "_fallback_history": [
                {"action": "restart_service", "status": "verification_failed"},
            ],
        })
        session = AsyncMock()

        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
            "restart_container": MagicMock(),
        }), patch("airex_core.services.fallback_service.transition_state", new_callable=AsyncMock), \
             patch("airex_core.services.fallback_service.check_policy", return_value=(True, "ok")), \
             patch("airex_core.services.fallback_service.evaluate_approval") as mock_eval:
            mock_eval.return_value = MagicMock(
                level=MagicMock(value="operator"),
                reason="Requires approval",
                confidence_met=False,
                senior_required=False,
                requires_human=True,
            )
            result = await attempt_fallback(
                session, incident, "scale_up_instances", "Verification failed"
            )

        assert result is True
        # Original should still be "restart_service", not overwritten
        assert incident.meta["_original_proposed_action"] == "restart_service"
        assert incident.meta["recommendation"]["proposed_action"] == "restart_container"

    @pytest.mark.asyncio
    async def test_handles_invalid_risk_level_gracefully(self):
        incident = _make_incident(meta={
            "recommendation": {
                "proposed_action": "restart_service",
                "alternatives": [
                    {"action": "scale_up_instances", "confidence": 0.7, "risk_level": "UNKNOWN", "rationale": "Scale"},
                ],
            },
        })
        session = AsyncMock()

        with patch("airex_core.services.fallback_service.ACTION_REGISTRY", {
            "restart_service": MagicMock(),
            "scale_up_instances": MagicMock(),
        }), patch("airex_core.services.fallback_service.transition_state", new_callable=AsyncMock), \
             patch("airex_core.services.fallback_service.check_policy", return_value=(True, "ok")), \
             patch("airex_core.services.fallback_service.evaluate_approval") as mock_eval:
            mock_eval.return_value = MagicMock(
                level=MagicMock(value="operator"),
                reason="Requires approval",
                confidence_met=False,
                senior_required=False,
                requires_human=True,
            )
            result = await attempt_fallback(
                session, incident, "restart_service", "Verification failed"
            )

        assert result is True
        # Should default to MED risk level
        assert incident.meta["recommendation"]["risk_level"] == "MED"


# ── State Machine Transition ─────────────────────────────────────


class TestStateTransitionAllowed:
    def test_failed_verification_to_awaiting_approval_allowed(self):
        from airex_core.core.state_machine import ALLOWED_TRANSITIONS

        allowed = ALLOWED_TRANSITIONS[IncidentState.FAILED_VERIFICATION]
        assert IncidentState.AWAITING_APPROVAL in allowed

    def test_original_transitions_preserved(self):
        from airex_core.core.state_machine import ALLOWED_TRANSITIONS

        allowed = ALLOWED_TRANSITIONS[IncidentState.FAILED_VERIFICATION]
        assert IncidentState.RESOLVED in allowed
        assert IncidentState.FAILED_VERIFICATION in allowed
        assert IncidentState.REJECTED in allowed
