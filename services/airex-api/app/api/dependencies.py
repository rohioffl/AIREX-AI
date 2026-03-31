"""
FastAPI dependencies for tenant context, DB sessions, Redis, and RBAC.
"""

import hmac
import hashlib
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Annotated, TypeAlias

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.config import settings
from airex_core.core.database import async_session_factory, get_tenant_session
from airex_core.core.rbac import Permission, has_any_permission, normalize_role_name
from airex_core.core.security import TokenData, decode_access_token
from airex_core.models.api_key import ApiKey
from airex_core.models.monitoring_integration import MonitoringIntegration
from airex_core.models.organization_membership import OrganizationMembership
from airex_core.models.tenant import Tenant
from airex_core.models.tenant_membership import TenantMembership


AUTH_ERROR_DETAIL = "Invalid or expired token"


def _decode_bearer_token_or_401(token: str) -> TokenData:
    try:
        return decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_ERROR_DETAIL,
        ) from exc


async def _resolve_api_key_token(raw_key: str) -> TokenData:
    """Validate an API key and return a synthetic TokenData for the org."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    async with async_session_factory() as session:
        result = await session.execute(
            select(ApiKey, Tenant.id).join(
                Tenant, Tenant.organization_id == ApiKey.organization_id
            ).where(
                ApiKey.key_hash == key_hash,
                ApiKey.revoked_at.is_(None),
                Tenant.is_active.is_(True),
            )
        )
        row = result.first()

    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=AUTH_ERROR_DETAIL)

    api_key, tenant_id = row

    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")

    return TokenData(
        sub=f"apikey:{api_key.id}",
        tenant_id=tenant_id,
        role="operator",
    )


async def get_current_user(
    authorization: str | None = Header(None),
) -> TokenData | None:
    """
    Extract the full user token data from JWT or API key.
    Returns None if no token provided (dev mode).
    """
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :]
        return _decode_bearer_token_or_401(token)
    if authorization.startswith("ApiKey "):
        raw_key = authorization[len("ApiKey ") :]
        return await _resolve_api_key_token(raw_key)
    return None


async def get_auth_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a non-RLS session for auth/bootstrap and membership checks."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def resolve_active_tenant_id(
    session: AsyncSession,
    current_user: TokenData | None,
    active_tenant_id: str | None,
) -> uuid.UUID:
    """Resolve the effective tenant for the current request."""
    try:
        parsed_active_tenant_id = uuid.UUID(active_tenant_id) if active_tenant_id else None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid active tenant identifier",
        ) from exc

    if current_user is None:
        if parsed_active_tenant_id:
            return parsed_active_tenant_id
        return uuid.UUID(settings.DEV_TENANT_ID)

    requested_tenant_id = parsed_active_tenant_id or current_user.tenant_id
    if requested_tenant_id == current_user.tenant_id:
        return requested_tenant_id

    tenant_result = await session.execute(
        select(Tenant.id, Tenant.organization_id, Tenant.is_active).where(Tenant.id == requested_tenant_id)
    )
    tenant_row = tenant_result.first()
    if tenant_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    organization_id = tenant_row.organization_id
    is_active = tenant_row.is_active
    if not is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is inactive")

    if organization_id is not None:
        org_membership_result = await session.execute(
            select(OrganizationMembership.role).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == current_user.user_id,
                ~OrganizationMembership.role.like("pending\\_%", escape="\\"),
            )
        )
        if org_membership_result.scalar_one_or_none() is not None:
            return requested_tenant_id

    tenant_membership_result = await session.execute(
        select(TenantMembership.role).where(
            TenantMembership.tenant_id == requested_tenant_id,
            TenantMembership.user_id == current_user.user_id,
        )
    )
    if tenant_membership_result.scalar_one_or_none() is not None:
        return requested_tenant_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access requested tenant",
    )


def require_authenticated_user(current_user: TokenData | None) -> TokenData:
    """Require a decoded access token for SaaS-protected routes."""
    if current_user is None or current_user.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


async def require_internal_tool_access(
    x_internal_tool_token: str | None = Header(None, alias="X-Internal-Tool-Token"),
) -> None:
    """Require the shared secret used by the internal OpenClaw tool server."""
    configured_token = settings.OPENCLAW_TOOL_SERVER_TOKEN or settings.OPENCLAW_GATEWAY_TOKEN
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal tool server token is not configured",
        )
    if not x_internal_tool_token or not hmac.compare_digest(
        x_internal_tool_token,
        configured_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal tool token",
        )


async def get_authenticated_user(
    current_user: TokenData | None = Depends(get_current_user),
) -> TokenData:
    """Dependency wrapper requiring an authenticated user."""
    return require_authenticated_user(current_user)


async def get_home_organization_id(
    session: AsyncSession,
    current_user: TokenData,
) -> uuid.UUID | None:
    """Return the organization that owns the user's home tenant."""
    result = await session.execute(
        select(Tenant.organization_id).where(Tenant.id == current_user.tenant_id)
    )
    return result.scalar_one_or_none()


