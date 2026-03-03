"""Tests for health check service (Phase 6 ARE — Proactive Monitoring)."""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.health_check import HealthCheck, HealthCheckStatus, TargetType
from app.services.health_check_service import (
    THRESHOLDS,
    evaluate_thresholds,
    _worst_status,
    check_site24x7_monitors,
    auto_create_incidents,
    run_health_checks,
    get_dashboard,
    get_target_history,
)

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _make_health_check(
    status: str = HealthCheckStatus.HEALTHY,
    target_type: str = TargetType.SITE24X7,
    target_id: str = "mon-001",
    target_name: str = "test-monitor",
    incident_created: bool = False,
    anomalies: list | None = None,
    metrics: dict | None = None,
) -> HealthCheck:
    hc = MagicMock(spec=HealthCheck)
    hc.id = uuid.uuid4()
    hc.tenant_id = TENANT
    hc.target_type = target_type
    hc.target_id = target_id
    hc.target_name = target_name
    hc.status = status
    hc.metrics = metrics or {}
    hc.anomalies = anomalies
    hc.incident_created = incident_created
    hc.incident_id = None
    hc.checked_at = datetime.now(timezone.utc)
    hc.duration_ms = 42.0
    hc.error = None
    return hc


# ── evaluate_thresholds ──────────────────────────────────────────


class TestEvaluateThresholds:
    """Tests for threshold evaluation logic."""

    def test_healthy_when_all_metrics_normal(self):
        metrics = {"cpu_percent": 50.0, "memory_percent": 60.0, "disk_percent": 40.0}
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.HEALTHY
        assert anomalies == []

    def test_degraded_when_warning_threshold_exceeded(self):
        metrics = {"cpu_percent": 90.0}  # above 85 warning, below 95 critical
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DEGRADED
        assert len(anomalies) == 1
        assert anomalies[0]["severity"] == "warning"
        assert anomalies[0]["metric"] == "cpu_percent"

    def test_down_when_critical_threshold_exceeded(self):
        metrics = {"cpu_percent": 97.0}  # above 95 critical
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DOWN
        assert len(anomalies) == 1
        assert anomalies[0]["severity"] == "critical"

    def test_multiple_anomalies_returns_worst(self):
        metrics = {"cpu_percent": 90.0, "memory_percent": 96.0}
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DOWN  # memory is critical
        assert len(anomalies) == 2

    def test_response_time_threshold(self):
        metrics = {"response_time_ms": 3000.0}  # above 2000 warning
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DEGRADED
        assert anomalies[0]["metric"] == "response_time_ms"

    def test_response_time_critical(self):
        metrics = {"response_time_ms": 6000.0}  # above 5000 critical
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DOWN

    def test_availability_inverted_threshold(self):
        """Availability: lower is worse (inverted threshold)."""
        metrics = {"availability_percent": 98.0}  # below 99 warning
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DEGRADED
        assert anomalies[0]["severity"] == "warning"

    def test_availability_critical(self):
        metrics = {"availability_percent": 90.0}  # below 95 critical
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DOWN
        assert anomalies[0]["severity"] == "critical"

    def test_unknown_metrics_ignored(self):
        metrics = {"custom_metric": 999.9, "another_thing": "hello"}
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.HEALTHY
        assert anomalies == []

    def test_empty_metrics(self):
        status, anomalies = evaluate_thresholds({})
        assert status == HealthCheckStatus.HEALTHY
        assert anomalies == []

    def test_non_numeric_values_ignored(self):
        metrics = {"cpu_percent": "high", "memory_percent": None}
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.HEALTHY
        assert anomalies == []

    def test_exact_warning_threshold(self):
        """Values exactly at warning threshold should trigger warning."""
        metrics = {"cpu_percent": 85.0}
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DEGRADED

    def test_exact_critical_threshold(self):
        metrics = {"cpu_percent": 95.0}
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DOWN

    def test_disk_percent_threshold(self):
        metrics = {"disk_percent": 82.0}  # above 80 warning
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DEGRADED

    def test_error_rate_threshold(self):
        metrics = {"error_rate_percent": 10.0}  # above 5 warning
        status, anomalies = evaluate_thresholds(metrics)
        assert status == HealthCheckStatus.DEGRADED


# ── _worst_status ────────────────────────────────────────────────


