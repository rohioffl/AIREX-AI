"""Tests for action registry and action execution."""

import pytest

from app.actions.registry import ACTION_REGISTRY, get_action
from app.actions.base import BaseAction, ActionResult
from app.actions.restart_service import RestartServiceAction
from app.actions.clear_logs import ClearLogsAction
from app.actions.scale_instances import ScaleInstancesAction


class TestActionRegistry:
    def test_registry_has_restart_service(self):
        assert "restart_service" in ACTION_REGISTRY

    def test_registry_has_clear_logs(self):
        assert "clear_logs" in ACTION_REGISTRY

    def test_registry_has_scale_instances(self):
        assert "scale_instances" in ACTION_REGISTRY

    def test_registry_size(self):
        assert len(ACTION_REGISTRY) == 3

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
