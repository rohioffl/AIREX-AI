"""
Action policy engine.

Defines approval rules, risk gating, and confidence-based auto-approval
for each registered action.

Approval decision chain:
  1. Policy lookup — unknown actions always require approval
  2. Risk gate — risk_level > max_allowed_risk blocks the action entirely
  3. Senior gate — requires_senior_approval actions need admin/senior role
  4. Auto-approve gate — auto_approve=True AND confidence >= threshold
  5. HIGH risk block — HIGH risk actions never auto-approve (configurable)
"""

from dataclasses import dataclass
from enum import Enum

import structlog

from app.models.enums import RiskLevel

logger = structlog.get_logger()

RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MED: 1,
    RiskLevel.HIGH: 2,
}


class ApprovalLevel(str, Enum):
    """The type of approval required for an action."""

    AUTO = "auto"  # No human needed (confidence gate passed)
    OPERATOR = "operator"  # Any operator/admin can approve
    SENIOR = "senior"  # Only admin can approve (requires_senior_approval)


@dataclass(frozen=True)
class ApprovalDecision:
    """Result of the approval policy evaluation."""

    requires_human: bool  # True if human must approve
    level: ApprovalLevel  # What level of approval is needed
    reason: str  # Human-readable explanation
    confidence_met: bool = True  # Whether confidence threshold was met
    senior_required: bool = False  # Whether senior/admin approval needed


@dataclass(frozen=True)
class ActionPolicy:
    """Static policy configuration for an executable action type."""

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
    "kill_process": ActionPolicy(
        action_type="kill_process",
        auto_approve=False,
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.MED,
    ),
    "flush_cache": ActionPolicy(
        action_type="flush_cache",
        auto_approve=True,
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.LOW,
    ),
    "rotate_credentials": ActionPolicy(
        action_type="rotate_credentials",
        auto_approve=False,
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
    ),
    "rollback_deployment": ActionPolicy(
        action_type="rollback_deployment",
        auto_approve=False,
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
    ),
    "resize_disk": ActionPolicy(
        action_type="resize_disk",
        auto_approve=False,
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.MED,
    ),
    "drain_node": ActionPolicy(
        action_type="drain_node",
        auto_approve=False,
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
    ),
    "toggle_feature_flag": ActionPolicy(
        action_type="toggle_feature_flag",
        auto_approve=True,
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.LOW,
    ),
    "restart_container": ActionPolicy(
        action_type="restart_container",
        auto_approve=False,
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.MED,
    ),
    "block_ip": ActionPolicy(
        action_type="block_ip",
        auto_approve=False,
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
    ),
}


def check_policy(
    action_type: str,
    risk_level: RiskLevel,
    correlation_id: str | None = None,
) -> tuple[bool, str]:
    """
    Check whether an action is allowed given the risk level.

    Returns (allowed: bool, reason: str).
    """
    policy = ACTION_POLICIES.get(action_type)
    if policy is None:
        logger.warning(
            "policy_missing",
            action=action_type,
            risk=risk_level.value,
            correlation_id=correlation_id,
        )
        return False, f"No policy defined for action: {action_type}"

    if RISK_ORDER[risk_level] > RISK_ORDER[policy.max_allowed_risk]:
        logger.warning(
            "policy_risk_blocked",
            action=action_type,
            risk=risk_level.value,
            max_allowed_risk=policy.max_allowed_risk.value,
            correlation_id=correlation_id,
        )
        return False, (
            f"Risk level {risk_level.value} exceeds max allowed "
            f"{policy.max_allowed_risk.value} for {action_type}"
        )

    logger.info(
        "policy_check_allowed",
        action=action_type,
        risk=risk_level.value,
        correlation_id=correlation_id,
    )
    return True, "allowed"


def requires_approval(action_type: str, correlation_id: str | None = None) -> bool:
    """Return True if the action requires human approval (legacy API).

    Preserved for backward compatibility. For confidence-aware decisions,
    use evaluate_approval() instead.
    """
    policy = ACTION_POLICIES.get(action_type)
    if policy is None:
        logger.warning(
            "requires_approval_policy_missing",
            action=action_type,
            correlation_id=correlation_id,
        )
        return True
    logger.info(
        "requires_approval_evaluated",
        action=action_type,
        requires_human=not policy.auto_approve,
        correlation_id=correlation_id,
    )
    return not policy.auto_approve