class TestWorstStatus:
    """Tests for status comparison helper."""

    def test_healthy_vs_healthy(self):
        assert _worst_status("healthy", "healthy") == "healthy"

    def test_healthy_vs_degraded(self):
        assert _worst_status("healthy", "degraded") == "degraded"

    def test_degraded_vs_down(self):
        assert _worst_status("degraded", "down") == "down"

    def test_down_vs_healthy(self):
        assert _worst_status("down", "healthy") == "down"

    def test_unknown_vs_degraded(self):
        assert _worst_status("unknown", "degraded") == "degraded"

    def test_error_vs_degraded(self):
        assert _worst_status("error", "degraded") == "error"


# ── check_site24x7_monitors ─────────────────────────────────────


class TestCheckSite24x7Monitors:
    """Tests for Site24x7 monitor polling."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self):
        session = AsyncMock()
        with patch("app.services.health_check_service.settings") as mock_settings:
            mock_settings.SITE24X7_ENABLED = False
            mock_settings.SITE24X7_REFRESH_TOKEN = ""
            result = await check_site24x7_monitors(session, TENANT)
            assert result == []

    @pytest.mark.asyncio
    async def test_processes_monitor_data(self):
        session = AsyncMock()
        redis = AsyncMock()

        mock_client_instance = AsyncMock()
        mock_client_instance._get.return_value = {
            "data": {
                "monitors": [
                    {
                        "monitors": [
                            {
                                "monitor_id": "111",
                                "name": "Web Server",
                                "status": 1,  # UP
                                "attribute_value": "150 ms",
                            },
                            {
                                "monitor_id": "222",
                                "name": "API Server",
                                "status": 0,  # DOWN
                                "attribute_value": "",
                            },
                        ]
                    }
                ]
            }
        }

        with (
            patch("app.services.health_check_service.settings") as mock_settings,
            patch(
                "app.monitoring.site24x7_client.Site24x7Client",
                return_value=mock_client_instance,
            ),
        ):
            mock_settings.SITE24X7_ENABLED = True
            mock_settings.SITE24X7_REFRESH_TOKEN = "refresh-token"
            mock_settings.HEALTH_CHECK_MAX_MONITORS = 200

            result = await check_site24x7_monitors(session, TENANT, redis=redis)
            assert len(result) == 2
            # First monitor: UP -> healthy
            assert result[0].status == HealthCheckStatus.HEALTHY
            assert result[0].target_id == "111"
            # Second monitor: DOWN
            assert result[1].status == HealthCheckStatus.DOWN
            assert result[1].target_id == "222"

    @pytest.mark.asyncio
    async def test_handles_monitor_error_gracefully(self):
        session = AsyncMock()

        mock_client_instance = AsyncMock()
        mock_client_instance._get.return_value = {
            "data": {
                "monitors": [
                    {
                        "monitors": [
                            {
                                "monitor_id": "333",
                                "name": "Broken Monitor",
                                "status": "not_a_number",
                            },
                        ]
                    }
                ]
            }
        }

        with (
            patch("app.services.health_check_service.settings") as mock_settings,
            patch(
                "app.monitoring.site24x7_client.Site24x7Client",
                return_value=mock_client_instance,
            ),
        ):
            mock_settings.SITE24X7_ENABLED = True
            mock_settings.SITE24X7_REFRESH_TOKEN = "token"
            mock_settings.HEALTH_CHECK_MAX_MONITORS = 200

            result = await check_site24x7_monitors(session, TENANT)
            assert len(result) == 1
            assert result[0].status == HealthCheckStatus.ERROR

    @pytest.mark.asyncio
    async def test_handles_bulk_api_failure(self):
        session = AsyncMock()

        mock_client_instance = AsyncMock()
        mock_client_instance._get.side_effect = Exception("API down")

        with (
            patch("app.services.health_check_service.settings") as mock_settings,
            patch(
                "app.monitoring.site24x7_client.Site24x7Client",
                return_value=mock_client_instance,
            ),
        ):
            mock_settings.SITE24X7_ENABLED = True
            mock_settings.SITE24X7_REFRESH_TOKEN = "token"
            mock_settings.HEALTH_CHECK_MAX_MONITORS = 200

            result = await check_site24x7_monitors(session, TENANT)
            assert result == []


# ── auto_create_incidents ────────────────────────────────────────


class TestAutoCreateIncidents:
    """Tests for automatic incident creation from health check results."""

    @pytest.mark.asyncio
    async def test_creates_incident_for_down_check(self):
        session = AsyncMock()
        hc = _make_health_check(status=HealthCheckStatus.DOWN)

        # First execute: active-incident dedup query (no active incident)
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = None
        # Second execute: cooldown query (no recent incident)
        cooldown_result = MagicMock()
        cooldown_result.scalar_one.return_value = 0
        session.execute.side_effect = [dedup_result, cooldown_result]

        mock_incident = MagicMock()
        mock_incident.id = uuid.uuid4()

        with (
            patch(
                "app.services.incident_service.create_incident",
                new_callable=AsyncMock,
                return_value=mock_incident,
            ),
            patch("app.services.health_check_service.settings") as mock_settings,
        ):
            mock_settings.HEALTH_CHECK_INCIDENT_COOLDOWN_MINUTES = 30
            count = await auto_create_incidents(session, TENANT, [hc])

        assert count == 1
        assert hc.incident_created is True
        assert hc.incident_id == mock_incident.id

    @pytest.mark.asyncio
    async def test_creates_incident_for_degraded_check(self):
        session = AsyncMock()
        hc = _make_health_check(status=HealthCheckStatus.DEGRADED)

        # First execute: active-incident dedup query (no active incident)
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = None
        # Second execute: cooldown query (no recent incident)
        cooldown_result = MagicMock()
        cooldown_result.scalar_one.return_value = 0
        session.execute.side_effect = [dedup_result, cooldown_result]

        mock_incident = MagicMock()
        mock_incident.id = uuid.uuid4()

        with (
            patch(
                "app.services.incident_service.create_incident",
                new_callable=AsyncMock,
                return_value=mock_incident,
            ),
            patch("app.services.health_check_service.settings") as mock_settings,
        ):
            mock_settings.HEALTH_CHECK_INCIDENT_COOLDOWN_MINUTES = 30
            count = await auto_create_incidents(session, TENANT, [hc])

        assert count == 1

    @pytest.mark.asyncio
    async def test_skips_healthy_check(self):
        session = AsyncMock()
        hc = _make_health_check(status=HealthCheckStatus.HEALTHY)

        count = await auto_create_incidents(session, TENANT, [hc])
        assert count == 0
        assert hc.incident_created is False

    @pytest.mark.asyncio
    async def test_skips_unknown_check(self):
        session = AsyncMock()
        hc = _make_health_check(status=HealthCheckStatus.UNKNOWN)

        count = await auto_create_incidents(session, TENANT, [hc])
        assert count == 0

    @pytest.mark.asyncio
    async def test_respects_cooldown(self):
        session = AsyncMock()
        hc = _make_health_check(status=HealthCheckStatus.DOWN)

        # First execute: active-incident dedup query (no active incident)
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = None
        # Second execute: cooldown query (recent incident exists)
        cooldown_result = MagicMock()
        cooldown_result.scalar_one.return_value = 1
        session.execute.side_effect = [dedup_result, cooldown_result]

        with patch("app.services.health_check_service.settings") as mock_settings:
            mock_settings.HEALTH_CHECK_INCIDENT_COOLDOWN_MINUTES = 30
            count = await auto_create_incidents(session, TENANT, [hc])

        assert count == 0
        assert hc.incident_created is False

    @pytest.mark.asyncio
    async def test_handles_incident_creation_failure(self):
        session = AsyncMock()
        hc = _make_health_check(status=HealthCheckStatus.DOWN)

        # First execute: active-incident dedup query (no active incident)
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = None
        # Second execute: cooldown query (no recent incident)
        cooldown_result = MagicMock()
        cooldown_result.scalar_one.return_value = 0
        session.execute.side_effect = [dedup_result, cooldown_result]

        with (
            patch(
                "app.services.incident_service.create_incident",
                new_callable=AsyncMock,
                side_effect=Exception("DB error"),
            ),
            patch("app.services.health_check_service.settings") as mock_settings,
        ):
            mock_settings.HEALTH_CHECK_INCIDENT_COOLDOWN_MINUTES = 30
            count = await auto_create_incidents(session, TENANT, [hc])

        assert count == 0

    @pytest.mark.asyncio
    async def test_multiple_checks_mixed_statuses(self):
        session = AsyncMock()
        checks = [
            _make_health_check(status=HealthCheckStatus.HEALTHY, target_id="h1"),
            _make_health_check(status=HealthCheckStatus.DOWN, target_id="d1"),
            _make_health_check(status=HealthCheckStatus.UNKNOWN, target_id="u1"),
            _make_health_check(status=HealthCheckStatus.DEGRADED, target_id="d2"),
        ]

        # For each DOWN/DEGRADED check: dedup query (no active) + cooldown query (no recent)
        dedup_result = MagicMock()
        dedup_result.scalar_one_or_none.return_value = None
        cooldown_result = MagicMock()
        cooldown_result.scalar_one.return_value = 0
        # DOWN: dedup + cooldown, DEGRADED: dedup + cooldown = 4 calls
        session.execute.side_effect = [
            dedup_result,
            cooldown_result,
            dedup_result,
            cooldown_result,
        ]

        mock_incident = MagicMock()
        mock_incident.id = uuid.uuid4()

        with (
            patch(
                "app.services.incident_service.create_incident",
                new_callable=AsyncMock,
                return_value=mock_incident,
            ),
            patch("app.services.health_check_service.settings") as mock_settings,
        ):
            mock_settings.HEALTH_CHECK_INCIDENT_COOLDOWN_MINUTES = 30
            count = await auto_create_incidents(session, TENANT, checks)

        # Only DOWN and DEGRADED should create incidents
        assert count == 2


# ── run_health_checks ────────────────────────────────────────────


class TestRunHealthChecks:
    """Tests for the main health check orchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrates_checks_and_incidents(self):
        checks = [
            _make_health_check(status=HealthCheckStatus.HEALTHY),
            _make_health_check(status=HealthCheckStatus.DOWN),
            _make_health_check(status=HealthCheckStatus.DEGRADED),
        ]

        mock_session = AsyncMock()

        with (
            patch("app.core.database.get_tenant_session") as mock_session_ctx,
            patch(
                "app.services.health_check_service.check_site24x7_monitors",
                new_callable=AsyncMock,
                return_value=checks,
            ),
            patch(
                "app.services.health_check_service.auto_create_incidents",
                new_callable=AsyncMock,
                return_value=2,
            ),
        ):
            mock_session_ctx.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            summary = await run_health_checks(TENANT)

        assert summary["checked"] == 3
        assert summary["healthy"] == 1
        assert summary["degraded"] == 1
        assert summary["down"] == 1
        assert summary["incidents_created"] == 2


