from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from airex_core.models.enums import RiskLevel
from airex_core.schemas.recommendation import Recommendation


class ConfidenceBreakdown(BaseModel):
    """Deterministic confidence components used for approval decisions."""

    model_confidence: float = Field(ge=0.0, le=1.0)
    evidence_strength_score: float = Field(ge=0.0, le=1.0)
    tool_grounding_score: float = Field(ge=0.0, le=1.0)
    kg_match_score: float = Field(ge=0.0, le=1.0)
    hallucination_penalty: float = Field(ge=0.0, le=1.0)
    composite_confidence: float = Field(ge=0.0, le=1.0)
    warning: str = ""


class ImpactEstimate(BaseModel):
    """Deterministic preview of likely remediation side effects."""

    cost_delta: str = "low"
    dependency_pressure: str = "low"
    resource_limit_risk: str = "low"
    blast_radius_summary: str = ""
    scale_delta: int | None = None
    notes: list[str] = Field(default_factory=list)


class ExecutionGuard(BaseModel):
    """Deterministic scope validation result for approval and execution."""

    valid: bool = True
    reason: str = ""
    enforcement_mode: str = "legacy"
    credential_scope_valid: bool = True
    cluster_ownership_valid: bool = True
    namespace_scope_valid: bool = True
    cross_tenant_denied: bool = False
    binding_id: str = ""
    target_scope: dict[str, str] = Field(default_factory=dict)


