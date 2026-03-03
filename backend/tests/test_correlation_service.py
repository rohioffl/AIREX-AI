"""
Tests for cross-host incident correlation service (Phase 4 ARE).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import IncidentState, SeverityLevel
from app.services.correlation_service import (
    CORRELATION_WINDOW_MINUTES,
    compute_correlation_group_id,
    correlate_incident,
    get_correlated_incidents,
    get_correlation_summary,
)


TENANT = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _make_incident(
    alert_type="cpu_high",
    host_key="10.0.0.1",
    state=IncidentState.INVESTIGATING,
    created_at=None,
    correlation_group_id=None,
):
    incident = MagicMock()
    incident.id = uuid.uuid4()
    incident.tenant_id = TENANT
    incident.alert_type = alert_type
    incident.host_key = host_key
    incident.state = state
    incident.severity = SeverityLevel.HIGH
    incident.title = f"[DOWN] {host_key} — {alert_type}"
    incident.created_at = created_at or datetime.now(timezone.utc)
    incident.updated_at = incident.created_at
    incident.deleted_at = None
    incident.correlation_group_id = correlation_group_id
    incident.meta = {}
    return incident


# ── compute_correlation_group_id ─────────────────────────────


class TestComputeCorrelationGroupId:
    def test_deterministic(self):
        ts = datetime(2026, 3, 1, 12, 3, 45, tzinfo=timezone.utc)
        g1 = compute_correlation_group_id(TENANT, "cpu_high", ts)
        g2 = compute_correlation_group_id(TENANT, "cpu_high", ts)
        assert g1 == g2
        assert len(g1) == 16  # SHA256[:16]

    def test_same_bucket(self):
        """Timestamps in the same 15-min bucket get the same group."""
        t1 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 1, 12, 14, 59, tzinfo=timezone.utc)
        assert compute_correlation_group_id(TENANT, "cpu_high", t1) == \
               compute_correlation_group_id(TENANT, "cpu_high", t2)

    def test_different_bucket(self):
        """Timestamps in different 15-min buckets get different groups."""
        t1 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 3, 1, 12, 15, 0, tzinfo=timezone.utc)
        assert compute_correlation_group_id(TENANT, "cpu_high", t1) != \
               compute_correlation_group_id(TENANT, "cpu_high", t2)

    def test_different_alert_type(self):
        ts = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        g1 = compute_correlation_group_id(TENANT, "cpu_high", ts)
        g2 = compute_correlation_group_id(TENANT, "disk_full", ts)
        assert g1 != g2

    def test_different_tenant(self):
        ts = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        other = uuid.UUID("11111111-1111-1111-1111-111111111111")
        g1 = compute_correlation_group_id(TENANT, "cpu_high", ts)
        g2 = compute_correlation_group_id(other, "cpu_high", ts)
        assert g1 != g2


# ── correlate_incident ───────────────────────────────────────


class TestCorrelateIncident:
    @pytest.mark.asyncio
    async def test_assigns_group_when_cross_host_siblings_exist(self):
        now = datetime.now(timezone.utc)
        incident = _make_incident(host_key="10.0.0.1", created_at=now)
        sibling = _make_incident(
            host_key="10.0.0.2",
            created_at=now - timedelta(minutes=5),
            correlation_group_id=None,
        )

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sibling]
        session.execute.return_value = mock_result

        group_id = await correlate_incident(session, incident)

        assert group_id is not None
        assert incident.correlation_group_id == group_id
        assert sibling.correlation_group_id == group_id

    @pytest.mark.asyncio
    async def test_returns_none_when_no_siblings(self):
        incident = _make_incident(host_key="10.0.0.1")

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        group_id = await correlate_incident(session, incident)
        assert group_id is None

    @pytest.mark.asyncio
    async def test_skips_same_host_incidents(self):
        """Same host_key should not trigger correlation (that's related_incidents)."""
        now = datetime.now(timezone.utc)
        incident = _make_incident(host_key="10.0.0.1", created_at=now)
        same_host = _make_incident(
            host_key="10.0.0.1",
            created_at=now - timedelta(minutes=2),
        )

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [same_host]
        session.execute.return_value = mock_result

        group_id = await correlate_incident(session, incident)
        assert group_id is None

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_sibling_group(self):
        """Siblings that already have a group_id should not be overwritten."""
        now = datetime.now(timezone.utc)
        incident = _make_incident(host_key="10.0.0.1", created_at=now)
        sibling = _make_incident(
            host_key="10.0.0.2",
            created_at=now - timedelta(minutes=3),
            correlation_group_id="existing_group",
        )

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sibling]
        session.execute.return_value = mock_result

        group_id = await correlate_incident(session, incident)
        assert group_id is not None
        assert incident.correlation_group_id == group_id
        # Sibling's existing group should NOT be overwritten
        assert sibling.correlation_group_id == "existing_group"

    @pytest.mark.asyncio
    async def test_correlates_multiple_hosts(self):
        now = datetime.now(timezone.utc)
        incident = _make_incident(host_key="10.0.0.1", created_at=now)
        siblings = [
            _make_incident(host_key=f"10.0.0.{i}", created_at=now - timedelta(minutes=i))
            for i in range(2, 6)
        ]

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = siblings
        session.execute.return_value = mock_result

        group_id = await correlate_incident(session, incident)
        assert group_id is not None
        assert incident.correlation_group_id == group_id
        for s in siblings:
            assert s.correlation_group_id == group_id


# ── get_correlation_summary ──────────────────────────────────


class TestGetCorrelationSummary:
    @pytest.mark.asyncio
    async def test_builds_summary(self):
        now = datetime.now(timezone.utc)
        incidents = [
            _make_incident(
                host_key=f"10.0.0.{i}",
                created_at=now - timedelta(minutes=5 - i),
                state=IncidentState.INVESTIGATING if i < 3 else IncidentState.RESOLVED,
            )
            for i in range(1, 5)
        ]

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = incidents
        session.execute.return_value = mock_result

        summary = await get_correlation_summary(session, TENANT, "test_group")

        assert summary["group_id"] == "test_group"
        assert summary["incident_count"] == 4
        assert summary["affected_hosts"] == 4
        assert len(summary["host_keys"]) == 4
        assert "INVESTIGATING" in summary["states"]
        assert summary["span_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_empty_summary(self):
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_result

        summary = await get_correlation_summary(session, TENANT, "empty_group")
        assert summary == {}


# ── State Machine: correlation_group_id column ───────────────


class TestIncidentModelHasCorrelationGroupId:
    def test_column_exists(self):
        from app.models.incident import Incident
        assert hasattr(Incident, "correlation_group_id")
