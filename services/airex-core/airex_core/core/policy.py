"""
Action policy engine.

Defines approval rules and risk gating for each registered action.
All actions require human approval — there is no auto-approve path.

Approval decision chain:
  1. Policy lookup — unknown actions always require approval
  2. Risk gate — risk_level > max_allowed_risk blocks the action entirely
  3. Senior gate — requires_senior_approval actions need admin/senior role
  4. Default — operator approval required
"""

from dataclasses import dataclass, field
from enum import Enum

import structlog

from airex_core.models.enums import RiskLevel

logger = structlog.get_logger()

RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MED: 1,
    RiskLevel.HIGH: 2,
}


class ApprovalLevel(str, Enum):
    """The type of approval required for an action."""

    OPERATOR = "operator"  # Any operator/admin can approve
    SENIOR = "senior"  # Only admin can approve (requires_senior_approval)


@dataclass(frozen=True)
class ApprovalDecision:
    """Result of the approval policy evaluation."""

    requires_human: bool  # Always True — execution requires human approval
    level: ApprovalLevel  # What level of approval is needed
    reason: str  # Human-readable explanation
    confidence_met: bool = True  # Informational only — does not gate execution
    senior_required: bool = False  # Whether senior/admin approval needed


@dataclass(frozen=True)
class ActionBounds:
    """Execution limits enforced before any action runs.

    Attributes:
        max_replicas:          Hard cap on target replica count (scale actions).
                               None = unrestricted.
        cooldown_seconds:      Minimum seconds between executions of this action
                               on the same incident. 0 = no cooldown.
        allowed_environments:  Whitelist of environments this action may run in
                               (matched against params["_environment"]).
                               None = unrestricted.
    """

    max_replicas: int | None = None
    cooldown_seconds: int = 0
    allowed_environments: frozenset[str] | None = None


@dataclass(frozen=True)
class ActionPolicy:
    """Static policy configuration for an executable action type."""

    action_type: str
    requires_senior_approval: bool
    max_allowed_risk: RiskLevel
    bounds: ActionBounds = field(default_factory=ActionBounds)
    required_scope_fields: frozenset[str] = field(default_factory=frozenset)


