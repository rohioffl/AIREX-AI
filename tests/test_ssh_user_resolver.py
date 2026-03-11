"""Tests for SSH user resolver — per-machine auto-detection and config lookup."""

import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

import airex_core.cloud.tenant_config as _tc_mod
from airex_core.cloud.ssh_user_resolver import (
    _GCP_IMAGE_USER_MAP,
    _AWS_AMI_USER_MAP,
    _match_image_pattern,
    _get_cached,
    _set_cached,
    _ssh_user_cache,
    clear_cache,
    resolve_ssh_user,
)
from airex_core.cloud.tenant_config import (
    get_ssh_user_for_host,
    get_tenant_config,
)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear both tenant config cache and SSH user cache between tests."""
    _tc_mod._config_cache = {}
    _tc_mod._cache_timestamp = 0.0
    clear_cache()
    yield
    _tc_mod._config_cache = {}
    _tc_mod._cache_timestamp = 0.0
    clear_cache()


def _write_config(data: dict) -> str:
    """Write a dict as YAML to a temp file and return the path."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix="airex_test_"
    )
    yaml.dump(data, tmp)
    tmp.close()
    return tmp.name


# ── Sample configs ───────────────────────────────────────────────

CONFIG_WITH_SERVERS = {
    "defaults": {
        "ssh_user": "ubuntu",
    },
    "tenants": {
        "multi-user-tenant": {
            "display_name": "Multi User Tenant",
            "cloud": "gcp",
            "ssh_user": "wacko",
            "gcp": {"project_id": "my-project"},
            "servers": [
                {
                    "name": "vm-web-01",
                    "private_ip": "10.128.0.15",
                    "ssh_user": "admin",
                    "role": "web",
                },
                {
                    "name": "vm-db-01",
                    "private_ip": "10.128.0.20",
                    "ssh_user": "postgres",
                    "role": "database",
                },
                {
                    "name": "vm-app-01",
                    "private_ip": "10.128.0.25",
                    # no ssh_user — should fall back to tenant-level
                    "role": "app",
                },
            ],
        },
        "aws-tenant": {
            "display_name": "AWS Tenant",
            "cloud": "aws",
            "ssh_user": "ec2-user",
            "servers": [
                {
                    "name": "web-prod",
                    "instance_id": "i-0abc123",
                    "private_ip": "172.31.10.5",
                    "ssh_user": "ubuntu",
                },
            ],
        },
        "no-ssh-user-tenant": {
            "display_name": "No SSH User",
            "cloud": "gcp",
            "gcp": {"project_id": "bare-project"},
            # no ssh_user at all — should use defaults.ssh_user
        },
    },
}


# ═══════════════════════════════════════════════════════════════════
#  Image pattern matching tests
# ═══════════════════════════════════════════════════════════════════


