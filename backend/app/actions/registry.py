"""
Deterministic action registry.

If an action type is not in this registry, it is REJECTED.
LLM-proposed actions must match a key here. No dynamic resolution.
"""

from app.actions.base import BaseAction
from app.actions.block_ip import BlockIpAction
from app.actions.clear_logs import ClearLogsAction
from app.actions.drain_node import DrainNodeAction
from app.actions.flush_cache import FlushCacheAction
from app.actions.kill_process import KillProcessAction
from app.actions.resize_disk import ResizeDiskAction
from app.actions.restart_container import RestartContainerAction
from app.actions.restart_service import RestartServiceAction
from app.actions.rollback_deployment import RollbackDeploymentAction
from app.actions.rotate_credentials import RotateCredentialsAction
from app.actions.scale_instances import ScaleInstancesAction
from app.actions.toggle_feature_flag import ToggleFeatureFlagAction

ACTION_REGISTRY: dict[str, type[BaseAction]] = {
    "restart_service": RestartServiceAction,
    "clear_logs": ClearLogsAction,
    "scale_instances": ScaleInstancesAction,
    "kill_process": KillProcessAction,
    "flush_cache": FlushCacheAction,
    "rotate_credentials": RotateCredentialsAction,
    "rollback_deployment": RollbackDeploymentAction,
    "resize_disk": ResizeDiskAction,
    "drain_node": DrainNodeAction,
    "toggle_feature_flag": ToggleFeatureFlagAction,
    "restart_container": RestartContainerAction,
    "block_ip": BlockIpAction,
}


def get_action(action_type: str) -> BaseAction:
    """
    Resolve an action by type from the registry.

    Raises ValueError if not found — never falls back to dynamic resolution.
    """
    cls = ACTION_REGISTRY.get(action_type)
    if cls is None:
        raise ValueError(
            f"Unknown action type: '{action_type}'. Not in ACTION_REGISTRY."
        )
    return cls()