ACTION_POLICIES: dict[str, ActionPolicy] = {
    "restart_service": ActionPolicy(
        action_type="restart_service",
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.HIGH,
        bounds=ActionBounds(cooldown_seconds=30),
    ),
    "clear_logs": ActionPolicy(
        action_type="clear_logs",
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.MED,
        bounds=ActionBounds(cooldown_seconds=0),
    ),
    "scale_instances": ActionPolicy(
        action_type="scale_instances",
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
        bounds=ActionBounds(max_replicas=20, cooldown_seconds=300),
    ),
    "kill_process": ActionPolicy(
        action_type="kill_process",
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.MED,
        bounds=ActionBounds(cooldown_seconds=30),
    ),
    "flush_cache": ActionPolicy(
        action_type="flush_cache",
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.LOW,
        bounds=ActionBounds(cooldown_seconds=60),
    ),
    "rotate_credentials": ActionPolicy(
        action_type="rotate_credentials",
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
        bounds=ActionBounds(cooldown_seconds=3600),
    ),
    "rollback_deployment": ActionPolicy(
        action_type="rollback_deployment",
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
        bounds=ActionBounds(cooldown_seconds=300),
    ),
    "resize_disk": ActionPolicy(
        action_type="resize_disk",
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.MED,
        bounds=ActionBounds(cooldown_seconds=1800),
    ),
    "drain_node": ActionPolicy(
        action_type="drain_node",
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
        bounds=ActionBounds(cooldown_seconds=600),
        required_scope_fields=frozenset({"_instance_id"}),
    ),
    "toggle_feature_flag": ActionPolicy(
        action_type="toggle_feature_flag",
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.LOW,
        bounds=ActionBounds(cooldown_seconds=60),
    ),
    "restart_container": ActionPolicy(
        action_type="restart_container",
        requires_senior_approval=False,
        max_allowed_risk=RiskLevel.MED,
        bounds=ActionBounds(cooldown_seconds=30),
    ),
    "block_ip": ActionPolicy(
        action_type="block_ip",
        requires_senior_approval=True,
        max_allowed_risk=RiskLevel.HIGH,
        bounds=ActionBounds(cooldown_seconds=300),
        required_scope_fields=frozenset({"_target_ip"}),
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
    """Return True — all actions require human approval.

    Preserved for backward compatibility.
    """
    logger.info(
        "requires_approval_evaluated",
        action=action_type,
        requires_human=True,
        correlation_id=correlation_id,
    )
    return True


def evaluate_approval(
    action_type: str,
    confidence: float = 0.0,
    risk_level: RiskLevel = RiskLevel.MED,
    correlation_id: str | None = None,
) -> ApprovalDecision:
    """
    Evaluate the approval policy for an action.

    All actions require human approval. This function determines the approval
    level (OPERATOR vs SENIOR) and provides a human-readable reason.

    Decision logic:
      1. Unknown action → require operator approval
      2. requires_senior_approval → require admin/senior approval
      3. Default → require operator approval

    Args:
        action_type: The proposed action (e.g. "restart_service").
        confidence: LLM confidence score (0.0 to 1.0) — informational only.
        risk_level: Risk level of the recommendation — informational only.

    Returns:
        ApprovalDecision with requires_human=True always.
    """
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

    # Default: operator approval
    logger.info(
        "operator_approval_required",
        action=action_type,
        confidence=confidence,
        risk=risk_level.value,
        correlation_id=correlation_id,
    )
    return ApprovalDecision(
        requires_human=True,
        level=ApprovalLevel.OPERATOR,
        reason=f"Action '{action_type}' requires operator approval",
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


def check_bounds(
    action_type: str,
    params: dict,
    correlation_id: str | None = None,
) -> tuple[bool, str]:
    """Phase 3a: Enforce action execution bounds.

    Checks:
      - max_replicas cap (for scale actions)
      - Environment whitelist guard

    Returns (allowed: bool, reason: str).
    """
    policy = ACTION_POLICIES.get(action_type)
    if policy is None:
        return True, "no policy — skipping bounds check"

    bounds = policy.bounds

    # Replica cap
    if bounds.max_replicas is not None:
        requested = params.get("desired_capacity") or params.get("target_replicas")
        if requested is not None:
            try:
                if int(requested) > bounds.max_replicas:
                    reason = (
                        f"Requested replicas {requested} exceeds max "
                        f"{bounds.max_replicas} for {action_type}"
                    )
                    logger.warning(
                        "bounds_replicas_exceeded",
                        action=action_type,
                        requested=requested,
                        max_replicas=bounds.max_replicas,
                        correlation_id=correlation_id,
                    )
                    return False, reason
            except (TypeError, ValueError):
                pass

    # Environment guard
    if bounds.allowed_environments is not None:
        env = (
            params.get("_environment") or params.get("environment") or ""
        ).lower().strip()
        if env and env not in bounds.allowed_environments:
            reason = (
                f"Environment '{env}' not in allowed list "
                f"{sorted(bounds.allowed_environments)} for {action_type}"
            )
            logger.warning(
                "bounds_env_blocked",
                action=action_type,
                environment=env,
                allowed=sorted(bounds.allowed_environments),
                correlation_id=correlation_id,
            )
            return False, reason

    logger.info(
        "bounds_check_passed",
        action=action_type,
        correlation_id=correlation_id,
    )
    return True, "bounds check passed"


def check_scope(
    action_type: str,
    params: dict,
    correlation_id: str | None = None,
) -> tuple[bool, str]:
    """Phase 3c: Validate required targeting fields are present.

    Ensures high-blast-radius actions are never run without explicit target
    identification (prevents 'target nothing' or cross-tenant drift).

    Returns (allowed: bool, reason: str).
    """
    policy = ACTION_POLICIES.get(action_type)
    if policy is None:
        return True, "no policy — skipping scope check"

    missing = [f for f in policy.required_scope_fields if not params.get(f)]
    if missing:
        reason = (
            f"Missing required scope fields for {action_type}: {missing}. "
            "Add these fields to the incident meta before approving."
        )
        logger.warning(
            "scope_check_failed",
            action=action_type,
            missing_fields=missing,
            correlation_id=correlation_id,
        )
        return False, reason

    logger.info(
        "scope_check_passed",
        action=action_type,
        correlation_id=correlation_id,
    )
    return True, "scope check passed"