# ── HealthCheck model ────────────────────────────────────────────


class TestHealthCheckModel:
    """Tests for the HealthCheck SQLAlchemy model."""

    def test_has_required_attributes(self):
        assert hasattr(HealthCheck, "tenant_id")
        assert hasattr(HealthCheck, "id")
        assert hasattr(HealthCheck, "target_type")
        assert hasattr(HealthCheck, "target_id")
        assert hasattr(HealthCheck, "target_name")
        assert hasattr(HealthCheck, "status")
        assert hasattr(HealthCheck, "metrics")
        assert hasattr(HealthCheck, "anomalies")
        assert hasattr(HealthCheck, "incident_created")
        assert hasattr(HealthCheck, "incident_id")
        assert hasattr(HealthCheck, "checked_at")
        assert hasattr(HealthCheck, "duration_ms")
        assert hasattr(HealthCheck, "error")

    def test_tablename(self):
        assert HealthCheck.__tablename__ == "health_checks"


class TestHealthCheckStatusConstants:
    """Tests for status and target type constants."""

    def test_status_values(self):
        assert HealthCheckStatus.HEALTHY == "healthy"
        assert HealthCheckStatus.DEGRADED == "degraded"
        assert HealthCheckStatus.DOWN == "down"
        assert HealthCheckStatus.UNKNOWN == "unknown"
        assert HealthCheckStatus.ERROR == "error"

    def test_target_type_values(self):
        assert TargetType.SITE24X7 == "site24x7_monitor"
        assert TargetType.CLOUD_INSTANCE == "cloud_instance"
        assert TargetType.ENDPOINT == "endpoint"


class TestThresholdConfig:
    """Tests for threshold configuration."""

    def test_all_expected_thresholds_defined(self):
        expected = [
            "response_time_ms",
            "cpu_percent",
            "memory_percent",
            "disk_percent",
            "availability_percent",
            "error_rate_percent",
        ]
        for key in expected:
            assert key in THRESHOLDS, f"Missing threshold for {key}"

    def test_thresholds_are_tuples_of_two_floats(self):
        for key, (warn, crit) in THRESHOLDS.items():
            assert isinstance(warn, float), f"{key} warning threshold must be float"
            assert isinstance(crit, float), f"{key} critical threshold must be float"
