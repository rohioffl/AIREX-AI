"""Tests for change detection, infra state, and log analysis probes (Phases 3-5)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from airex_core.investigations.change_detection_probe import (
    ChangeDetectionProbe,
    should_run_change_detection,
    _empty_audit_result,
)
from airex_core.investigations.infra_state_probe import (
    InfraStateProbe,
    should_run_infra_state_probe,
    _format_bytes,
    _empty_scaling,
    _empty_flows,
)
from airex_core.investigations.log_analysis_probe import (
    LogAnalysisProbe,
    should_run_log_analysis,
)
from airex_core.investigations.base import ProbeCategory, ProbeResult


# ═══════════════════════════════════════════════════════════════════
#  Change Detection — Gate Tests
# ═══════════════════════════════════════════════════════════════════


class TestShouldRunChangeDetection:
    def test_aws_with_instance_id(self):
        meta = {"_cloud": "aws", "_instance_id": "i-abc123"}
        assert should_run_change_detection(meta) is True

    def test_gcp_with_private_ip(self):
        meta = {"_cloud": "gcp", "_private_ip": "10.0.0.1"}
        assert should_run_change_detection(meta) is True

    def test_no_cloud(self):
        meta = {"_cloud": "", "_instance_id": "i-abc123"}
        assert should_run_change_detection(meta) is False

    def test_cloud_without_resource(self):
        meta = {"_cloud": "aws"}
        assert should_run_change_detection(meta) is False

    def test_unsupported_cloud(self):
        meta = {"_cloud": "azure", "_instance_id": "vm-1"}
        assert should_run_change_detection(meta) is False

    def test_missing_cloud_key(self):
        meta = {"_instance_id": "i-abc"}
        assert should_run_change_detection(meta) is False

    def test_resource_id_suffices(self):
        meta = {"_cloud": "aws", "_resource_id": "arn:aws:ec2:..."}
        assert should_run_change_detection(meta) is True


# ═══════════════════════════════════════════════════════════════════
#  Change Detection — Probe Tests
# ═══════════════════════════════════════════════════════════════════


class TestChangeDetectionProbe:
    @pytest.mark.asyncio
    async def test_unsupported_cloud_returns_empty(self):
        probe = ChangeDetectionProbe()
        result = await probe.investigate(
            {
                "_cloud": "azure",
                "_instance_id": "vm-1",
            }
        )
        assert isinstance(result, ProbeResult)
        assert result.category == ProbeCategory.CHANGE
        assert result.metrics["total_changes"] == 0

    @pytest.mark.asyncio
    async def test_aws_probe_routes_correctly(self):
        probe = ChangeDetectionProbe()
        with patch.object(probe, "_query_aws", new_callable=AsyncMock) as mock_aws:
            mock_aws.return_value = {
                "events": [{"event_name": "StopInstances"}],
                "total_count": 1,
                "high_risk_changes": [],
                "deployment_detected": False,
                "lookback_minutes": 60,
                "resource_id": "i-abc",
            }
            result = await probe.investigate(
                {
                    "_cloud": "aws",
                    "_instance_id": "i-abc",
                    "_region": "us-east-1",
                }
            )
            mock_aws.assert_called_once()
            assert "change_detection_aws" in result.tool_name
            assert result.metrics["total_changes"] == 1

    @pytest.mark.asyncio
    async def test_gcp_probe_routes_correctly(self):
        probe = ChangeDetectionProbe()
        with patch.object(probe, "_query_gcp", new_callable=AsyncMock) as mock_gcp:
            mock_gcp.return_value = {
                "events": [],
                "total_count": 0,
                "high_risk_changes": [],
                "deployment_detected": False,
                "lookback_minutes": 60,
                "resource_id": "vm-1",
            }
            result = await probe.investigate(
                {
                    "_cloud": "gcp",
                    "_instance_id": "vm-1",
                    "_project": "my-proj",
                }
            )
            mock_gcp.assert_called_once()
            assert "change_detection_gcp" in result.tool_name

    @pytest.mark.asyncio
    async def test_deployment_detected_creates_anomaly(self):
        probe = ChangeDetectionProbe()
        with patch.object(probe, "_query_aws", new_callable=AsyncMock) as mock_aws:
            mock_aws.return_value = {
                "events": [{"event_name": "UpdateService"}],
                "total_count": 1,
                "high_risk_changes": [{"event_name": "UpdateService"}],
                "deployment_detected": True,
                "lookback_minutes": 60,
                "resource_id": "i-abc",
            }
            result = await probe.investigate(
                {
                    "_cloud": "aws",
                    "_instance_id": "i-abc",
                }
            )
            assert result.metrics["deployment_detected"] is True
            assert len(result.anomalies) >= 1
            anomaly_names = [a.metric_name for a in result.anomalies]
            assert "deployment_detected" in anomaly_names

    @pytest.mark.asyncio
    async def test_high_risk_changes_create_anomaly(self):
        probe = ChangeDetectionProbe()
        with patch.object(probe, "_query_aws", new_callable=AsyncMock) as mock_aws:
            mock_aws.return_value = {
                "events": [],
                "total_count": 3,
                "high_risk_changes": [
                    {"event_name": "DeleteSecurityGroup"},
                    {"event_name": "ModifyVpcAttribute"},
                    {"event_name": "RevokeSecurityGroupIngress"},
                ],
                "deployment_detected": False,
                "lookback_minutes": 60,
                "resource_id": "i-abc",
            }
            result = await probe.investigate(
                {
                    "_cloud": "aws",
                    "_instance_id": "i-abc",
                }
            )
            anomaly_names = [a.metric_name for a in result.anomalies]
            assert "high_risk_changes" in anomaly_names
            hr_anomaly = [
                a for a in result.anomalies if a.metric_name == "high_risk_changes"
            ][0]
            assert hr_anomaly.severity == "critical"  # >= 3 high risk


class TestEmptyAuditResult:
    def test_structure(self):
        r = _empty_audit_result("i-abc", "test error")
        assert r["events"] == []
        assert r["total_count"] == 0
        assert r["resource_id"] == "i-abc"
        assert r["error"] == "test error"


# ═══════════════════════════════════════════════════════════════════
#  Infra State — Gate Tests
# ═══════════════════════════════════════════════════════════════════


class TestShouldRunInfraState:
    def test_aws_with_instance(self):
        assert (
            should_run_infra_state_probe({"_cloud": "aws", "_instance_id": "i-1"})
            is True
        )

    def test_gcp_with_ip(self):
        assert (
            should_run_infra_state_probe({"_cloud": "gcp", "_private_ip": "10.0.0.1"})
            is True
        )

    def test_no_cloud(self):
        assert (
            should_run_infra_state_probe({"_cloud": "", "_instance_id": "i-1"}) is False
        )

    def test_no_resource(self):
        assert should_run_infra_state_probe({"_cloud": "aws"}) is False


# ═══════════════════════════════════════════════════════════════════
#  Infra State — Probe Tests
# ═══════════════════════════════════════════════════════════════════


class TestInfraStateProbe:
    @pytest.mark.asyncio
    async def test_unsupported_cloud_returns_empty(self):
        probe = InfraStateProbe()
        result = await probe.investigate(
            {
                "_cloud": "azure",
                "_instance_id": "vm-1",
            }
        )
        assert isinstance(result, ProbeResult)
        assert result.category == ProbeCategory.INFRASTRUCTURE

    @pytest.mark.asyncio
    async def test_aws_runs_parallel_queries(self):
        probe = InfraStateProbe()
        with (
            patch.object(probe, "_query_aws_asg", new_callable=AsyncMock) as mock_asg,
            patch.object(
                probe, "_query_aws_vpc_flows", new_callable=AsyncMock
            ) as mock_flows,
        ):
            mock_asg.return_value = {
                "asg_name": "my-asg",
                "instance_count": 3,
                "healthy_count": 2,
                "unhealthy_count": 1,
                "scaling_in_progress": False,
                "desired_capacity": 3,
            }
            mock_flows.return_value = {
                "total_records": 100,
                "rejected_count": 2,
                "accepted_count": 98,
            }
            result = await probe.investigate(
                {
                    "_cloud": "aws",
                    "_instance_id": "i-abc",
                    "_private_ip": "172.31.5.42",
                    "_region": "us-east-1",
                }
            )

            mock_asg.assert_called_once()
            mock_flows.assert_called_once()
            assert "infra_state_aws" in result.tool_name
            assert result.metrics["scaling_group"] == "my-asg"
            assert result.metrics["unhealthy_count"] == 1

    @pytest.mark.asyncio
    async def test_unhealthy_instances_create_anomaly(self):
        probe = InfraStateProbe()
        with (
            patch.object(probe, "_query_aws_asg", new_callable=AsyncMock) as mock_asg,
            patch.object(
                probe, "_query_aws_vpc_flows", new_callable=AsyncMock
            ) as mock_flows,
        ):
            mock_asg.return_value = {
                "asg_name": "my-asg",
                "instance_count": 3,
                "healthy_count": 1,
                "unhealthy_count": 2,
                "scaling_in_progress": False,
                "desired_capacity": 3,
            }
            mock_flows.return_value = _empty_flows()

            result = await probe.investigate(
                {
                    "_cloud": "aws",
                    "_instance_id": "i-abc",
                }
            )

            anomaly_names = [a.metric_name for a in result.anomalies]
            assert "unhealthy_instances" in anomaly_names
            ui_anomaly = [
                a for a in result.anomalies if a.metric_name == "unhealthy_instances"
            ][0]
            assert ui_anomaly.severity == "critical"  # >= 2

    @pytest.mark.asyncio
    async def test_rejected_traffic_creates_anomaly(self):
        probe = InfraStateProbe()
        with (
            patch.object(probe, "_query_aws_asg", new_callable=AsyncMock) as mock_asg,
            patch.object(
                probe, "_query_aws_vpc_flows", new_callable=AsyncMock
            ) as mock_flows,
        ):
            mock_asg.return_value = _empty_scaling()
            mock_flows.return_value = {
                "total_records": 50,
                "rejected_count": 25,
                "accepted_count": 25,
            }

            result = await probe.investigate(
                {
                    "_cloud": "aws",
                    "_instance_id": "i-abc",
                }
            )

            anomaly_names = [a.metric_name for a in result.anomalies]
            assert "rejected_traffic" in anomaly_names
            rt_anomaly = [
                a for a in result.anomalies if a.metric_name == "rejected_traffic"
            ][0]
            assert rt_anomaly.severity == "critical"  # > 20

    @pytest.mark.asyncio
    async def test_gcp_routes_correctly(self):
        probe = InfraStateProbe()
        with (
            patch.object(probe, "_query_gcp_mig", new_callable=AsyncMock) as mock_mig,
            patch.object(
                probe, "_query_gcp_vpc_flows", new_callable=AsyncMock
            ) as mock_flows,
        ):
            mock_mig.return_value = _empty_scaling()
            mock_flows.return_value = _empty_flows()

            result = await probe.investigate(
                {
                    "_cloud": "gcp",
                    "_instance_id": "vm-1",
                    "_project": "my-proj",
                    "_zone": "us-central1-a",
                }
            )

            mock_mig.assert_called_once()
            mock_flows.assert_called_once()
            assert "infra_state_gcp" in result.tool_name

    @pytest.mark.asyncio
    async def test_scaling_in_progress_creates_anomaly(self):
        probe = InfraStateProbe()
        with (
            patch.object(probe, "_query_aws_asg", new_callable=AsyncMock) as mock_asg,
            patch.object(
                probe, "_query_aws_vpc_flows", new_callable=AsyncMock
            ) as mock_flows,
        ):
            mock_asg.return_value = {
                "asg_name": "my-asg",
                "instance_count": 2,
                "healthy_count": 2,
                "unhealthy_count": 0,
                "scaling_in_progress": True,
                "desired_capacity": 4,
            }
            mock_flows.return_value = _empty_flows()

            result = await probe.investigate(
                {
                    "_cloud": "aws",
                    "_instance_id": "i-abc",
                }
            )

            anomaly_names = [a.metric_name for a in result.anomalies]
            assert "scaling_in_progress" in anomaly_names


class TestFormatBytes:
    def test_bytes(self):
        assert _format_bytes(500) == "500 B"

    def test_kilobytes(self):
        assert _format_bytes(2048) == "2.0 KB"

    def test_megabytes(self):
        assert _format_bytes(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert _format_bytes(3 * 1024 * 1024 * 1024) == "3.0 GB"


# ═══════════════════════════════════════════════════════════════════
#  Log Analysis — Gate Tests
# ═══════════════════════════════════════════════════════════════════


class TestShouldRunLogAnalysis:
    def test_log_alert_types(self):
        for at in (
            "log_anomaly",
            "healthcheck",
            "http_check",
            "cpu_high",
            "memory_high",
        ):
            assert should_run_log_analysis({"alert_type": at}) is True

    def test_cloud_context_triggers(self):
        assert (
            should_run_log_analysis({"alert_type": "unknown", "_cloud": "aws"}) is True
        )
        assert (
            should_run_log_analysis({"alert_type": "unknown", "_cloud": "gcp"}) is True
        )

    def test_no_cloud_unknown_type_skips(self):
        assert should_run_log_analysis({"alert_type": "unknown_type"}) is False

    def test_empty_meta(self):
        assert should_run_log_analysis({}) is False


# ═══════════════════════════════════════════════════════════════════
#  Log Analysis — Probe Tests
# ═══════════════════════════════════════════════════════════════════


class TestLogAnalysisProbe:
    @pytest.mark.asyncio
    async def test_simulated_logs_produce_results(self):
        probe = LogAnalysisProbe()
        result = await probe.investigate(
            {
                "_cloud": "",
                "host": "test-server",
                "alert_type": "cpu_high",
            }
        )
        assert isinstance(result, ProbeResult)
        assert result.category == ProbeCategory.LOG_ANALYSIS
        assert result.tool_name == "log_analysis"
        assert result.metrics["total_log_lines"] > 0

    @pytest.mark.asyncio
    async def test_produces_severity_counts(self):
        probe = LogAnalysisProbe()
        result = await probe.investigate(
            {
                "_cloud": "",
                "host": "web-01",
                "alert_type": "cpu_high",
            }
        )
        metrics = result.metrics
        assert "error_count" in metrics
        assert "warning_count" in metrics
        assert "critical_count" in metrics
        # Simulated logs should contain errors
        total_errors = metrics["error_count"] + metrics["critical_count"]
        assert total_errors > 0

    @pytest.mark.asyncio
    async def test_produces_pattern_matches(self):
        probe = LogAnalysisProbe()
        result = await probe.investigate(
            {
                "_cloud": "",
                "host": "web-01",
                "alert_type": "memory_high",
            }
        )
        # Memory high should match OOM patterns
        assert result.metrics["pattern_count"] > 0

    @pytest.mark.asyncio
    async def test_output_format(self):
        probe = LogAnalysisProbe()
        result = await probe.investigate(
            {
                "_cloud": "",
                "host": "web-01",
                "alert_type": "disk_full",
            }
        )
        assert "Enhanced Log Analysis" in result.raw_output
        assert "Severity Breakdown" in result.raw_output

    @pytest.mark.asyncio
    async def test_deterministic_output_for_same_meta(self):
        """Seeded RNG should produce identical results for identical meta."""
        probe = LogAnalysisProbe()
        meta = {"_cloud": "", "host": "web-01", "alert_type": "cpu_high"}
        r1 = await probe.investigate(dict(meta))
        r2 = await probe.investigate(dict(meta))
        assert r1.metrics["total_log_lines"] == r2.metrics["total_log_lines"]
        assert r1.metrics["error_count"] == r2.metrics["error_count"]

    def test_extract_patterns(self):
        probe = LogAnalysisProbe()
        lines = [
            "ERROR Out of memory: Kill process 1234",
            "ERROR Connection refused to upstream",
            "ERROR Out of memory: Kill process 5678",
            "WARNING disk at 90%",
        ]
        patterns = probe._extract_patterns(lines)
        pattern_dict = dict(patterns)
        assert "OOM Kill" in pattern_dict
        assert pattern_dict["OOM Kill"] == 2
        assert "Connection Refused" in pattern_dict

    def test_count_severities(self):
        probe = LogAnalysisProbe()
        lines = [
            "CRITICAL system failure",
            "ERROR something broke",
            "ERROR another error",
            "WARNING heads up",
            "INFO normal operation",
        ]
        counts = probe._count_severities(lines)
        assert counts["CRITICAL"] == 1
        assert counts["ERROR"] == 2
        assert counts["WARNING"] == 1
        assert counts["INFO"] == 1

    def test_find_first_error(self):
        probe = LogAnalysisProbe()
        lines = [
            "INFO starting up",
            "WARNING low disk",
            "ERROR connection refused",
            "ERROR OOM kill",
        ]
        first = probe._find_first_error(lines)
        assert "connection refused" in first

    def test_find_first_error_empty(self):
        probe = LogAnalysisProbe()
        lines = ["INFO all good", "INFO still good"]
        assert probe._find_first_error(lines) == ""

    def test_analyze_volume_no_spike(self):
        probe = LogAnalysisProbe()
        buckets = [("10:00", 5), ("10:05", 6), ("10:10", 4), ("10:15", 5)]
        result = probe._analyze_volume([], buckets)
        assert result["spike_detected"] is False

    def test_analyze_volume_with_spike(self):
        probe = LogAnalysisProbe()
        # Big spike at 10:10 (30 vs avg ~7)
        buckets = [
            ("10:00", 2),
            ("10:05", 3),
            ("10:10", 30),
            ("10:15", 2),
            ("10:20", 1),
        ]
        result = probe._analyze_volume([], buckets)
        assert result["spike_detected"] is True
        assert result["spike_bucket"] == "10:10"
        assert result["spike_ratio"] > 3.0

    def test_analyze_volume_too_few_buckets(self):
        probe = LogAnalysisProbe()
        buckets = [("10:00", 100), ("10:05", 1)]
        result = probe._analyze_volume([], buckets)
        assert result["spike_detected"] is False

    def test_group_by_time_bucket(self):
        probe = LogAnalysisProbe()
        lines = [
            "[2024-01-15 10:01:00] ERROR foo",
            "[2024-01-15 10:03:00] ERROR bar",
            "[2024-01-15 10:06:00] ERROR baz",
            "[2024-01-15 10:07:00] ERROR qux",
        ]
        buckets = probe._group_by_time_bucket(lines)
        bucket_dict = dict(buckets)
        # 10:01 and 10:03 -> 10:00 bucket
        assert bucket_dict.get("10:00") == 2
        # 10:06 and 10:07 -> 10:05 bucket
        assert bucket_dict.get("10:05") == 2

    @pytest.mark.asyncio
    async def test_anomalies_created_for_high_error_count(self):
        probe = LogAnalysisProbe()
        result = await probe.investigate(
            {
                "_cloud": "",
                "host": "crash-server",
                "alert_type": "memory_high",
            }
        )
        # Memory high generates OOM logs -> errors > 5 threshold
        error_total = result.metrics["error_count"] + result.metrics["critical_count"]
        if error_total > 5:
            anomaly_names = [a.metric_name for a in result.anomalies]
            assert "log_error_count" in anomaly_names
