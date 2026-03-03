"""Tests for resolution outcome tracking service."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import IncidentState, SeverityLevel
from app.services.resolution_service import (
    ResolutionType,
    build_resolution_summary,
    compute_resolution_duration,
    determine_resolution_type,
    record_resolution,
)


def _make_incident(**overrides):
    """Create a mock incident with sensible defaults."""
    inc = MagicMock()
    inc.id = uuid.uuid4()
    inc.tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    inc.state = IncidentState.RESOLVED
    inc.severity = SeverityLevel.HIGH
    inc.title = "Test incident"
    inc.alert_type = "cpu_high"
    inc.created_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    inc.updated_at = datetime.now(timezone.utc)
    inc.meta = {}
    inc.investigation_retry_count = 0
    inc.execution_retry_count = 0
    inc.verification_retry_count = 0
    inc.resolution_type = None
    inc.resolution_summary = None
    inc.resolution_duration_seconds = None
    inc.resolved_at = None
    inc.feedback_score = None
    inc.feedback_note = None
    for k, v in overrides.items():
        setattr(inc, k, v)
    return inc


class TestResolutionType:
    def test_constants(self):
        assert ResolutionType.AUTO == "auto"
        assert ResolutionType.OPERATOR == "operator"
        assert ResolutionType.SENIOR == "senior"
        assert ResolutionType.REJECTED == "rejected"
        assert ResolutionType.FAILED == "failed"
        assert ResolutionType.MANUAL == "manual"


class TestDetermineResolutionType:
    def test_rejected_state(self):
        inc = _make_incident(state=IncidentState.REJECTED)
        assert determine_resolution_type(inc) == "rejected"

    def test_failed_execution_state(self):
        inc = _make_incident(state=IncidentState.FAILED_EXECUTION)
        assert determine_resolution_type(inc) == "failed"

    def test_failed_verification_state(self):
        inc = _make_incident(state=IncidentState.FAILED_VERIFICATION)
        assert determine_resolution_type(inc) == "failed"

    def test_auto_approval_level(self):
        inc = _make_incident(
            state=IncidentState.RESOLVED,
            meta={"_approval_level": "auto"},
        )
        assert determine_resolution_type(inc) == "auto"

    def test_operator_approval_level(self):
        inc = _make_incident(
            state=IncidentState.RESOLVED,
            meta={"_approval_level": "operator"},
        )
        assert determine_resolution_type(inc) == "operator"

    def test_senior_approval_level(self):
        inc = _make_incident(
            state=IncidentState.RESOLVED,
            meta={"_approval_level": "senior"},
        )
        assert determine_resolution_type(inc) == "senior"

    def test_default_is_operator(self):
        inc = _make_incident(state=IncidentState.RESOLVED, meta={})
        assert determine_resolution_type(inc) == "operator"

    def test_none_meta_defaults_to_operator(self):
        inc = _make_incident(state=IncidentState.RESOLVED, meta=None)
        assert determine_resolution_type(inc) == "operator"


class TestComputeResolutionDuration:
    def test_returns_positive_duration(self):
        inc = _make_incident(
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10)
        )
        duration = compute_resolution_duration(inc)
        assert duration is not None
        assert 590 < duration < 620  # ~600 seconds (10 min)

    def test_returns_none_when_no_created_at(self):
        inc = _make_incident(created_at=None)
        assert compute_resolution_duration(inc) is None

    def test_handles_naive_datetime(self):
        """Should handle naive datetimes by assuming UTC."""
        inc = _make_incident(
            created_at=datetime.now(timezone.utc) - timedelta(seconds=30)
        )
        duration = compute_resolution_duration(inc)
        assert duration is not None
        assert 25 < duration < 35

    def test_short_duration(self):
        inc = _make_incident(
            created_at=datetime.now(timezone.utc) - timedelta(seconds=5)
        )
        duration = compute_resolution_duration(inc)
        assert duration is not None
        assert 3 < duration < 8


class TestBuildResolutionSummary:
    def test_includes_outcome(self):
        inc = _make_incident(state=IncidentState.RESOLVED)
        summary = build_resolution_summary(inc)
        assert "RESOLVED" in summary

    def test_includes_action(self):
        inc = _make_incident(
            meta={"recommendation": {"proposed_action": "restart_service", "root_cause": "OOM"}}
        )
        summary = build_resolution_summary(inc)
        assert "restart_service" in summary
        assert "OOM" in summary

    def test_includes_approval_level(self):
        inc = _make_incident(meta={"_approval_level": "senior"})
        summary = build_resolution_summary(inc)
        assert "senior" in summary

    def test_includes_rejection_reason(self):
        inc = _make_incident(
            state=IncidentState.REJECTED,
            meta={"_manual_review_reason": "False positive"},
        )
        summary = build_resolution_summary(inc)
        assert "False positive" in summary

    def test_includes_retries(self):
        inc = _make_incident(
            investigation_retry_count=1,
            verification_retry_count=2,
        )
        summary = build_resolution_summary(inc)
        assert "investigation=1" in summary
        assert "verification=2" in summary

    def test_no_retries_omits_section(self):
        inc = _make_incident()
        summary = build_resolution_summary(inc)
        assert "Retries" not in summary

    def test_minimal_meta(self):
        inc = _make_incident(meta=None)
        summary = build_resolution_summary(inc)
        assert "Outcome: RESOLVED" in summary


class TestRecordResolution:
    @pytest.mark.asyncio
    async def test_records_all_fields(self):
        inc = _make_incident(
            meta={"_approval_level": "auto", "recommendation": {"proposed_action": "clear_logs"}},
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        session = AsyncMock()

        await record_resolution(session, inc)

        assert inc.resolution_type == "auto"
        assert inc.resolution_summary is not None
        assert "RESOLVED" in inc.resolution_summary
        assert inc.resolution_duration_seconds is not None
        assert 295 < inc.resolution_duration_seconds < 310
        assert inc.resolved_at is not None

    @pytest.mark.asyncio
    async def test_idempotent_skips_if_already_recorded(self):
        inc = _make_incident(
            resolved_at=datetime.now(timezone.utc),
            resolution_type="auto",
        )
        session = AsyncMock()

        await record_resolution(session, inc)

        # Should not overwrite existing
        assert inc.resolution_type == "auto"

    @pytest.mark.asyncio
    async def test_records_rejected_incident(self):
        inc = _make_incident(
            state=IncidentState.REJECTED,
            meta={"_manual_review_reason": "Not needed"},
        )
        session = AsyncMock()

        await record_resolution(session, inc)

        assert inc.resolution_type == "rejected"
        assert "Not needed" in inc.resolution_summary
        assert inc.resolved_at is not None