async def has_org_membership(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> bool:
    """Return True if the user is a member of the organization."""
    result = await session.execute(
        select(OrganizationMembership.role).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            ~OrganizationMembership.role.like("pending\\_%", escape="\\"),
        )
    )
    return result.scalar_one_or_none() is not None


async def has_org_admin_membership(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> bool:
    """Return True if the user has admin rights on the organization."""
    result = await session.execute(
        select(OrganizationMembership.role).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            ~OrganizationMembership.role.like("pending\\_%", escape="\\"),
        )
    )
    role = result.scalar_one_or_none()
    return role is not None and normalize_role_name(str(role)) in ("admin", "platform_admin")


async def has_tenant_membership(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    """Return True if the user has any membership on the tenant."""
    result = await session.execute(
        select(TenantMembership.role).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def authorize_org_access(
    session: AsyncSession,
    current_user: TokenData,
    organization_id: uuid.UUID,
) -> bool:
    """Check if the user can access the organization."""
    if current_user.role.lower() == "platform_admin":
        return True

    home_org_id = await get_home_organization_id(session, current_user)
    if home_org_id == organization_id:
        return True

    return await has_org_membership(
        session, user_id=current_user.user_id, organization_id=organization_id
    )


async def authorize_org_admin(
    session: AsyncSession,
    current_user: TokenData,
    organization_id: uuid.UUID,
) -> bool:
    """Check if the user has admin rights for the organization."""
    if normalize_role_name(current_user.role) in ("admin", "platform_admin"):
        if current_user.role.lower() == "platform_admin":
            return True
        home_org_id = await get_home_organization_id(session, current_user)
        if home_org_id == organization_id:
            return True

    return await has_org_admin_membership(
        session, user_id=current_user.user_id, organization_id=organization_id
    )


async def authorize_tenant_access(
    session: AsyncSession,
    current_user: TokenData,
    tenant_id: uuid.UUID,
) -> bool:
    """Check if the user can access the tenant."""
    try:
        resolved = await resolve_active_tenant_id(
            session=session,
            current_user=current_user,
            active_tenant_id=str(tenant_id),
        )
    except HTTPException as exc:
        if exc.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}:
            return False
        raise
    return resolved == tenant_id


async def authorize_tenant_admin(
    session: AsyncSession,
    current_user: TokenData,
    tenant_id: uuid.UUID,
) -> bool:
    """Check if the user has admin rights for the tenant."""
    normalized = normalize_role_name(current_user.role)
    if normalized == "platform_admin":
        return True

    tenant_org_result = await session.execute(
        select(Tenant.organization_id).where(Tenant.id == tenant_id)
    )
    tenant_organization_id = tenant_org_result.scalar_one_or_none()
    if tenant_organization_id is not None and await authorize_org_admin(
        session, current_user, tenant_organization_id
    ):
        return True

    if normalized != "admin":
        result = await session.execute(
            select(TenantMembership.role).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == current_user.user_id,
            )
        )
        role = result.scalar_one_or_none()
        return role is not None and normalize_role_name(str(role)) == "admin"

    return await authorize_tenant_access(session, current_user, tenant_id)


def require_role(*allowed_roles: str):
    """
    RBAC dependency factory for role-based access. Usage:

        @router.post("/admin-only", dependencies=[Depends(require_role("admin"))])
        @router.post("/operator-or-admin", dependencies=[Depends(require_role("operator", "admin"))])
    """

    async def _check(
        current_user: TokenData | None = Depends(get_current_user),
        session: AsyncSession = Depends(get_auth_session),
        x_active_tenant_id: str | None = Header(None, alias="X-Active-Tenant-Id"),
        x_tenant_id: str | None = Header(None, alias="X-Tenant-Id"),
    ) -> None:
        if current_user is None:
            # Allow dev mode without auth
            return

        user_role = normalize_role_name(current_user.role)
        allowed_normalized = [normalize_role_name(r) for r in allowed_roles]

        if user_role not in allowed_normalized:
            requested_tenant_id = x_active_tenant_id or x_tenant_id
            if requested_tenant_id:
                try:
                    tenant_uuid = uuid.UUID(requested_tenant_id)
                except ValueError:
                    tenant_uuid = None
                if tenant_uuid is not None:
                    if "viewer" in allowed_normalized and await authorize_tenant_access(
                        session, current_user, tenant_uuid
                    ):
                        return
                    if any(role in allowed_normalized for role in ("operator", "admin")) and await authorize_tenant_admin(
                        session, current_user, tenant_uuid
                    ):
                        return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized. Required: {', '.join(allowed_roles)}",
            )

    return _check


