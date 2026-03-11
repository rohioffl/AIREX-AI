"""Tests for action policy engine."""

import pytest
from unittest.mock import patch

from airex_core.core.policy import (
    ACTION_POLICIES,
    ApprovalDecision,
    ApprovalLevel,
    check_policy,
    evaluate_approval,
    get_policy,
    requires_approval,
)
from airex_core.models.enums import RiskLevel


class TestCheckPolicy:
    def test_known_action_within_risk(self):
        allowed, reason = check_policy("restart_service", RiskLevel.LOW)
        assert allowed is True
        assert reason == "allowed"

    def test_known_action_at_max_risk(self):
        allowed, reason = check_policy("restart_service", RiskLevel.MED)
        assert allowed is True

    def test_known_action_at_high_risk(self):
        """restart_service now allows up to HIGH risk (updated policy)."""
        allowed, reason = check_policy("restart_service", RiskLevel.HIGH)
        assert allowed is True

    def test_unknown_action_rejected(self):
        allowed, reason = check_policy("delete_database", RiskLevel.LOW)
        assert allowed is False
        assert "No policy" in reason

    def test_clear_logs_low_risk_allowed(self):
        allowed, _ = check_policy("clear_logs", RiskLevel.LOW)
        assert allowed is True

    def test_clear_logs_med_risk_allowed(self):
        """clear_logs allows up to MED risk (updated policy)."""
        allowed, _ = check_policy("clear_logs", RiskLevel.MED)
        assert allowed is True

    def test_clear_logs_high_risk_rejected(self):
        allowed, _ = check_policy("clear_logs", RiskLevel.HIGH)
        assert allowed is False

    def test_scale_instances_any_risk_allowed(self):
        """scale_instances allows up to HIGH risk."""
        allowed, _ = check_policy("scale_instances", RiskLevel.HIGH)
        assert allowed is True

    def test_scale_instances_low_risk_allowed(self):
        allowed, _ = check_policy("scale_instances", RiskLevel.LOW)
        assert allowed is True


class TestRequiresApproval:
    def test_restart_service_requires_approval(self):
        assert requires_approval("restart_service") is True

    def test_clear_logs_auto_approved(self):
        assert requires_approval("clear_logs") is False

    def test_scale_instances_requires_approval(self):
        assert requires_approval("scale_instances") is True

    def test_unknown_action_defaults_to_requiring_approval(self):
        assert requires_approval("unknown_action") is True


class TestGetPolicy:
    def test_known_action_returns_policy(self):
        policy = get_policy("restart_service")
        assert policy is not None
        assert policy.action_type == "restart_service"
        assert policy.auto_approve is False
        assert policy.requires_senior_approval is False
        assert policy.max_allowed_risk == RiskLevel.HIGH

    def test_senior_action_returns_policy(self):
        policy = get_policy("scale_instances")
        assert policy is not None
        assert policy.requires_senior_approval is True

    def test_unknown_action_returns_none(self):
        assert get_policy("nuke_everything") is None

    def test_auto_approve_action_returns_policy(self):
        policy = get_policy("clear_logs")
        assert policy is not None
        assert policy.auto_approve is True
        assert policy.requires_senior_approval is False


class TestApprovalLevelEnum:
    def test_auto_value(self):
        assert ApprovalLevel.AUTO == "auto"

    def test_operator_value(self):
        assert ApprovalLevel.OPERATOR == "operator"

    def test_senior_value(self):
        assert ApprovalLevel.SENIOR == "senior"

    def test_is_string_enum(self):
        assert isinstance(ApprovalLevel.AUTO, str)


class TestApprovalDecision:
    def test_defaults(self):
        d = ApprovalDecision(
            requires_human=True,
            level=ApprovalLevel.OPERATOR,
            reason="test",
        )
        assert d.confidence_met is True
        assert d.senior_required is False

    def test_frozen(self):
        d = ApprovalDecision(
            requires_human=False,
            level=ApprovalLevel.AUTO,
            reason="auto",
        )
        with pytest.raises(AttributeError):
            d.requires_human = True  # type: ignore[misc]


