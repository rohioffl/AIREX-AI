"""
Deterministic action registry.

If an action type is not in this registry, it is REJECTED.
LLM-proposed actions must match a key here. No dynamic resolution.
"""

from airex_core.actions.base import BaseAction
from airex_core.actions.block_ip import BlockIpAction
from airex_core.actions.clear_logs import ClearLogsAction
from airex_core.actions.drain_node import DrainNodeAction
from airex_core.actions.flush_cache import FlushCacheAction
from airex_core.actions.kill_process import KillProcessAction
from airex_core.actions.resize_disk import ResizeDiskAction
from airex_core.actions.restart_container import RestartContainerAction
from airex_core.actions.restart_service import RestartServiceAction
from airex_core.actions.rollback_deployment import RollbackDeploymentAction
from airex_core.actions.rotate_credentials import RotateCredentialsAction
from airex_core.actions.scale_instances import ScaleInstancesAction
from airex_core.actions.toggle_feature_flag import ToggleFeatureFlagAction

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
