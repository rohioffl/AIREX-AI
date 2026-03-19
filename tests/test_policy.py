"""Tests for action policy engine."""

import pytest

from airex_core.core.policy import (
    ACTION_POLICIES,
    ActionBounds,
    ActionPolicy,
    ApprovalDecision,
    ApprovalLevel,
    check_bounds,
    check_policy,
    check_scope,
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
        """restart_service allows up to HIGH risk."""
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
        """clear_logs allows up to MED risk."""
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

    def test_clear_logs_requires_approval(self):
        """All actions require approval — no auto-approve path."""
        assert requires_approval("clear_logs") is True

    def test_scale_instances_requires_approval(self):
        assert requires_approval("scale_instances") is True

    def test_flush_cache_requires_approval(self):
        assert requires_approval("flush_cache") is True

    def test_toggle_feature_flag_requires_approval(self):
        assert requires_approval("toggle_feature_flag") is True

    def test_unknown_action_defaults_to_requiring_approval(self):
        assert requires_approval("unknown_action") is True


class TestGetPolicy:
    def test_known_action_returns_policy(self):
        policy = get_policy("restart_service")
        assert policy is not None
        assert policy.action_type == "restart_service"
        assert policy.requires_senior_approval is False
        assert policy.max_allowed_risk == RiskLevel.HIGH

    def test_senior_action_returns_policy(self):
        policy = get_policy("scale_instances")
        assert policy is not None
        assert policy.requires_senior_approval is True

    def test_unknown_action_returns_none(self):
        assert get_policy("nuke_everything") is None

    def test_low_risk_action_returns_policy(self):
        policy = get_policy("clear_logs")
        assert policy is not None
        assert policy.requires_senior_approval is False


class TestApprovalLevelEnum:
    def test_operator_value(self):
        assert ApprovalLevel.OPERATOR == "operator"

    def test_senior_value(self):
        assert ApprovalLevel.SENIOR == "senior"

    def test_no_auto_level(self):
        assert not hasattr(ApprovalLevel, "AUTO")


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
            requires_human=True,
            level=ApprovalLevel.OPERATOR,
            reason="operator required",
        )
        with pytest.raises(AttributeError):
            d.requires_human = False  # type: ignore[misc]


class TestEvaluateApproval:
    """Tests for the approval policy engine."""

    # ── Gate 1: Unknown action ──────────────────────────────────

    def test_unknown_action_requires_operator(self):
        decision = evaluate_approval("nonexistent_action", confidence=0.99)
        assert decision.requires_human is True
        assert decision.level == ApprovalLevel.OPERATOR
        assert "No policy" in decision.reason

    def test_unknown_action_high_confidence_still_blocked(self):
        """Even 100% confidence cannot bypass human approval for unknown actions."""
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
        """All senior-gated actions should return SENIOR level."""
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
        """Senior gate fires regardless of confidence level."""
        for conf in [0.0, 0.5, 0.85, 1.0]:
            decision = evaluate_approval("drain_node", confidence=conf)
            assert decision.requires_human is True
            assert decision.level == ApprovalLevel.SENIOR

    # ── Default: operator approval ───────────────────────────────

    def test_operator_approval_required(self):
        decision = evaluate_approval(
            "restart_service", confidence=0.99, risk_level=RiskLevel.LOW
        )
        assert decision.requires_human is True
        assert decision.level == ApprovalLevel.OPERATOR

    def test_high_confidence_still_requires_operator(self):
        """No confidence score can bypass human approval."""
        for action in ["clear_logs", "flush_cache", "toggle_feature_flag"]:
            decision = evaluate_approval(action, confidence=1.0, risk_level=RiskLevel.LOW)
            assert decision.requires_human is True, f"{action} should require human approval"
            assert decision.level == ApprovalLevel.OPERATOR

    def test_all_actions_require_human(self):
        """Every registered action must always require human approval."""
        for action_type in ACTION_POLICIES:
            decision = evaluate_approval(action_type, confidence=1.0, risk_level=RiskLevel.LOW)
            assert decision.requires_human is True, f"{action_type} bypassed human approval"

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

    def test_default_confidence_is_zero(self):
        """When confidence is not provided, it defaults to 0.0 (still requires approval)."""
        decision = evaluate_approval("clear_logs")
        assert decision.requires_human is True


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

    def test_no_auto_approve_field(self):
        """ActionPolicy no longer has auto_approve — human approval is always required."""
        for policy in ACTION_POLICIES.values():
            assert not hasattr(policy, "auto_approve"), (
                f"{policy.action_type} should not have auto_approve field"
            )

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

    def test_all_policies_have_bounds(self):
        """Every policy must carry an ActionBounds instance."""
        for action, policy in ACTION_POLICIES.items():
            assert isinstance(policy.bounds, ActionBounds), (
                f"{action} missing ActionBounds"
            )

    def test_all_policies_have_required_scope_fields(self):
        """required_scope_fields must be a frozenset (empty is fine)."""
        for action, policy in ACTION_POLICIES.items():
            assert isinstance(policy.required_scope_fields, frozenset), (
                f"{action}.required_scope_fields is not a frozenset"
            )

    def test_scale_instances_bounds(self):
        """scale_instances must cap at 20 replicas with a 5-minute cooldown."""
        policy = ACTION_POLICIES["scale_instances"]
        assert policy.bounds.max_replicas == 20
        assert policy.bounds.cooldown_seconds == 300

    def test_drain_node_required_fields(self):
        """drain_node requires _instance_id in scope."""
        policy = ACTION_POLICIES["drain_node"]
        assert "_instance_id" in policy.required_scope_fields

    def test_block_ip_required_fields(self):
        """block_ip requires _target_ip in scope."""
        policy = ACTION_POLICIES["block_ip"]
        assert "_target_ip" in policy.required_scope_fields