class TestEvaluateApproval:
    """Tests for the confidence-gated approval policy engine."""

    # ── Gate 1: Unknown action ──────────────────────────────────

    def test_unknown_action_requires_operator(self):
        decision = evaluate_approval("nonexistent_action", confidence=0.99)
        assert decision.requires_human is True
        assert decision.level == ApprovalLevel.OPERATOR
        assert "No policy" in decision.reason

    def test_unknown_action_high_confidence_still_blocked(self):
        """Even 100% confidence cannot auto-approve an unknown action."""
        decision = evaluate_approval("wipe_prod_db", confidence=1.0)
        assert decision.requires_human is True

    # ── Gate 2: Senior approval ─────────────────────────────────

    def test_senior_action_requires_senior(self):
        """Actions with requires_senior_approval=True go to SENIOR level."""
        decision = evaluate_approval(
            "scale_instances", confidence=0.99, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is True
        assert decision.level == ApprovalLevel.SENIOR
        assert decision.senior_required is True
        assert "senior" in decision.reason.lower()

    def test_all_senior_actions_flagged(self):
        """All 5 senior-gated actions should return SENIOR level."""
        senior_actions = [
            "scale_instances",
            "rotate_credentials",
            "rollback_deployment",
            "drain_node",
            "block_ip",
        ]
        for action in senior_actions:
            decision = evaluate_approval(action, confidence=1.0)
            assert decision.level == ApprovalLevel.SENIOR, f"{action} should be SENIOR"
            assert decision.senior_required is True, f"{action} senior_required should be True"

    def test_senior_action_ignores_confidence(self):
        """Senior gate fires before confidence check — any confidence level blocked."""
        for conf in [0.0, 0.5, 0.85, 1.0]:
            decision = evaluate_approval("drain_node", confidence=conf)
            assert decision.requires_human is True
            assert decision.level == ApprovalLevel.SENIOR

    # ── Gate 3: Non-auto-approve actions ────────────────────────

    def test_non_auto_approve_requires_operator(self):
        """Actions with auto_approve=False need operator approval."""
        decision = evaluate_approval(
            "restart_service", confidence=0.99, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is True
        assert decision.level == ApprovalLevel.OPERATOR
        assert "auto_approve=False" in decision.reason

    def test_kill_process_requires_operator(self):
        decision = evaluate_approval("kill_process", confidence=0.95)
        assert decision.requires_human is True
        assert decision.level == ApprovalLevel.OPERATOR

    # ── Gate 4: Confidence threshold ────────────────────────────

    def test_auto_approve_below_threshold_requires_operator(self):
        """Auto-approve eligible action with low confidence needs operator."""
        decision = evaluate_approval(
            "clear_logs", confidence=0.5, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is True
        assert decision.level == ApprovalLevel.OPERATOR
        assert decision.confidence_met is False
        assert "below threshold" in decision.reason.lower()

    def test_auto_approve_at_threshold_passes(self):
        """Confidence exactly at threshold should pass (>= check)."""
        decision = evaluate_approval(
            "clear_logs", confidence=0.85, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is False
        assert decision.level == ApprovalLevel.AUTO
        assert decision.confidence_met is True

    def test_auto_approve_above_threshold_passes(self):
        decision = evaluate_approval(
            "flush_cache", confidence=0.95, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is False
        assert decision.level == ApprovalLevel.AUTO

    def test_confidence_zero_always_blocked(self):
        decision = evaluate_approval(
            "clear_logs", confidence=0.0, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is True
        assert decision.confidence_met is False

    # ── Gate 5: HIGH risk block ─────────────────────────────────

    def test_high_risk_auto_approve_blocked(self):
        """HIGH risk actions cannot auto-approve even with high confidence."""
        # clear_logs max_allowed_risk is MED, so HIGH would fail check_policy
        # toggle_feature_flag max_allowed_risk is LOW, so HIGH would fail too
        # We need an action that has auto_approve=True AND max_allowed_risk=HIGH
        # None exist currently, so we test with a mock
        with patch.dict(
            "airex_core.core.policy.ACTION_POLICIES",
            {
                "test_action": type(
                    "ActionPolicy",
                    (),
                    {
                        "action_type": "test_action",
                        "auto_approve": True,
                        "requires_senior_approval": False,
                        "max_allowed_risk": RiskLevel.HIGH,
                    },
                )()
            },
        ):
            decision = evaluate_approval(
                "test_action", confidence=0.99, risk_level=RiskLevel.HIGH
            )
            assert decision.requires_human is True
            assert decision.level == ApprovalLevel.OPERATOR
            assert "HIGH risk" in decision.reason

    def test_high_risk_block_disabled(self):
        """When AUTO_APPROVAL_BLOCK_HIGH_RISK=False, HIGH risk can auto-approve."""
        with patch.dict(
            "airex_core.core.policy.ACTION_POLICIES",
            {
                "test_action": type(
                    "ActionPolicy",
                    (),
                    {
                        "action_type": "test_action",
                        "auto_approve": True,
                        "requires_senior_approval": False,
                        "max_allowed_risk": RiskLevel.HIGH,
                    },
                )()
            },
        ):
            with patch("airex_core.core.config.settings") as mock_settings:
                mock_settings.AUTO_APPROVAL_CONFIDENCE_THRESHOLD = 0.85
                mock_settings.AUTO_APPROVAL_BLOCK_HIGH_RISK = False
                decision = evaluate_approval(
                    "test_action", confidence=0.99, risk_level=RiskLevel.HIGH
                )
                assert decision.requires_human is False
                assert decision.level == ApprovalLevel.AUTO

    # ── Auto-approve happy path ─────────────────────────────────

    def test_auto_approve_clear_logs(self):
        """clear_logs with high confidence and LOW risk auto-approves."""
        decision = evaluate_approval(
            "clear_logs", confidence=0.90, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is False
        assert decision.level == ApprovalLevel.AUTO
        assert decision.confidence_met is True
        assert decision.senior_required is False

    def test_auto_approve_toggle_feature_flag(self):
        decision = evaluate_approval(
            "toggle_feature_flag", confidence=0.95, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is False
        assert decision.level == ApprovalLevel.AUTO

    def test_auto_approve_flush_cache(self):
        decision = evaluate_approval(
            "flush_cache", confidence=0.86, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is False
        assert decision.level == ApprovalLevel.AUTO

    # ── Threshold configuration ─────────────────────────────────

    def test_custom_threshold(self):
        """Changing threshold affects decision."""
        with patch("airex_core.core.config.settings") as mock_settings:
            mock_settings.AUTO_APPROVAL_CONFIDENCE_THRESHOLD = 0.95
            mock_settings.AUTO_APPROVAL_BLOCK_HIGH_RISK = True
            decision = evaluate_approval(
                "clear_logs", confidence=0.90, risk_level=RiskLevel.LOW
            )
            assert decision.requires_human is True
            assert decision.confidence_met is False

    def test_threshold_at_one_disables_auto_approval(self):
        """Setting threshold to 1.0 effectively disables auto-approval."""
        with patch("airex_core.core.config.settings") as mock_settings:
            mock_settings.AUTO_APPROVAL_CONFIDENCE_THRESHOLD = 1.0
            mock_settings.AUTO_APPROVAL_BLOCK_HIGH_RISK = True
            decision = evaluate_approval(
                "clear_logs", confidence=0.99, risk_level=RiskLevel.LOW
            )
            assert decision.requires_human is True
            assert decision.confidence_met is False

    # ── Default confidence value ────────────────────────────────

    def test_default_confidence_is_zero(self):
        """When confidence is not provided, it defaults to 0.0."""
        decision = evaluate_approval("clear_logs")
        assert decision.requires_human is True
        assert decision.confidence_met is False

    # ── Edge cases ──────────────────────────────────────────────

    def test_decision_reason_always_set(self):
        """Every decision path must produce a non-empty reason."""
        test_cases = [
            ("unknown_action", 0.5, RiskLevel.LOW),
            ("scale_instances", 0.9, RiskLevel.LOW),
            ("restart_service", 0.9, RiskLevel.LOW),
            ("clear_logs", 0.5, RiskLevel.LOW),
            ("clear_logs", 0.95, RiskLevel.LOW),
        ]
        for action, conf, risk in test_cases:
            decision = evaluate_approval(action, confidence=conf, risk_level=risk)
            assert decision.reason, f"Empty reason for {action}"
            assert len(decision.reason) > 5, f"Too short reason for {action}"


class TestPolicyCoverage:
    """Ensure all 12 registered actions have consistent policies."""

    def test_all_actions_have_policies(self):
        expected_actions = [
            "restart_service",
            "clear_logs",
            "scale_instances",
            "kill_process",
            "flush_cache",
            "rotate_credentials",
            "rollback_deployment",
            "resize_disk",
            "drain_node",
            "toggle_feature_flag",
            "restart_container",
            "block_ip",
        ]
        for action in expected_actions:
            assert action in ACTION_POLICIES, f"Missing policy for {action}"

    def test_auto_approve_actions(self):
        """Only specific low-risk actions should be auto-approvable."""
        auto_actions = [
            a for a, p in ACTION_POLICIES.items() if p.auto_approve
        ]
        assert set(auto_actions) == {"clear_logs", "flush_cache", "toggle_feature_flag"}

    def test_senior_actions(self):
        """Only high-impact actions should require senior approval."""
        senior_actions = [
            a for a, p in ACTION_POLICIES.items() if p.requires_senior_approval
        ]
        assert set(senior_actions) == {
            "scale_instances",
            "rotate_credentials",
            "rollback_deployment",
            "drain_node",
            "block_ip",
        }