class TestImagePatternMatching:
    """Test _match_image_pattern against known OS image strings."""

    def test_gcp_ubuntu_image(self):
        img = "projects/ubuntu-os-cloud/global/images/ubuntu-2204-jammy-v20240101"
        assert _match_image_pattern(img, _GCP_IMAGE_USER_MAP) == "ubuntu"

    def test_gcp_debian_image(self):
        img = "projects/debian-cloud/global/images/debian-11-bullseye-v20240101"
        assert _match_image_pattern(img, _GCP_IMAGE_USER_MAP) == "admin"

    def test_gcp_centos_image(self):
        img = "projects/centos-cloud/global/images/centos-7-v20240101"
        assert _match_image_pattern(img, _GCP_IMAGE_USER_MAP) == "centos"

    def test_gcp_cos_image(self):
        img = "projects/cos-cloud/global/images/cos-stable-101-v20240101"
        assert _match_image_pattern(img, _GCP_IMAGE_USER_MAP) == "chronos"

    def test_gcp_rhel_image(self):
        img = "projects/rhel-cloud/global/images/rhel-8-v20240101"
        assert _match_image_pattern(img, _GCP_IMAGE_USER_MAP) == "ec2-user"

    def test_gcp_rocky_image(self):
        img = "projects/rocky-linux-cloud/global/images/rocky-linux-9-v20240101"
        assert _match_image_pattern(img, _GCP_IMAGE_USER_MAP) == "rocky"

    def test_gcp_container_optimized(self):
        img = "projects/cos-cloud/global/images/container-optimized-os-stable"
        assert _match_image_pattern(img, _GCP_IMAGE_USER_MAP) == "chronos"

    def test_aws_ubuntu_ami(self):
        ami = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20240101"
        assert _match_image_pattern(ami, _AWS_AMI_USER_MAP) == "ubuntu"

    def test_aws_amazon_linux_ami(self):
        ami = "amzn2-ami-hvm-2.0.20240101-x86_64-gp2"
        assert _match_image_pattern(ami, _AWS_AMI_USER_MAP) == "ec2-user"

    def test_aws_al2023_ami(self):
        ami = "al2023-ami-2023.3.20240101-kernel-6.1-x86_64"
        assert _match_image_pattern(ami, _AWS_AMI_USER_MAP) == "ec2-user"

    def test_aws_debian_ami(self):
        ami = "debian-11-amd64-20240101-1234"
        assert _match_image_pattern(ami, _AWS_AMI_USER_MAP) == "admin"

    def test_aws_centos_ami(self):
        ami = "CentOS-7-2111-20211221_1-x86_64-GP2"
        assert _match_image_pattern(ami, _AWS_AMI_USER_MAP) == "centos"

    def test_aws_bitnami_ami(self):
        ami = "bitnami-wordpress-6.4.2-0-linux-debian-12-x86_64"
        assert _match_image_pattern(ami, _AWS_AMI_USER_MAP) == "bitnami"

    def test_unknown_image_returns_empty(self):
        assert (
            _match_image_pattern("custom-golden-image-v42", _GCP_IMAGE_USER_MAP) == ""
        )
        assert _match_image_pattern("my-custom-ami-2024", _AWS_AMI_USER_MAP) == ""

    def test_case_insensitive_matching(self):
        assert _match_image_pattern("UBUNTU-IMAGE-V1", _GCP_IMAGE_USER_MAP) == "ubuntu"
        assert _match_image_pattern("Amazon-Linux-2", _AWS_AMI_USER_MAP) == "ec2-user"


# ═══════════════════════════════════════════════════════════════════
#  In-process cache tests
# ═══════════════════════════════════════════════════════════════════


class TestSSHUserCache:
    """Test the in-process SSH user cache."""

    def test_cache_set_and_get(self):
        _set_cached("gcp", "vm-web-01", "wacko")
        assert _get_cached("gcp", "vm-web-01") == "wacko"

    def test_cache_miss(self):
        assert _get_cached("gcp", "nonexistent-vm") is None

    def test_cache_clear(self):
        _set_cached("gcp", "vm-web-01", "wacko")
        clear_cache()
        assert _get_cached("gcp", "vm-web-01") is None

    def test_cache_different_clouds(self):
        _set_cached("gcp", "instance-1", "wacko")
        _set_cached("aws", "instance-1", "ec2-user")
        assert _get_cached("gcp", "instance-1") == "wacko"
        assert _get_cached("aws", "instance-1") == "ec2-user"

    def test_cache_case_insensitive_cloud(self):
        _set_cached("GCP", "vm-01", "wacko")
        assert _get_cached("gcp", "vm-01") == "wacko"


# ═══════════════════════════════════════════════════════════════════
#  Tenant config SSH user parsing (bug fix verification)
# ═══════════════════════════════════════════════════════════════════


