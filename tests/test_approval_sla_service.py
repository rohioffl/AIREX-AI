"""Tests for Approval SLA enforcement service — Phase 6 Operational Polish."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.services.approval_sla_service import check_approval_slas


def _make_incident(
    severity: SeverityLevel = SeverityLevel.HIGH,
    state: IncidentState = IncidentState.AWAITING_APPROVAL,
    updated_at: datetime | None = None,
    meta: dict | None = None,
) -> MagicMock:
    inc = MagicMock()
    inc.id = uuid.uuid4()
    inc.tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    inc.severity = severity
    inc.state = state
    inc.title = "Test incident"
    inc.meta = meta or {}
    inc.updated_at = updated_at or datetime.now(timezone.utc) - timedelta(seconds=10)
    return inc


def _make_session(incidents: list) -> AsyncMock:
    session = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = incidents
    result = MagicMock()
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return session


class TestCheckApprovalSlas:
    @pytest.mark.asyncio
    async def test_no_incidents_returns_zero(self):
        session = _make_session([])
        count = await check_approval_slas(session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_incident_within_sla_not_escalated(self):
        """An incident entered AWAITING_APPROVAL just now is within SLA."""
        inc = _make_incident(
            severity=SeverityLevel.HIGH,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        session = _make_session([inc])
        count = await check_approval_slas(session)
        assert count == 0
        assert not inc.meta.get("_sla_breached")

    @pytest.mark.asyncio
    async def test_critical_sla_breach_detected(self):
        """CRITICAL incident past 120s threshold should be escalated."""
        inc = _make_incident(
            severity=SeverityLevel.CRITICAL,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=200),
        )
        session = _make_session([inc])

        with patch(
            "airex_core.services.approval_sla_service.emit_state_changed",
            new_callable=AsyncMock,
        ):
            count = await check_approval_slas(session)

        assert count == 1
        assert inc.meta["_sla_breached"] is True

    @pytest.mark.asyncio
    async def test_high_sla_breach_detected(self):
        """HIGH incident past 300s threshold should be escalated."""
        inc = _make_incident(
            severity=SeverityLevel.HIGH,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=400),
        )
        session = _make_session([inc])

        with patch(
            "airex_core.services.approval_sla_service.emit_state_changed",
            new_callable=AsyncMock,
        ):
            count = await check_approval_slas(session)

        assert count == 1

    @pytest.mark.asyncio
    async def test_medium_within_sla_not_escalated(self):
        """MEDIUM incident at 500s (threshold 900s) should not be escalated."""
        inc = _make_incident(
            severity=SeverityLevel.MEDIUM,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=500),
        )
        session = _make_session([inc])
        count = await check_approval_slas(session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_low_sla_breach_detected(self):
        """LOW incident past 1800s threshold should be escalated."""
        inc = _make_incident(
            severity=SeverityLevel.LOW,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=2000),
        )
        session = _make_session([inc])

        with patch(
            "airex_core.services.approval_sla_service.emit_state_changed",
            new_callable=AsyncMock,
        ):
            count = await check_approval_slas(session)

        assert count == 1

    @pytest.mark.asyncio
    async def test_already_breached_incident_skipped(self):
        """Incident already marked _sla_breached should not be escalated again."""
        inc = _make_incident(
            severity=SeverityLevel.CRITICAL,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=500),
            meta={"_sla_breached": True},
        )
        session = _make_session([inc])
        count = await check_approval_slas(session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_meta_fields_set_on_breach(self):
        """Breach meta fields must be populated with elapsed/threshold."""
        inc = _make_incident(
            severity=SeverityLevel.HIGH,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=400),
        )
        session = _make_session([inc])

        with patch(
            "airex_core.services.approval_sla_service.emit_state_changed",
            new_callable=AsyncMock,
        ):
            await check_approval_slas(session)

        assert inc.meta["_sla_breached"] is True
        assert "_sla_breach_elapsed_seconds" in inc.meta
        assert inc.meta["_sla_threshold_seconds"] == 300

    @pytest.mark.asyncio
    async def test_naive_datetime_handled(self):
        """updated_at without timezone info should still be processed correctly."""
        naive_dt = datetime.utcnow() - timedelta(seconds=400)
        assert naive_dt.tzinfo is None

        inc = _make_incident(
            severity=SeverityLevel.HIGH,
            updated_at=naive_dt,
        )
        session = _make_session([inc])

        with patch(
            "airex_core.services.approval_sla_service.emit_state_changed",
            new_callable=AsyncMock,
        ):
            count = await check_approval_slas(session)

        assert count == 1

    @pytest.mark.asyncio
    async def test_none_updated_at_skipped(self):
        """Incident with no updated_at should not be escalated (can't compute elapsed)."""
        inc = _make_incident(severity=SeverityLevel.CRITICAL)
        inc.updated_at = None
        session = _make_session([inc])
        count = await check_approval_slas(session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_incidents_counted(self):
        """Multiple breached incidents should all be counted."""
        inc1 = _make_incident(
            severity=SeverityLevel.CRITICAL,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=300),
        )
        inc2 = _make_incident(
            severity=SeverityLevel.HIGH,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=500),
        )
        inc3 = _make_incident(
            severity=SeverityLevel.MEDIUM,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=100),  # within SLA
        )
        session = _make_session([inc1, inc2, inc3])

        with patch(
            "airex_core.services.approval_sla_service.emit_state_changed",
            new_callable=AsyncMock,
        ):
            count = await check_approval_slas(session)

        assert count == 2

    @pytest.mark.asyncio
    async def test_sse_failure_does_not_propagate(self):
        """SSE emit failure should be swallowed, not raise."""
        inc = _make_incident(
            severity=SeverityLevel.HIGH,
            updated_at=datetime.now(timezone.utc) - timedelta(seconds=400),
        )
        session = _make_session([inc])

        with patch(
            "airex_core.services.approval_sla_service.emit_state_changed",
            side_effect=RuntimeError("SSE failure"),
        ):
            count = await check_approval_slas(session)

        assert count == 1
