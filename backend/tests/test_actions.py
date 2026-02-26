"""Tests for action registry and action execution."""

import pytest

from app.actions.registry import ACTION_REGISTRY, get_action
from app.actions.base import BaseAction, ActionResult
from app.actions.restart_service import RestartServiceAction
from app.actions.clear_logs import ClearLogsAction
from app.actions.scale_instances import ScaleInstancesAction
from app.actions.kill_process import KillProcessAction
from app.actions.flush_cache import FlushCacheAction
from app.actions.rotate_credentials import RotateCredentialsAction
from app.actions.rollback_deployment import RollbackDeploymentAction
from app.actions.resize_disk import ResizeDiskAction
from app.actions.drain_node import DrainNodeAction
from app.actions.toggle_feature_flag import ToggleFeatureFlagAction
from app.actions.restart_container import RestartContainerAction
from app.actions.block_ip import BlockIpAction


ALL_ACTION_NAMES = [
    "restart_service",
    "clear_logs",
    "scale_instances",
    "kill_process",
    "flush_cache",
    "rotate_credentials",
    "rollback_deployment",
    "resize_disk",
    "drain_node",
    "toggle_feature_flag",
    "restart_container",
    "block_ip",
]


class TestActionRegistry:
    def test_registry_has_restart_service(self):
        assert "restart_service" in ACTION_REGISTRY

    def test_registry_has_clear_logs(self):
        assert "clear_logs" in ACTION_REGISTRY

    def test_registry_has_scale_instances(self):
        assert "scale_instances" in ACTION_REGISTRY

    def test_registry_has_all_new_actions(self):
        for name in ALL_ACTION_NAMES:
            assert name in ACTION_REGISTRY, f"Missing from registry: {name}"

    def test_registry_size(self):
        assert len(ACTION_REGISTRY) == 12

    def test_get_action_returns_instance(self):
        action = get_action("restart_service")
        assert isinstance(action, RestartServiceAction)
        assert isinstance(action, BaseAction)

    def test_get_action_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown action type"):
            get_action("delete_everything")

    def test_get_action_rejects_dynamic_names(self):
        """LLM-proposed actions not in registry must be rejected."""
        with pytest.raises(ValueError):
            get_action("rm -rf /")

    def test_registry_values_are_base_action_subclasses(self):
        for name, cls in ACTION_REGISTRY.items():
            assert issubclass(cls, BaseAction), f"{name} is not a BaseAction subclass"

    def test_all_actions_have_action_type(self):
        for name in ALL_ACTION_NAMES:
            action = get_action(name)
            assert action.action_type == name, f"{name} has wrong action_type"

    def test_all_actions_have_execute_and_verify(self):
        for name in ALL_ACTION_NAMES:
            action = get_action(name)
            assert hasattr(action, "execute"), f"{name} missing execute()"
            assert hasattr(action, "verify"), f"{name} missing verify()"


class TestActionPolicyAlignment:
    def test_all_registry_actions_have_policies(self):
        from app.core.policy import ACTION_POLICIES
        missing = set(ACTION_REGISTRY.keys()) - set(ACTION_POLICIES.keys())
        assert not missing, f"Actions missing policies: {missing}"

    def test_no_orphaned_policies(self):
        from app.core.policy import ACTION_POLICIES
        extra = set(ACTION_POLICIES.keys()) - set(ACTION_REGISTRY.keys())
        assert not extra, f"Orphaned policies: {extra}"

    def test_all_actions_in_llm_prompt(self):
        from app.llm.prompts import SYSTEM_PROMPT
        for name in ALL_ACTION_NAMES:
            assert name in SYSTEM_PROMPT, f"{name} not in SYSTEM_PROMPT"


class TestRestartServiceAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = RestartServiceAction()
        result = await action.execute({"service_name": "nginx"})
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert "nginx" in result.logs

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = RestartServiceAction()
        result = await action.verify({})
        assert isinstance(result, bool)


class TestClearLogsAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = ClearLogsAction()
        result = await action.execute({"log_path": "/var/log/app"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = ClearLogsAction()
        result = await action.verify({})
        assert isinstance(result, bool)


class TestScaleInstancesAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = ScaleInstancesAction()
        result = await action.execute({"service_name": "web-app", "current_instances": 2, "target_instances": 4})
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert "Auto Scaling Group" in result.logs

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = ScaleInstancesAction()
        result = await action.verify({})
        assert isinstance(result, bool)


class TestKillProcessAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = KillProcessAction()
        result = await action.execute({"process_name": "runaway_worker"})
        assert isinstance(result, ActionResult)
        assert result.success is True
        assert "runaway_worker" in result.logs

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = KillProcessAction()
        result = await action.verify({"process_name": "runaway_worker"})
        assert isinstance(result, bool)


class TestFlushCacheAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = FlushCacheAction()
        result = await action.execute({"cache_type": "redis"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = FlushCacheAction()
        result = await action.verify({})
        assert isinstance(result, bool)


class TestRotateCredentialsAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = RotateCredentialsAction()
        result = await action.execute({"credential_type": "ssl_cert"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = RotateCredentialsAction()
        result = await action.verify({})
        assert isinstance(result, bool)


class TestRollbackDeploymentAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = RollbackDeploymentAction()
        result = await action.execute({"deployment_name": "web-api"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = RollbackDeploymentAction()
        result = await action.verify({"deployment_name": "web-api"})
        assert isinstance(result, bool)


class TestResizeDiskAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = ResizeDiskAction()
        result = await action.execute({"disk_device": "/dev/xvda1", "mount_point": "/"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = ResizeDiskAction()
        result = await action.verify({"mount_point": "/"})
        assert isinstance(result, bool)


class TestDrainNodeAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = DrainNodeAction()
        result = await action.execute({"node_name": "worker-1"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = DrainNodeAction()
        result = await action.verify({"node_name": "worker-1"})
        assert isinstance(result, bool)


class TestToggleFeatureFlagAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = ToggleFeatureFlagAction()
        result = await action.execute({"flag_name": "new_ui"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = ToggleFeatureFlagAction()
        result = await action.verify({"flag_name": "new_ui"})
        assert isinstance(result, bool)


class TestRestartContainerAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = RestartContainerAction()
        result = await action.execute({"container_name": "app-server"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = RestartContainerAction()
        result = await action.verify({"container_name": "app-server"})
        assert isinstance(result, bool)


class TestBlockIpAction:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        action = BlockIpAction()
        result = await action.execute({"malicious_ip": "192.168.1.100"})
        assert isinstance(result, ActionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_verify_returns_bool(self):
        action = BlockIpAction()
        result = await action.verify({"malicious_ip": "192.168.1.100"})
        assert isinstance(result, bool)
