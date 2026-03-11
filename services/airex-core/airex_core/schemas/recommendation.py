from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from airex_core.models.enums import RiskLevel


class ReasoningStep(BaseModel):
    """A single step in the AI's reasoning chain."""

    step: int
    description: str
    evidence_used: str = ""


class AlternativeRecommendation(BaseModel):
    """An alternative action the AI considered."""

    action: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel = RiskLevel.MED

    @field_validator("action", "rationale", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class Recommendation(BaseModel):
    """Structured AI recommendation. proposed_action MUST exist in ACTION_REGISTRY."""

    # ── Core fields (backward-compatible) ────────────────────────
    root_cause: str
    proposed_action: str
    risk_level: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)

    # ── Enhanced fields (Phase 6) ────────────────────────────────
    summary: str = ""
    root_cause_category: str = ""  # e.g. "resource_exhaustion", "deployment", "network"
    contributing_factors: list[str] = Field(default_factory=list)
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    rationale: str = ""  # Why this action was chosen over alternatives
    blast_radius: str = ""  # Impact scope: "single_instance", "service", "cluster"
    alternatives: list[AlternativeRecommendation] = Field(default_factory=list)
    evidence_annotations: list[str] = Field(default_factory=list)
    verification_criteria: list[str] = Field(default_factory=list)

    @field_validator("root_cause", "proposed_action", mode="before")
    @classmethod
    def normalize_core_text_fields(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value
