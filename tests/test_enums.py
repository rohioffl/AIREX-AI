"""Tests for enum definitions — verifying completeness and consistency."""

import pytest

from airex_core.models.enums import ExecutionStatus, IncidentState, RiskLevel, SeverityLevel


class TestIncidentState:
    def test_has_11_states(self):
        assert len(IncidentState) == 11

    def test_all_expected_states_exist(self):
        expected = {
            "RECEIVED",
            "INVESTIGATING",
            "RECOMMENDATION_READY",
            "AWAITING_APPROVAL",
            "EXECUTING",
            "VERIFYING",
            "RESOLVED",
            "FAILED_ANALYSIS",
            "FAILED_EXECUTION",
            "FAILED_VERIFICATION",
            "REJECTED",
        }
        actual = {s.value for s in IncidentState}
        assert actual == expected

    def test_states_are_str_enum(self):
        assert isinstance(IncidentState.RECEIVED, str)
        assert IncidentState.RECEIVED == "RECEIVED"


class TestSeverityLevel:
    def test_has_4_levels(self):
        assert len(SeverityLevel) == 4

    def test_ordering(self):
        expected = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        actual = [s.value for s in SeverityLevel]
        assert actual == expected


class TestExecutionStatus:
    def test_has_4_statuses(self):
        assert len(ExecutionStatus) == 4

    def test_all_statuses(self):
        expected = {"PENDING", "RUNNING", "COMPLETED", "FAILED"}
        actual = {s.value for s in ExecutionStatus}
        assert actual == expected


class TestRiskLevel:
    def test_has_3_levels(self):
        assert len(RiskLevel) == 3

    def test_values(self):
        assert RiskLevel.LOW == "LOW"
        assert RiskLevel.MED == "MED"
        assert RiskLevel.HIGH == "HIGH"