class TestTenantConfigSSHUserParsing:
    """Verify the SSH user parsing bug fix — top-level ssh_user is now read."""

    def test_top_level_ssh_user_is_parsed(self):
        """Previously broken: top-level ssh_user was silently ignored."""
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            config = get_tenant_config("multi-user-tenant", config_path=path)
            assert config is not None
            assert config.ssh.user == "wacko"  # was always "ubuntu" before fix
        finally:
            os.unlink(path)

    def test_defaults_ssh_user_applied(self):
        """Tenant with no ssh_user should inherit from defaults."""
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            config = get_tenant_config("no-ssh-user-tenant", config_path=path)
            assert config is not None
            assert config.ssh.user == "ubuntu"  # from defaults
        finally:
            os.unlink(path)

    def test_nested_ssh_block_still_works(self):
        """Nested ssh: block should still take precedence."""
        data = {
            "defaults": {"ssh_user": "ubuntu"},
            "tenants": {
                "nested-ssh": {
                    "cloud": "gcp",
                    "ssh_user": "top-level-user",
                    "ssh": {
                        "user": "nested-user",
                        "port": 2222,
                    },
                },
            },
        }
        path = _write_config(data)
        try:
            config = get_tenant_config("nested-ssh", config_path=path)
            assert config.ssh.user == "nested-user"  # nested wins
            assert config.ssh.port == 2222
        finally:
            os.unlink(path)

    def test_server_entry_ssh_user_parsed(self):
        """Per-server ssh_user should be read into ServerEntry."""
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            config = get_tenant_config("multi-user-tenant", config_path=path)
            assert len(config.servers) == 3
            assert config.servers[0].ssh_user == "admin"
            assert config.servers[1].ssh_user == "postgres"
            assert config.servers[2].ssh_user == ""  # no override
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════
#  get_ssh_user_for_host tests
# ═══════════════════════════════════════════════════════════════════


class TestGetSSHUserForHost:
    """Test the static config lookup (per-server > per-tenant)."""

    def test_per_server_by_ip(self):
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            user = get_ssh_user_for_host(
                "multi-user-tenant", host_ip="10.128.0.15", config_path=path
            )
            assert user == "admin"
        finally:
            os.unlink(path)

    def test_per_server_by_instance_id(self):
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            user = get_ssh_user_for_host(
                "aws-tenant", instance_id="i-0abc123", config_path=path
            )
            assert user == "ubuntu"
        finally:
            os.unlink(path)

    def test_fallback_to_tenant_level(self):
        """Server without ssh_user should fall back to tenant-level."""
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            user = get_ssh_user_for_host(
                "multi-user-tenant", host_ip="10.128.0.25", config_path=path
            )
            assert user == "wacko"  # tenant-level ssh_user
        finally:
            os.unlink(path)

    def test_unknown_host_falls_back_to_tenant(self):
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            user = get_ssh_user_for_host(
                "multi-user-tenant", host_ip="10.128.0.99", config_path=path
            )
            assert user == "wacko"  # tenant-level
        finally:
            os.unlink(path)

    def test_unknown_tenant_returns_empty(self):
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            user = get_ssh_user_for_host(
                "nonexistent", host_ip="10.0.0.1", config_path=path
            )
            assert user == ""
        finally:
            os.unlink(path)

    def test_no_ssh_user_tenant_uses_defaults(self):
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            user = get_ssh_user_for_host(
                "no-ssh-user-tenant", host_ip="10.0.0.1", config_path=path
            )
            assert user == "ubuntu"  # from defaults
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════
#  resolve_ssh_user integration tests (with mocked cloud APIs)
# ═══════════════════════════════════════════════════════════════════


