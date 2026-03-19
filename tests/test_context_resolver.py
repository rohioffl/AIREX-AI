"""Tests for Phase 3e: Execution Context Resolver."""

from airex_core.core.context_resolver import ExecutionContext, resolve_execution_context


class TestResolveExecutionContextExecMode:
    """exec_mode derivation: ssm | ssh | sim."""

    def test_aws_with_instance_id_is_ssm(self):
        ctx = resolve_execution_context({"_cloud": "aws", "_instance_id": "i-abc123"})
        assert ctx.exec_mode == "ssm"
        assert ctx.cloud == "aws"
        assert ctx.instance_id == "i-abc123"

    def test_gcp_with_instance_id_is_ssh(self):
        ctx = resolve_execution_context({"_cloud": "gcp", "_instance_id": "my-vm"})
        assert ctx.exec_mode == "ssh"
        assert ctx.cloud == "gcp"

    def test_aws_without_instance_id_is_sim(self):
        ctx = resolve_execution_context({"_cloud": "aws"})
        assert ctx.exec_mode == "sim"

    def test_gcp_without_instance_id_is_sim(self):
        ctx = resolve_execution_context({"_cloud": "gcp"})
        assert ctx.exec_mode == "sim"

    def test_unknown_cloud_is_sim(self):
        ctx = resolve_execution_context({"_cloud": "azure", "_instance_id": "vm-1"})
        assert ctx.exec_mode == "sim"

    def test_empty_params_is_sim(self):
        ctx = resolve_execution_context({})
        assert ctx.exec_mode == "sim"
        assert ctx.cloud == "unknown"


class TestResolveExecutionContextFieldResolution:
    """Field extraction with underscore-prefix priority."""

    def test_underscore_prefix_takes_precedence(self):
        ctx = resolve_execution_context({"_cloud": "aws", "cloud": "gcp"})
        assert ctx.cloud == "aws"

    def test_plain_key_fallback_when_no_prefix(self):
        ctx = resolve_execution_context({"cloud": "gcp", "_instance_id": "vm-1"})
        assert ctx.cloud == "gcp"

    def test_region_resolved(self):
        ctx = resolve_execution_context({"_region": "ap-south-1"})
        assert ctx.region == "ap-south-1"

    def test_region_plain_key_fallback(self):
        ctx = resolve_execution_context({"region": "us-east-1"})
        assert ctx.region == "us-east-1"

    def test_zone_resolved(self):
        ctx = resolve_execution_context({"_zone": "ap-south-1a"})
        assert ctx.zone == "ap-south-1a"

    def test_zone_gcp_zone_fallback(self):
        ctx = resolve_execution_context({"_gcp_zone": "asia-south1-a"})
        assert ctx.zone == "asia-south1-a"

    def test_environment_normalised_lowercase(self):
        ctx = resolve_execution_context({"_environment": "PROD"})
        assert ctx.environment == "prod"

    def test_environment_defaults_to_unknown(self):
        ctx = resolve_execution_context({})
        assert ctx.environment == "unknown"

    def test_namespace_resolved(self):
        ctx = resolve_execution_context({"_namespace": "kube-system"})
        assert ctx.namespace == "kube-system"

    def test_cluster_resolved(self):
        ctx = resolve_execution_context({"_cluster": "prod-cluster"})
        assert ctx.cluster == "prod-cluster"

    def test_service_name_resolved(self):
        ctx = resolve_execution_context({"service_name": "payment-api"})
        assert ctx.service_name == "payment-api"

    def test_tenant_name_resolved(self):
        ctx = resolve_execution_context({"_tenant_name": "acme"})
        assert ctx.tenant_name == "acme"

    def test_whitespace_stripped(self):
        ctx = resolve_execution_context({"_region": "  ap-south-1  "})
        assert ctx.region == "ap-south-1"


class TestResolveExecutionContextReturnType:
    def test_returns_execution_context_instance(self):
        ctx = resolve_execution_context({})
        assert isinstance(ctx, ExecutionContext)

    def test_all_defaults_when_empty(self):
        ctx = resolve_execution_context({})
        assert ctx.cloud == "unknown"
        assert ctx.instance_id == ""
        assert ctx.region == ""
        assert ctx.zone == ""
        assert ctx.exec_mode == "sim"
        assert ctx.environment == "unknown"
        assert ctx.namespace == ""
        assert ctx.cluster == ""
        assert ctx.service_name == ""
        assert ctx.tenant_name == ""

    def test_full_aws_context(self):
        ctx = resolve_execution_context({
            "_cloud": "aws",
            "_instance_id": "i-0abc123",
            "_region": "us-east-1",
            "_zone": "us-east-1a",
            "_environment": "prod",
            "_namespace": "default",
            "_cluster": "eks-prod",
            "service_name": "api",
            "_tenant_name": "customer-a",
        })
        assert ctx.cloud == "aws"
        assert ctx.instance_id == "i-0abc123"
        assert ctx.region == "us-east-1"
        assert ctx.zone == "us-east-1a"
        assert ctx.exec_mode == "ssm"
        assert ctx.environment == "prod"
        assert ctx.namespace == "default"
        assert ctx.cluster == "eks-prod"
        assert ctx.service_name == "api"
        assert ctx.tenant_name == "customer-a"

    def test_full_gcp_context(self):
        ctx = resolve_execution_context({
            "_cloud": "gcp",
            "_instance_id": "my-gce-instance",
            "_region": "asia-south1",
            "_gcp_zone": "asia-south1-a",
            "_environment": "staging",
        })
        assert ctx.cloud == "gcp"
        assert ctx.exec_mode == "ssh"
        assert ctx.zone == "asia-south1-a"
        assert ctx.environment == "staging"
