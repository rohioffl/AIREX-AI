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


class UserRole(str, enum.Enum):
    """User roles with hierarchical permissions."""

    OPERATOR = "operator"  # Default: view incidents, approve/reject
    ADMIN = (
        "admin"  # Full access: user management, tenant config, all operator permissions
    )
    VIEWER = "viewer"  # Read-only: view incidents, no approvals


class Permission(str, enum.Enum):
    """Granular permissions for fine-grained access control."""

    # Incident permissions
    INCIDENT_VIEW = "incident:view"
    INCIDENT_APPROVE = "incident:approve"
    INCIDENT_SENIOR_APPROVE = (
        "incident:senior_approve"  # approve high-risk / senior-gated actions
    )
    INCIDENT_REJECT = "incident:reject"
    INCIDENT_DELETE = "incident:delete"

    # User management permissions
    USER_LIST = "user:list"
    USER_VIEW = "user:view"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_CHANGE_ROLE = "user:change_role"

    # Tenant management permissions
    TENANT_VIEW = "tenant:view"
    TENANT_UPDATE = "tenant:update"
    TENANT_RELOAD_CONFIG = "tenant:reload_config"

    # System permissions
    SYSTEM_METRICS = "system:metrics"
    SYSTEM_DLQ = "system:dlq"
