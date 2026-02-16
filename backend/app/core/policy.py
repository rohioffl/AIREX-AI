"""
Action policy engine.

Defines approval rules and risk gating for each registered action.
"""

from dataclasses import dataclass

from app.models.enums import RiskLevel

RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MED: 1,
    RiskLevel.HIGH: 2,
}


@dataclass(frozen=True)
class ActionPolicy:
    action_type: str
    auto_approve: bool
    requires_senior_approval: bool
    max_allowed_risk: RiskLevel


ACTION_POLICIES: dict[str, ActionPolicy] = {
    "restart_service": ActionPolicy(
        action_type="restart_service",
        auto_approve=False,
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.HIGH,
    ),
    "clear_logs": ActionPolicy(
        action_type="clear_logs",
        auto_approve=True,
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.MED,
    ),
    "scale_instances": ActionPolicy(
        action_type="scale_instances",
        auto_approve=False,
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
    ),
}


def check_policy(action_type: str, risk_level: RiskLevel) -> tuple[bool, str]:
    """
    Check whether an action is allowed given the risk level.

    Returns (allowed: bool, reason: str).
    """
    policy = ACTION_POLICIES.get(action_type)
    if policy is None:
        return False, f"No policy defined for action: {action_type}"

    if RISK_ORDER[risk_level] > RISK_ORDER[policy.max_allowed_risk]:
        return False, (
            f"Risk level {risk_level.value} exceeds max allowed "
            f"{policy.max_allowed_risk.value} for {action_type}"
        )

    return True, "allowed"


def requires_approval(action_type: str) -> bool:
    """Return True if the action requires human approval."""
    policy = ACTION_POLICIES.get(action_type)
    if policy is None:
        return True
    return not policy.auto_approve