def evaluate_approval(
    action_type: str,
    confidence: float = 0.0,
    risk_level: RiskLevel = RiskLevel.MED,
    correlation_id: str | None = None,
) -> ApprovalDecision:
    """
    Evaluate the full approval policy for an action.

    Decision logic:
      1. Unknown action → require operator approval
      2. requires_senior_approval → require admin/senior approval
      3. auto_approve=False → require operator approval
      4. auto_approve=True but confidence < threshold → require operator approval
      5. auto_approve=True but HIGH risk + block enabled → require operator approval
      6. All gates passed → auto-approve

    Args:
        action_type: The proposed action (e.g. "restart_service").
        confidence: LLM confidence score (0.0 to 1.0).
        risk_level: Risk level of the recommendation.

    Returns:
        ApprovalDecision with requires_human, level, and reason.
    """
    from app.core.config import settings

    policy = ACTION_POLICIES.get(action_type)

    # Gate 1: Unknown action
    if policy is None:
        logger.warning(
            "approval_policy_missing",
            action=action_type,
            confidence=confidence,
            risk=risk_level.value,
            correlation_id=correlation_id,
        )
        return ApprovalDecision(
            requires_human=True,
            level=ApprovalLevel.OPERATOR,
            reason=f"No policy for action '{action_type}' — manual approval required",
        )

    # Gate 2: Senior approval required
    if policy.requires_senior_approval:
        logger.info(
            "senior_approval_required",
            action=action_type,
            confidence=confidence,
            correlation_id=correlation_id,
        )
        return ApprovalDecision(
            requires_human=True,
            level=ApprovalLevel.SENIOR,
            reason=(
                f"Action '{action_type}' requires senior/admin approval "
                f"(confidence={confidence:.2f})"
            ),
            senior_required=True,
        )

    # Gate 3: Not eligible for auto-approval
    if not policy.auto_approve:
        logger.info(
            "operator_approval_required_auto_approve_disabled",
            action=action_type,
            confidence=confidence,
            risk=risk_level.value,
            correlation_id=correlation_id,
        )
        return ApprovalDecision(
            requires_human=True,
            level=ApprovalLevel.OPERATOR,
            reason=(
                f"Action '{action_type}' requires operator approval "
                f"(auto_approve=False, confidence={confidence:.2f})"
            ),
        )

    # Gate 4: Confidence threshold check
    threshold = settings.AUTO_APPROVAL_CONFIDENCE_THRESHOLD
    if confidence < threshold:
        logger.info(
            "confidence_below_threshold",
            action=action_type,
            confidence=confidence,
            threshold=threshold,
            correlation_id=correlation_id,
        )
        return ApprovalDecision(
            requires_human=True,
            level=ApprovalLevel.OPERATOR,
            reason=(
                f"Confidence {confidence:.2f} below threshold {threshold:.2f} "
                f"for auto-approval of '{action_type}'"
            ),
            confidence_met=False,
        )

    # Gate 5: HIGH risk block
    if settings.AUTO_APPROVAL_BLOCK_HIGH_RISK and risk_level == RiskLevel.HIGH:
        logger.info(
            "auto_approval_blocked_high_risk",
            action=action_type,
            confidence=confidence,
            risk=risk_level.value,
            correlation_id=correlation_id,
        )
        return ApprovalDecision(
            requires_human=True,
            level=ApprovalLevel.OPERATOR,
            reason=(
                f"HIGH risk actions cannot be auto-approved "
                f"(action='{action_type}', confidence={confidence:.2f})"
            ),
        )

    # All gates passed — auto-approve
    logger.info(
        "auto_approval_granted",
        action=action_type,
        confidence=confidence,
        risk=risk_level.value,
        correlation_id=correlation_id,
    )
    return ApprovalDecision(
        requires_human=False,
        level=ApprovalLevel.AUTO,
        reason=(
            f"Auto-approved: '{action_type}' "
            f"(confidence={confidence:.2f} >= {threshold:.2f}, "
            f"risk={risk_level.value})"
        ),
        confidence_met=True,
    )


def get_policy(
    action_type: str, correlation_id: str | None = None
) -> ActionPolicy | None:
    """Look up the policy for an action type."""
    policy = ACTION_POLICIES.get(action_type)
    if policy is None:
        logger.warning(
            "get_policy_not_found",
            action=action_type,
            correlation_id=correlation_id,
        )
    return policy