class TestCheckBounds:
    """Phase 3a: Action bounds enforcement."""

    def test_unknown_action_passes(self):
        ok, reason = check_bounds("unknown_action", {})
        assert ok is True

    def test_no_replica_param_passes(self):
        """scale_instances without replica params passes (bounds can't apply)."""
        ok, reason = check_bounds("scale_instances", {"_cloud": "aws"})
        assert ok is True

    def test_replica_within_cap_passes(self):
        ok, reason = check_bounds("scale_instances", {"desired_capacity": 10})
        assert ok is True

    def test_replica_at_cap_passes(self):
        ok, reason = check_bounds("scale_instances", {"desired_capacity": 20})
        assert ok is True

    def test_replica_over_cap_blocked(self):
        ok, reason = check_bounds("scale_instances", {"desired_capacity": 21})
        assert ok is False
        assert "21" in reason
        assert "20" in reason

    def test_target_replicas_param_also_checked(self):
        ok, reason = check_bounds("scale_instances", {"target_replicas": 50})
        assert ok is False

    def test_no_max_replicas_action_ignores_desired_capacity(self):
        """restart_service has no max_replicas — desired_capacity is irrelevant."""
        ok, _ = check_bounds("restart_service", {"desired_capacity": 999})
        assert ok is True

    def test_env_guard_no_restriction_passes(self):
        """Actions without allowed_environments pass any environment."""
        ok, _ = check_bounds("restart_service", {"_environment": "dev"})
        assert ok is True

    def test_env_guard_allowed_env_passes(self):
        """If an action has allowed_environments, a matching env passes."""
        # Build a test policy with env restriction inline
        from airex_core.core.policy import ActionBounds
        bounds = ActionBounds(allowed_environments=frozenset({"prod", "staging"}))
        policy = ActionPolicy(
            action_type="test_action",
            requires_senior_approval=False,
            max_allowed_risk=RiskLevel.HIGH,
            bounds=bounds,
        )
        # Inject temporarily
        ACTION_POLICIES["test_action"] = policy
        try:
            ok, _ = check_bounds("test_action", {"_environment": "prod"})
            assert ok is True
        finally:
            del ACTION_POLICIES["test_action"]

    def test_env_guard_disallowed_env_blocked(self):
        """Environment not in allowed list is rejected."""
        bounds = ActionBounds(allowed_environments=frozenset({"prod", "staging"}))
        policy = ActionPolicy(
            action_type="test_action2",
            requires_senior_approval=False,
            max_allowed_risk=RiskLevel.HIGH,
            bounds=bounds,
        )
        ACTION_POLICIES["test_action2"] = policy
        try:
            ok, reason = check_bounds("test_action2", {"_environment": "dev"})
            assert ok is False
            assert "dev" in reason
        finally:
            del ACTION_POLICIES["test_action2"]

    def test_empty_env_with_restriction_passes(self):
        """Missing _environment key is not blocked (env unknown — allow by default)."""
        bounds = ActionBounds(allowed_environments=frozenset({"prod"}))
        policy = ActionPolicy(
            action_type="test_action3",
            requires_senior_approval=False,
            max_allowed_risk=RiskLevel.HIGH,
            bounds=bounds,
        )
        ACTION_POLICIES["test_action3"] = policy
        try:
            ok, _ = check_bounds("test_action3", {})
            assert ok is True
        finally:
            del ACTION_POLICIES["test_action3"]


class TestCheckScope:
    """Phase 3c: Action scoping / required targeting fields."""

    def test_unknown_action_passes(self):
        ok, reason = check_scope("unknown_action", {})
        assert ok is True

    def test_action_with_no_required_fields_passes(self):
        ok, reason = check_scope("restart_service", {})
        assert ok is True

    def test_drain_node_missing_instance_id_blocked(self):
        ok, reason = check_scope("drain_node", {})
        assert ok is False
        assert "_instance_id" in reason

    def test_drain_node_with_instance_id_passes(self):
        ok, reason = check_scope("drain_node", {"_instance_id": "i-abc123"})
        assert ok is True

    def test_block_ip_missing_target_ip_blocked(self):
        ok, reason = check_scope("block_ip", {"_instance_id": "i-abc123"})
        assert ok is False
        assert "_target_ip" in reason

    def test_block_ip_with_target_ip_passes(self):
        ok, reason = check_scope("block_ip", {"_target_ip": "10.0.0.5"})
        assert ok is True

    def test_all_non_scoped_actions_pass_empty_params(self):
        """Actions with no required_scope_fields must never block on empty params."""
        no_scope_actions = [
            a for a, p in ACTION_POLICIES.items()
            if not p.required_scope_fields
        ]
        for action in no_scope_actions:
            ok, _ = check_scope(action, {})
            assert ok is True, f"{action} should pass scope check with empty params"
