"""
Role-Based Access Control (RBAC) system.

Defines role-to-permission mappings and provides permission checking utilities.
"""

import structlog

from airex_core.models.enums import Permission, UserRole

logger = structlog.get_logger(__name__)

# Role hierarchy: ADMIN > OPERATOR > VIEWER
# Each role inherits permissions from lower roles

_ADMIN_PERMISSIONS: set[Permission] = {
    # All operator permissions
    Permission.INCIDENT_VIEW,
    Permission.INCIDENT_APPROVE,
    Permission.INCIDENT_SENIOR_APPROVE,  # admins can approve senior-gated actions
    Permission.INCIDENT_REJECT,
    Permission.INCIDENT_DELETE,
    # User management
    Permission.USER_LIST,
    Permission.USER_VIEW,
    Permission.USER_CREATE,
    Permission.USER_UPDATE,
    Permission.USER_DELETE,
    Permission.USER_CHANGE_ROLE,
    # Tenant management
    Permission.TENANT_VIEW,
    Permission.TENANT_UPDATE,
    Permission.TENANT_RELOAD_CONFIG,
    # System
    Permission.SYSTEM_METRICS,
    Permission.SYSTEM_DLQ,
    # Org-level (org admin and above)
    Permission.ORG_VIEW,
    Permission.ORG_MANAGE_MEMBERS,
    Permission.TENANT_MANAGE_MEMBERS,
}

ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.VIEWER: {
        Permission.INCIDENT_VIEW,
    },
    UserRole.OPERATOR: {
        Permission.INCIDENT_VIEW,
        Permission.INCIDENT_APPROVE,
        Permission.INCIDENT_REJECT,
    },
    UserRole.ADMIN: _ADMIN_PERMISSIONS,
    UserRole.PLATFORM_ADMIN: {
        *_ADMIN_PERMISSIONS,
        # Org CRUD
        Permission.ORG_CREATE,
        Permission.ORG_UPDATE,
        Permission.ORG_DELETE,
        # Platform-level gates
        Permission.PLATFORM_SETTINGS,
        Permission.PLATFORM_IMPERSONATE,
    },
}


def normalize_role_name(role: str) -> str:
    """Normalize scoped SaaS role names to base role values."""
    normalized = role.strip().lower()
    if normalized.startswith("org_"):
        return normalized.removeprefix("org_")
    if normalized.startswith("tenant_"):
        return normalized.removeprefix("tenant_")
    return normalized


def _parse_user_role(role: str) -> UserRole | None:
    """Parse role string into :class:`UserRole` safely."""
    try:
        return UserRole(normalize_role_name(role))
    except ValueError:
        logger.warning(
            "rbac_invalid_role",
            correlation_id=None,
            role=role,
        )
        return None


def get_permissions_for_role(role: str) -> set[Permission]:
    """
    Get all permissions for a given role string.

    Returns empty set if role is unknown.
    """
    user_role = _parse_user_role(role)
    if user_role is None:
        return set()
    return ROLE_PERMISSIONS.get(user_role, set())


def has_permission(role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in get_permissions_for_role(role)


def has_any_permission(role: str, *permissions: Permission) -> bool:
    """Check if a role has any of the specified permissions."""
    role_perms = get_permissions_for_role(role)
    return any(perm in role_perms for perm in permissions)


def has_all_permissions(role: str, *permissions: Permission) -> bool:
    """Check if a role has all of the specified permissions."""
    role_perms = get_permissions_for_role(role)
    return all(perm in role_perms for perm in permissions)


def is_admin(role: str) -> bool:
    """Check if role is admin or platform_admin."""
    user_role = _parse_user_role(role)
    return user_role in (UserRole.ADMIN, UserRole.PLATFORM_ADMIN)


def is_operator_or_admin(role: str) -> bool:
    """Check if role is operator, admin, or platform_admin."""
    user_role = _parse_user_role(role)
    if user_role is None:
        return False
    return user_role in (UserRole.OPERATOR, UserRole.ADMIN, UserRole.PLATFORM_ADMIN)