class TestResolveSSHUser:
    """Test the full resolution chain: config > cache > cloud API > fallback."""

    @pytest.mark.asyncio
    async def test_static_config_takes_priority(self):
        """Per-server config should win over everything else via resolve_ssh_user."""
        path = _write_config(CONFIG_WITH_SERVERS)
        try:
            # Patch at the source module — resolve_ssh_user imports lazily
            with patch(
                "airex_core.cloud.tenant_config.get_ssh_user_for_host",
                return_value="admin",
            ) as mock_lookup:
                user = await resolve_ssh_user(
                    cloud="gcp",
                    tenant_name="multi-user-tenant",
                    private_ip="10.128.0.15",
                )
                assert user == "admin"
                mock_lookup.assert_called_once_with(
                    "multi-user-tenant",
                    host_ip="10.128.0.15",
                    instance_id="",
                )
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_cache_hit_skips_cloud_api(self):
        """Cached value should be returned without calling cloud APIs."""
        _set_cached("gcp", "vm-cached-01", "cached-user")

        with patch("airex_core.cloud.ssh_user_resolver._detect_gcp_ssh_user") as mock_detect:
            user = await resolve_ssh_user(
                cloud="gcp",
                private_ip="",
                instance_name="vm-cached-01",
            )
            assert user == "cached-user"
            mock_detect.assert_not_called()

    @pytest.mark.asyncio
    async def test_gcp_auto_detection_called(self):
        """When no config/cache, GCP detection should be called."""
        with patch(
            "airex_core.cloud.ssh_user_resolver._detect_gcp_ssh_user",
            new_callable=AsyncMock,
            return_value="detected-user",
        ) as mock_detect:
            user = await resolve_ssh_user(
                cloud="gcp",
                instance_name="vm-new-01",
                project="my-project",
                zone="us-central1-a",
            )
            assert user == "detected-user"
            mock_detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_aws_auto_detection_called(self):
        """When no config/cache, AWS detection should be called."""
        with patch(
            "airex_core.cloud.ssh_user_resolver._detect_aws_ssh_user",
            new_callable=AsyncMock,
            return_value="ec2-user",
        ) as mock_detect:
            user = await resolve_ssh_user(
                cloud="aws",
                instance_id="i-0new456",
                region="us-east-1",
            )
            assert user == "ec2-user"
            mock_detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_detection_result_is_cached(self):
        """Auto-detected user should be stored in cache."""
        with patch(
            "airex_core.cloud.ssh_user_resolver._detect_gcp_ssh_user",
            new_callable=AsyncMock,
            return_value="detected-wacko",
        ):
            await resolve_ssh_user(
                cloud="gcp",
                instance_name="vm-cacheable-01",
                project="proj",
                zone="zone-a",
            )
        assert _get_cached("gcp", "vm-cacheable-01") == "detected-wacko"

    @pytest.mark.asyncio
    async def test_fallback_to_settings(self):
        """When nothing resolves, should use settings.SSH_USER."""
        with patch(
            "airex_core.cloud.ssh_user_resolver._detect_gcp_ssh_user",
            new_callable=AsyncMock,
            return_value="",
        ):
            with patch("airex_core.cloud.ssh_user_resolver.settings") as mock_settings:
                mock_settings.SSH_USER = "global-fallback"
                user = await resolve_ssh_user(
                    cloud="gcp",
                    instance_name="vm-unknown-01",
                    project="proj",
                    zone="zone-a",
                )
                assert user == "global-fallback"

    @pytest.mark.asyncio
    async def test_fallback_to_ubuntu_when_no_settings(self):
        """Ultimate fallback should be 'ubuntu'."""
        with patch(
            "airex_core.cloud.ssh_user_resolver._detect_gcp_ssh_user",
            new_callable=AsyncMock,
            return_value="",
        ):
            with patch("airex_core.cloud.ssh_user_resolver.settings") as mock_settings:
                mock_settings.SSH_USER = ""
                user = await resolve_ssh_user(
                    cloud="gcp",
                    instance_name="vm-bare-01",
                    project="proj",
                    zone="zone-a",
                )
                assert user == "ubuntu"

    @pytest.mark.asyncio
    async def test_unknown_cloud_falls_back(self):
        """Unknown cloud should skip detection and use fallback."""
        user = await resolve_ssh_user(
            cloud="azure",
            instance_id="vm-azure-01",
        )
        # Should get settings.SSH_USER or "ubuntu"
        assert user  # not empty

    @pytest.mark.asyncio
    async def test_empty_identifiers_still_resolves(self):
        """Even with no identifiers, should return a valid user."""
        user = await resolve_ssh_user(cloud="gcp")
        assert user  # not empty
