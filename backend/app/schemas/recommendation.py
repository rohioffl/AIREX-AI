from pydantic import BaseModel, Field

from app.models.enums import RiskLevel


class Recommendation(BaseModel):
    """Structured AI recommendation. proposed_action MUST exist in ACTION_REGISTRY."""

    root_cause: str
    proposed_action: str
    risk_level: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)
