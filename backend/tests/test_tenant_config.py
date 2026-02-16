"""Tests for tenant configuration loader and auto-discovery enrichment."""

import os
import tempfile

import pytest
import yaml

from app.cloud.tenant_config import (
    get_tenant_config,
    list_tenants,
    _load_raw_config,
)
import app.cloud.tenant_config as _tc_mod
from app.cloud.tag_parser import parse_tags
from app.cloud.discovery import DiscoveredInstance


@pytest.fixture(autouse=True)
def _clear_tenant_cache():
    """Clear the tenant config cache between tests."""
    _tc_mod._config_cache = {}
    _tc_mod._cache_timestamp = 0.0
    yield
    _tc_mod._config_cache = {}
    _tc_mod._cache_timestamp = 0.0


def _write_config(data: dict) -> str:
    """Write a dict as YAML to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix="airex_test_"
    )
    yaml.dump(data, tmp)
    tmp.close()
    return tmp.name


SAMPLE_CONFIG = {
    "defaults": {
        "ssh_user": "ubuntu",
        "investigation_timeout": 60,
    },
    "tenants": {
        "acme-corp": {
            "display_name": "Acme Corporation",
            "cloud": "gcp",
            "gcp": {
                "project_id": "acme-production",
            },
            "escalation_email": "sre@acme.com",
        },
        "beta-inc": {
            "display_name": "Beta Inc.",
            "cloud": "aws",
            "aws": {
                "region": "ap-south-1",
            },
            "escalation_email": "ops@beta.com",
        },
    },
}


class TestTenantConfigLoader:
    """Test loading and parsing the minimal tenant config."""

    def test_load_config_file(self):
        path = _write_config(SAMPLE_CONFIG)
        try:
            data = _load_raw_config(path)
            assert "tenants" in data
            assert "acme-corp" in data["tenants"]
            assert "beta-inc" in data["tenants"]
        finally:
            os.unlink(path)

    def test_get_gcp_tenant(self):
        path = _write_config(SAMPLE_CONFIG)
        try:
            config = get_tenant_config("acme-corp", config_path=path)
            assert config is not None
            assert config.tenant_name == "acme-corp"
            assert config.display_name == "Acme Corporation"
            assert config.cloud == "gcp"
            assert config.gcp.project_id == "acme-production"
            assert config.escalation_email == "sre@acme.com"
        finally:
            os.unlink(path)

    def test_get_aws_tenant(self):
        path = _write_config(SAMPLE_CONFIG)
        try:
            config = get_tenant_config("beta-inc", config_path=path)
            assert config is not None
            assert config.cloud == "aws"
            assert config.aws.region == "ap-south-1"
        finally:
            os.unlink(path)

    def test_case_insensitive_lookup(self):
        path = _write_config(SAMPLE_CONFIG)
        try:
            config = get_tenant_config("ACME-CORP", config_path=path)
            assert config is not None
            assert config.tenant_name == "acme-corp"
        finally:
            os.unlink(path)

    def test_unknown_tenant_returns_none(self):
        path = _write_config(SAMPLE_CONFIG)
        try:
            assert get_tenant_config("nonexistent", config_path=path) is None
        finally:
            os.unlink(path)

    def test_empty_tenant_returns_none(self):
        assert get_tenant_config("") is None

    def test_list_tenants(self):
        path = _write_config(SAMPLE_CONFIG)
        try:
            names = list_tenants(config_path=path)
            assert "acme-corp" in names
            assert "beta-inc" in names
        finally:
            os.unlink(path)

    def test_missing_config_file(self):
        assert _load_raw_config("/nonexistent/path.yaml") == {}


class TestMinimalConfig:
    """Verify the config works with only cloud + project + email."""

    def test_minimal_gcp(self):
        data = {
            "tenants": {
                "simple-client": {
                    "cloud": "gcp",
                    "gcp": {"project_id": "my-project"},
                    "escalation_email": "team@client.com",
                },
            },
        }
        path = _write_config(data)
        try:
            config = get_tenant_config("simple-client", config_path=path)
            assert config.cloud == "gcp"
            assert config.gcp.project_id == "my-project"
            assert config.gcp.zone == ""  # auto-discovered later
            assert config.escalation_email == "team@client.com"
        finally:
            os.unlink(path)

    def test_minimal_aws(self):
        data = {
            "tenants": {
                "aws-client": {
                    "cloud": "aws",
                    "escalation_email": "ops@aws-client.com",
                },
            },
        }
        path = _write_config(data)
        try:
            config = get_tenant_config("aws-client", config_path=path)
            assert config.cloud == "aws"
            assert config.aws.region == ""  # empty = auto-discover
            assert config.escalation_email == "ops@aws-client.com"
        finally:
            os.unlink(path)

    def test_display_name_defaults_to_key(self):
        data = {"tenants": {"my-org": {"cloud": "gcp"}}}
        path = _write_config(data)
        try:
            config = get_tenant_config("my-org", config_path=path)
            assert config.display_name == "my-org"
        finally:
            os.unlink(path)


class TestDiscoveredInstance:
    """Test the DiscoveredInstance dataclass."""

    def test_gcp_instance(self):
        inst = DiscoveredInstance(
            cloud="gcp",
            instance_name="vm-prod-web-01",
            instance_id="vm-prod-web-01",
            private_ip="10.128.0.15",
            zone="asia-south1-a",
            region="asia-south1",
            machine_type="e2-medium",
            status="RUNNING",
        )
        assert inst.cloud == "gcp"
        assert inst.zone == "asia-south1-a"
        assert inst.region == "asia-south1"

    def test_aws_instance(self):
        inst = DiscoveredInstance(
            cloud="aws",
            instance_name="prod-api",
            instance_id="i-0abc123",
            private_ip="172.31.5.42",
            zone="ap-south-1a",
            region="ap-south-1",
            machine_type="t3.medium",
            status="running",
        )
        assert inst.cloud == "aws"
        assert inst.instance_id == "i-0abc123"


class TestTagParserEnrichment:
    """Test that tag parser enriches from tenant config."""

    def test_tags_fill_cloud_from_config(self):
        """tenant:smart-ops tag should auto-fill cloud=gcp from config."""
        # This test uses the real config file at config/tenants.yaml
        ctx = parse_tags("tenant:smart-ops,ip:10.128.0.15")
        assert ctx.cloud == "gcp"
        assert ctx.project == "smartops-automation"
        assert ctx.private_ip == "10.128.0.15"
        assert ctx.has_target is True

    def test_tags_fill_aws_region_from_config(self):
        ctx = parse_tags("tenant:beta-inc,ip:172.31.5.42")
        assert ctx.cloud == "aws"
        assert ctx.private_ip == "172.31.5.42"

    def test_webhook_tags_override_config(self):
        """Explicit cloud tag in webhook overrides config."""
        ctx = parse_tags("tenant:acme-corp,cloud:aws,ip:10.0.0.1")
        assert ctx.cloud == "aws"  # webhook says aws, not gcp from config

    def test_no_tenant_tag_no_enrichment(self):
        ctx = parse_tags("ip:10.0.0.1")
        assert ctx.cloud == ""  # no tenant tag, no enrichment
        assert ctx.project == ""


class TestAWSAuthConfig:
    """Test AWS role assumption and static key config parsing."""

    def test_role_assumption_config(self):
        data = {
            "tenants": {
                "role-client": {
                    "cloud": "aws",
                    "aws": {
                        "account_id": "111222333444",
                        "role_name": "AirexReadOnly",
                        "external_id": "airex-secret",
                        "region": "us-west-2",
                    },
                },
            },
        }
        path = _write_config(data)
        try:
            config = get_tenant_config("role-client", config_path=path)
            assert config.aws.account_id == "111222333444"
            assert config.aws.role_name == "AirexReadOnly"
            assert config.aws.external_id == "airex-secret"
            assert config.aws.get_role_arn() == "arn:aws:iam::111222333444:role/AirexReadOnly"
        finally:
            os.unlink(path)

    def test_explicit_role_arn(self):
        data = {
            "tenants": {
                "arn-client": {
                    "cloud": "aws",
                    "aws": {
                        "role_arn": "arn:aws:iam::999888777666:role/CustomRole",
                    },
                },
            },
        }
        path = _write_config(data)
        try:
            config = get_tenant_config("arn-client", config_path=path)
            assert config.aws.get_role_arn() == "arn:aws:iam::999888777666:role/CustomRole"
        finally:
            os.unlink(path)

    def test_static_key_credentials_file(self):
        data = {
            "tenants": {
                "key-client": {
                    "cloud": "aws",
                    "aws": {
                        "credentials_file": "config/credentials/my-client-aws.json",
                        "region": "eu-west-1",
                    },
                },
            },
        }
        path = _write_config(data)
        try:
            config = get_tenant_config("key-client", config_path=path)
            assert config.aws.credentials_file == "config/credentials/my-client-aws.json"
            assert config.aws.region == "eu-west-1"
            assert config.aws.get_role_arn() == ""  # no role configured
        finally:
            os.unlink(path)

    def test_no_aws_auth_uses_defaults(self):
        data = {
            "tenants": {
                "default-client": {
                    "cloud": "aws",
                },
            },
        }
        path = _write_config(data)
        try:
            config = get_tenant_config("default-client", config_path=path)
            assert config.aws.get_role_arn() == ""
            assert config.aws.credentials_file == ""
            assert config.aws.access_key_id == ""
            assert config.aws.region == ""  # empty = auto-discover all regions
        finally:
            os.unlink(path)