def require_permission(*permissions: Permission):
    """
    RBAC dependency factory for permission-based access. Usage:

        @router.post("/delete", dependencies=[Depends(require_permission(Permission.INCIDENT_DELETE))])
        @router.get("/users", dependencies=[Depends(require_permission(Permission.USER_LIST))])
    """

    async def _check(
        current_user: TokenData | None = Depends(get_current_user),
        session: AsyncSession = Depends(get_auth_session),
        x_active_tenant_id: str | None = Header(None, alias="X-Active-Tenant-Id"),
        x_tenant_id: str | None = Header(None, alias="X-Tenant-Id"),
    ) -> None:
        if current_user is None:
            # Allow dev mode without auth
            return

        if has_any_permission(current_user.role, *permissions):
            return

        requested_tenant_id = x_active_tenant_id or x_tenant_id
        if requested_tenant_id:
            try:
                tenant_uuid = uuid.UUID(requested_tenant_id)
            except ValueError:
                tenant_uuid = None
            if tenant_uuid is not None:
                if await authorize_tenant_admin(session, current_user, tenant_uuid):
                    return
                if all(permission == Permission.INCIDENT_VIEW for permission in permissions) and await authorize_tenant_access(
                    session, current_user, tenant_uuid
                ):
                    return

        if not has_any_permission(current_user.role, *permissions):
            perm_names = ", ".join(p.value for p in permissions)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' lacks required permission(s): {perm_names}",
            )

    return _check


async def get_redis(request: Request) -> aioredis.Redis:
    """Return the shared Redis connection from app state."""
    return request.app.state.redis


async def get_tenant_id(
    current_user: TokenData | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_auth_session),
    x_active_tenant_id: str | None = Header(None, alias="X-Active-Tenant-Id"),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-Id"),
    integration_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Resolve the active tenant using auth context and optional tenant headers."""
    if integration_id is not None and current_user is None:
        integration_result = await session.execute(
            select(MonitoringIntegration.tenant_id, MonitoringIntegration.enabled).where(
                MonitoringIntegration.id == integration_id
            )
        )
        integration = integration_result.one_or_none()
        if integration is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
        tenant_id, enabled = integration
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Integration is disabled",
            )
        return tenant_id

    requested_tenant_id = x_active_tenant_id or x_tenant_id
    return await resolve_active_tenant_id(
        session=session,
        current_user=current_user,
        active_tenant_id=requested_tenant_id,
    )


async def get_db_session(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a tenant-scoped async DB session."""
    async with get_tenant_session(tenant_id) as session:
        yield session


# Type aliases for cleaner route signatures
TenantId: TypeAlias = Annotated[uuid.UUID, Depends(get_tenant_id)]
TenantSession: TypeAlias = Annotated[AsyncSession, Depends(get_db_session)]
Redis: TypeAlias = Annotated[aioredis.Redis, Depends(get_redis)]
CurrentUser: TypeAlias = Annotated[TokenData | None, Depends(get_current_user)]

# RBAC type aliases
RequireAdmin: TypeAlias = Annotated[None, Depends(require_role("admin"))]
RequireOperator: TypeAlias = Annotated[None, Depends(require_role("operator", "admin"))]
RequireViewer: TypeAlias = Annotated[None, Depends(require_role("viewer", "operator", "admin"))]

# Permission-based type aliases (for use in function signatures)
def RequirePermission(*permissions: Permission):
    """Create a type alias for permission-based access control."""
    return Annotated[None, Depends(require_permission(*permissions))]


def require_platform_admin():
    """Dependency factory that enforces platform_admin role."""

    async def _check(
        current_user: TokenData | None = Depends(get_current_user),
    ) -> None:
        if current_user is None:
            # Allow dev mode without auth
            return
        if normalize_role_name(current_user.role) != "platform_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform admin access required",
            )

    return _check


RequirePlatformAdmin: TypeAlias = Annotated[None, Depends(require_platform_admin())]
