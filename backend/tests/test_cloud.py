"""Tests for cloud integration: tag parsing, routing, diagnostics."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.cloud.tag_parser import parse_tags, merge_context_into_meta, CloudContext
from app.cloud.diagnostics import get_diagnostic_commands, DIAGNOSTIC_COMMANDS
from app.services.investigation_service import _should_use_cloud_investigation


# ═══════════════════════════════════════════════════════════════════
#  Tag Parser Tests
# ═══════════════════════════════════════════════════════════════════

class TestTagParser:
    """Parse Site24x7 tags into CloudContext."""

    def test_gcp_full_tags(self):
        ctx = parse_tags("cloud:gcp,tenant:acme-corp,ip:10.128.0.15,instance:vm-prod-01,project:my-project,zone:us-central1-a")
        assert ctx.cloud == "gcp"
        assert ctx.tenant == "acme-corp"
        assert ctx.private_ip == "10.128.0.15"
        assert ctx.instance_id == "vm-prod-01"
        assert ctx.project == "my-project"
        assert ctx.zone == "us-central1-a"
        assert ctx.is_gcp
        assert not ctx.is_aws
        assert ctx.has_target

    def test_aws_full_tags(self):
        ctx = parse_tags("cloud:aws,tenant:beta-inc,ip:172.31.5.42,instance:i-0abc123def,region:ap-south-1")
        assert ctx.cloud == "aws"
        assert ctx.tenant == "beta-inc"
        assert ctx.private_ip == "172.31.5.42"
        assert ctx.instance_id == "i-0abc123def"
        assert ctx.region == "ap-south-1"
        assert ctx.is_aws
        assert not ctx.is_gcp
        assert ctx.has_target

    def test_spaces_in_tags(self):
        ctx = parse_tags("cloud:gcp, tenant:acme, ip:10.0.0.1")
        assert ctx.cloud == "gcp"
        assert ctx.tenant == "acme"
        assert ctx.private_ip == "10.0.0.1"

    def test_mixed_kv_and_plain(self):
        ctx = parse_tags("production,web,cloud:aws,10.0.0.5,i-0abc123def456")
        assert ctx.cloud == "aws"
        assert ctx.private_ip == "10.0.0.5"
        assert ctx.instance_id == "i-0abc123def456"
        assert ctx.environment == "production"

    def test_plain_cloud_detection(self):
        ctx = parse_tags("gcp,prod,frontend")
        assert ctx.cloud == "gcp"
        assert ctx.environment == "prod"

    def test_empty_tags(self):
        ctx = parse_tags("")
        assert ctx.cloud == ""
        assert not ctx.has_target

    def test_none_tags(self):
        ctx = parse_tags(None)
        assert ctx.cloud == ""

    def test_only_cloud_and_tenant(self):
        ctx = parse_tags("cloud:gcp,tenant:mycompany")
        assert ctx.cloud == "gcp"
        assert ctx.tenant == "mycompany"
        assert not ctx.has_target  # No IP or instance

    def test_private_ip_patterns(self):
        # 10.x.x.x
        ctx = parse_tags("ip:10.0.0.1")
        assert ctx.private_ip == "10.0.0.1"
        # 172.16-31.x.x
        ctx = parse_tags("ip:172.20.5.100")
        assert ctx.private_ip == "172.20.5.100"
        # 192.168.x.x
        ctx = parse_tags("ip:192.168.1.50")
        assert ctx.private_ip == "192.168.1.50"

    def test_ec2_instance_id_detection(self):
        ctx = parse_tags("i-0abc123def456789a")
        assert ctx.instance_id == "i-0abc123def456789a"

    def test_service_account_tag(self):
        ctx = parse_tags("cloud:gcp,sa:mysa@myproject.iam.gserviceaccount.com")
        assert ctx.service_account == "mysa@myproject.iam.gserviceaccount.com"

    def test_alternative_key_names(self):
        ctx = parse_tags("privateip:10.0.0.1,instance_id:i-abc123,project_id:proj1")
        assert ctx.private_ip == "10.0.0.1"
        assert ctx.instance_id == "i-abc123"
        assert ctx.project == "proj1"

    def test_extra_tags_preserved(self):
        ctx = parse_tags("cloud:gcp,team:sre,cost_center:eng-123")
        assert ctx.extra_tags["team"] == "sre"
        assert ctx.extra_tags["cost_center"] == "eng-123"


class TestMergeContext:
    """merge_context_into_meta injects cloud fields into incident meta."""

    def test_merge_gcp_context(self):
        meta = {"host": "test", "_source": "site24x7"}
        ctx = CloudContext(
            cloud="gcp",
            tenant="acme",
            private_ip="10.128.0.15",
            instance_id="vm-prod-01",
            project="my-project",
            zone="us-central1-a",
        )
        result = merge_context_into_meta(meta, ctx)
        assert result["_cloud"] == "gcp"
        assert result["_tenant_name"] == "acme"
        assert result["_private_ip"] == "10.128.0.15"
        assert result["_instance_id"] == "vm-prod-01"
        assert result["_project"] == "my-project"
        assert result["_has_cloud_target"] is True

    def test_merge_empty_context(self):
        meta = {"host": "test"}
        ctx = CloudContext()
        result = merge_context_into_meta(meta, ctx)
        assert result["_cloud"] == ""
        assert result["_has_cloud_target"] is False


# ═══════════════════════════════════════════════════════════════════
#  Diagnostic Commands Tests
# ═══════════════════════════════════════════════════════════════════

class TestDiagnosticCommands:
    """Verify diagnostic command sets exist for alert types."""

    def test_cpu_commands_exist(self):
        cmds = get_diagnostic_commands("cpu_high")
        assert len(cmds) > 10
        assert any("vmstat" in c for c in cmds)
        assert any("ps aux" in c for c in cmds)

    def test_memory_commands_exist(self):
        cmds = get_diagnostic_commands("memory_high")
        assert any("free" in c for c in cmds)
        assert any("oom" in c.lower() for c in cmds)

    def test_disk_commands_exist(self):
        cmds = get_diagnostic_commands("disk_full")
        assert any("df" in c for c in cmds)
        assert any("du" in c for c in cmds)

    def test_network_commands_exist(self):
        cmds = get_diagnostic_commands("network_issue")
        assert any("ip addr" in c or "ifconfig" in c for c in cmds)

    def test_unknown_alert_gets_health_check(self):
        cmds = get_diagnostic_commands("unknown_type")
        assert any("uptime" in c for c in cmds)

    def test_all_registered_types_have_commands(self):
        for alert_type in DIAGNOSTIC_COMMANDS:
            cmds = get_diagnostic_commands(alert_type)
            assert len(cmds) > 0, f"No commands for {alert_type}"


# ═══════════════════════════════════════════════════════════════════
#  Cloud Routing Tests
# ═══════════════════════════════════════════════════════════════════

class TestCloudRouting:
    """Verify investigation service routes correctly based on meta."""

    def test_gcp_with_target_uses_cloud(self):
        meta = {"_cloud": "gcp", "_has_cloud_target": True, "_private_ip": "10.0.0.1"}
        assert _should_use_cloud_investigation(meta) is True

    def test_aws_with_target_uses_cloud(self):
        meta = {"_cloud": "aws", "_has_cloud_target": True, "_instance_id": "i-abc123"}
        assert _should_use_cloud_investigation(meta) is True

    def test_no_cloud_uses_simulated(self):
        meta = {"_cloud": "", "_has_cloud_target": False}
        assert _should_use_cloud_investigation(meta) is False

    def test_cloud_without_target_uses_simulated(self):
        meta = {"_cloud": "gcp", "_has_cloud_target": False}
        assert _should_use_cloud_investigation(meta) is False

    def test_missing_cloud_key_uses_simulated(self):
        meta = {"host": "some-server"}
        assert _should_use_cloud_investigation(meta) is False


# ═══════════════════════════════════════════════════════════════════
#  Cloud Investigation Plugin Tests
# ═══════════════════════════════════════════════════════════════════

class TestCloudInvestigationPlugin:
    """Test the CloudInvestigation plugin dispatch."""

    @pytest.mark.asyncio
    async def test_falls_back_to_simulated_when_no_cloud(self):
        from app.investigations.cloud_investigation import CloudInvestigation

        plugin = CloudInvestigation()
        result = await plugin.investigate({
            "_cloud": "",
            "_private_ip": "",
            "_instance_id": "",
            "_has_cloud_target": False,
            "alert_type": "cpu_high",
            "host": "test-server",
        })
        assert "cloud_investigation_fallback" in result.tool_name
        assert "CPU" in result.raw_output or "cpu" in result.raw_output.lower()

    @pytest.mark.asyncio
    async def test_aws_dispatch_calls_ssm(self):
        from app.investigations.cloud_investigation import CloudInvestigation

        plugin = CloudInvestigation()

        with patch.object(plugin, '_run_aws_ssm', new_callable=AsyncMock) as mock_ssm, \
             patch.object(plugin, '_query_aws_logs', new_callable=AsyncMock) as mock_logs:
            mock_ssm.return_value = "SSM OUTPUT: cpu usage 95%"
            mock_logs.return_value = "CloudWatch: 5 error events"

            result = await plugin.investigate({
                "_cloud": "aws",
                "_private_ip": "172.31.5.42",
                "_instance_id": "i-0abc123",
                "_has_cloud_target": True,
                "_region": "ap-south-1",
                "alert_type": "cpu_high",
                "host": "i-0abc123",
            })

            mock_ssm.assert_called_once()
            mock_logs.assert_called_once()
            assert "cloud_investigation_aws" in result.tool_name
            assert "SSM OUTPUT" in result.raw_output
            assert "CloudWatch" in result.raw_output

    @pytest.mark.asyncio
    async def test_aws_fallback_to_ec2_instance_connect_when_ssm_fails(self):
        """When SSM returns an error, use EC2 Instance Connect (no stored keys)."""
        from app.investigations.cloud_investigation import CloudInvestigation

        plugin = CloudInvestigation()

        with patch.object(plugin, '_run_aws_ssm', new_callable=AsyncMock) as mock_ssm, \
             patch.object(plugin, '_run_aws_ec2_connect_ssh', new_callable=AsyncMock) as mock_ec2_ssh, \
             patch.object(plugin, '_query_aws_logs', new_callable=AsyncMock) as mock_logs:
            mock_ssm.return_value = "SSM ERROR: Instances not in a valid state"
            mock_ec2_ssh.return_value = "EC2 Instance Connect: uptime 1 day"
            mock_logs.return_value = "CloudWatch: no groups"

            result = await plugin.investigate({
                "_cloud": "aws",
                "_private_ip": "172.31.5.42",
                "_instance_id": "i-0abc123",
                "_has_cloud_target": True,
                "_region": "ap-south-1",
                "_zone": "ap-south-1a",
                "alert_type": "cpu_high",
                "host": "i-0abc123",
            })

            mock_ssm.assert_called_once()
            mock_ec2_ssh.assert_called_once()
            assert result.raw_output.count("EC2 Instance Connect") >= 1
            assert "uptime 1 day" in result.raw_output

    @pytest.mark.asyncio
    async def test_gcp_dispatch_calls_ssh(self):
        from app.investigations.cloud_investigation import CloudInvestigation

        plugin = CloudInvestigation()

        with patch.object(plugin, '_run_gcp_ssh', new_callable=AsyncMock) as mock_ssh, \
             patch.object(plugin, '_query_gcp_logs', new_callable=AsyncMock) as mock_logs:
            mock_ssh.return_value = "SSH OUTPUT: memory at 92%"
            mock_logs.return_value = "Log Explorer: 3 OOM events"

            result = await plugin.investigate({
                "_cloud": "gcp",
                "_private_ip": "10.128.0.15",
                "_instance_id": "vm-prod-01",
                "_has_cloud_target": True,
                "_project": "my-project",
                "_zone": "us-central1-a",
                "alert_type": "memory_high",
                "host": "10.128.0.15",
            })

            mock_ssh.assert_called_once()
            mock_logs.assert_called_once()
            assert "cloud_investigation_gcp" in result.tool_name
            assert "SSH OUTPUT" in result.raw_output
            assert "Log Explorer" in result.raw_output

    @pytest.mark.asyncio
    async def test_gcp_resolves_ip_when_only_instance_given(self):
        from app.investigations.cloud_investigation import CloudInvestigation

        plugin = CloudInvestigation()

        with patch.object(plugin, '_resolve_gcp_ip', new_callable=AsyncMock) as mock_resolve, \
             patch.object(plugin, '_run_gcp_ssh', new_callable=AsyncMock) as mock_ssh, \
             patch.object(plugin, '_query_gcp_logs', new_callable=AsyncMock) as mock_logs:
            mock_resolve.return_value = "10.128.0.99"
            mock_ssh.return_value = "OK"
            mock_logs.return_value = "No logs"

            result = await plugin.investigate({
                "_cloud": "gcp",
                "_private_ip": "",
                "_instance_id": "vm-prod-02",
                "_has_cloud_target": True,
                "_project": "my-project",
                "_zone": "us-central1-a",
                "alert_type": "cpu_high",
                "host": "vm-prod-02",
            })

            mock_resolve.assert_called_once_with("vm-prod-02", "my-project", "us-central1-a")
            mock_ssh.assert_called_once()