class RecommendationContract(BaseModel):
    """Explicit execution-facing recommendation contract."""

    action_type: str = "execute_fix"
    action_id: str
    target: str = ""
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    risk: str = RiskLevel.MED.value
    root_cause: str = ""
    summary: str = ""
    rationale: str = ""
    blast_radius: str = ""
    root_cause_category: str = ""
    contributing_factors: list[str] = Field(default_factory=list)
    reasoning_chain: list[dict[str, Any]] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    evidence_annotations: list[str] = Field(default_factory=list)
    verification_criteria: list[str] = Field(default_factory=list)
    confidence_breakdown: ConfidenceBreakdown | None = None
    grounding_summary: str = ""
    impact_estimate: ImpactEstimate | None = None
    execution_guard: ExecutionGuard | None = None

    @field_validator(
        "action_type",
        "action_id",
        "target",
        "reason",
        "risk",
        "root_cause",
        "summary",
        "rationale",
        "blast_radius",
        "root_cause_category",
        "grounding_summary",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @classmethod
    def from_recommendation(
        cls,
        recommendation: Recommendation,
        *,
        confidence_breakdown: ConfidenceBreakdown | dict[str, Any] | None = None,
        grounding_summary: str = "",
        impact_estimate: ImpactEstimate | dict[str, Any] | None = None,
        execution_guard: ExecutionGuard | dict[str, Any] | None = None,
    ) -> "RecommendationContract":
        payload = recommendation.model_dump()
        normalized_breakdown: ConfidenceBreakdown | None = None
        normalized_impact: ImpactEstimate | None = None
        normalized_guard: ExecutionGuard | None = None
        if confidence_breakdown is not None:
            normalized_breakdown = ConfidenceBreakdown.model_validate(confidence_breakdown)
        if impact_estimate is not None:
            normalized_impact = ImpactEstimate.model_validate(impact_estimate)
        if execution_guard is not None:
            normalized_guard = ExecutionGuard.model_validate(execution_guard)
        return cls(
            action_type=recommendation.action_type or "execute_fix",
            action_id=recommendation.action_id or recommendation.proposed_action,
            target=recommendation.target,
            params=recommendation.params,
            reason=recommendation.reason or recommendation.rationale or recommendation.summary,
            confidence=recommendation.confidence,
            risk=recommendation.risk_level.value,
            root_cause=recommendation.root_cause,
            summary=recommendation.summary,
            rationale=recommendation.rationale,
            blast_radius=recommendation.blast_radius,
            root_cause_category=recommendation.root_cause_category,
            contributing_factors=payload.get("contributing_factors", []),
            reasoning_chain=payload.get("reasoning_chain", []),
            alternatives=payload.get("alternatives", []),
            evidence_annotations=payload.get("evidence_annotations", []),
            verification_criteria=payload.get("verification_criteria", []),
            confidence_breakdown=normalized_breakdown,
            grounding_summary=grounding_summary,
            impact_estimate=normalized_impact,
            execution_guard=normalized_guard,
        )

    def to_legacy_recommendation(self) -> dict[str, Any]:
        """Compatibility view for current UI/API consumers."""
        return {
            "root_cause": self.root_cause,
            "proposed_action": self.action_id,
            "risk_level": self.risk,
            "confidence": self.confidence,
            "action_type": self.action_type,
            "action_id": self.action_id,
            "target": self.target,
            "params": self.params,
            "reason": self.reason,
            "summary": self.summary,
            "rationale": self.rationale,
            "blast_radius": self.blast_radius,
            "root_cause_category": self.root_cause_category,
            "contributing_factors": self.contributing_factors,
            "reasoning_chain": self.reasoning_chain,
            "alternatives": self.alternatives,
            "evidence_annotations": self.evidence_annotations,
            "verification_criteria": self.verification_criteria,
            "confidence_breakdown": (
                self.confidence_breakdown.model_dump() if self.confidence_breakdown else None
            ),
            "grounding_summary": self.grounding_summary,
            "impact_estimate": self.impact_estimate.model_dump() if self.impact_estimate else None,
            "execution_guard": self.execution_guard.model_dump() if self.execution_guard else None,
        }


def resolve_recommendation_contract(meta: dict[str, Any] | None) -> RecommendationContract | None:
    """Return the contract from meta, accepting either the new or legacy shape."""
    if not meta:
        return None

    contract_payload = meta.get("recommendation_contract")
    if isinstance(contract_payload, dict):
        return RecommendationContract.model_validate(contract_payload)

    legacy_payload = meta.get("recommendation")
    if not isinstance(legacy_payload, dict):
        return None

    proposed_action = legacy_payload.get("proposed_action") or legacy_payload.get("action_id")
    risk = legacy_payload.get("risk_level") or legacy_payload.get("risk") or RiskLevel.MED.value
    if not proposed_action:
        return None

    return RecommendationContract(
        action_type=str(legacy_payload.get("action_type") or "execute_fix"),
        action_id=str(proposed_action),
        target=str(legacy_payload.get("target") or ""),
        params=legacy_payload.get("params") if isinstance(legacy_payload.get("params"), dict) else {},
        reason=str(legacy_payload.get("reason") or legacy_payload.get("summary") or ""),
        confidence=float(legacy_payload.get("confidence", 0.0)),
        risk=str(risk),
        root_cause=str(legacy_payload.get("root_cause") or ""),
        summary=str(legacy_payload.get("summary") or ""),
        rationale=str(legacy_payload.get("rationale") or ""),
        blast_radius=str(legacy_payload.get("blast_radius") or ""),
        root_cause_category=str(legacy_payload.get("root_cause_category") or ""),
        contributing_factors=legacy_payload.get("contributing_factors", []),
        reasoning_chain=legacy_payload.get("reasoning_chain", []),
        alternatives=legacy_payload.get("alternatives", []),
        evidence_annotations=legacy_payload.get("evidence_annotations", []),
        verification_criteria=legacy_payload.get("verification_criteria", []),
        confidence_breakdown=legacy_payload.get("confidence_breakdown"),
        grounding_summary=str(legacy_payload.get("grounding_summary") or ""),
        impact_estimate=legacy_payload.get("impact_estimate"),
        execution_guard=legacy_payload.get("execution_guard"),
    )


__all__ = [
    "ConfidenceBreakdown",
    "ExecutionGuard",
    "ImpactEstimate",
    "RecommendationContract",
    "resolve_recommendation_contract",
]
