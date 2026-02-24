import enum


class IncidentState(str, enum.Enum):
    """Immutable incident lifecycle states. No additional states allowed."""

    RECEIVED = "RECEIVED"
    INVESTIGATING = "INVESTIGATING"
    RECOMMENDATION_READY = "RECOMMENDATION_READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    FAILED_ANALYSIS = "FAILED_ANALYSIS"
    FAILED_EXECUTION = "FAILED_EXECUTION"
    FAILED_VERIFICATION = "FAILED_VERIFICATION"


class SeverityLevel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
