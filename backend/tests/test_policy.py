"""Tests for action policy engine."""

import pytest

from app.core.policy import (
    ACTION_POLICIES,
    check_policy,
    requires_approval,
)
from app.models.enums import RiskLevel


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
