"""
Deterministic action registry.

If an action type is not in this registry, it is REJECTED.
LLM-proposed actions must match a key here. No dynamic resolution.
"""

from app.actions.base import BaseAction
from app.actions.clear_logs import ClearLogsAction
from app.actions.restart_service import RestartServiceAction
from app.actions.scale_instances import ScaleInstancesAction

ACTION_REGISTRY: dict[str, type[BaseAction]] = {
    "restart_service": RestartServiceAction,
    "clear_logs": ClearLogsAction,
    "scale_instances": ScaleInstancesAction,
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
