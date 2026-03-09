"""
FastAPI dependencies for tenant context, DB sessions, Redis, and RBAC.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, TypeAlias

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_tenant_session
from app.core.rbac import Permission, has_any_permission
from app.core.security import TokenData, decode_access_token


AUTH_ERROR_DETAIL = "Invalid or expired token"


def _decode_bearer_token_or_401(token: str) -> TokenData:
    try:
        return decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_ERROR_DETAIL,
        ) from exc


async def get_tenant_id() -> uuid.UUID:
    """Single-tenant mode: always use the primary DEV tenant ID."""
    return uuid.UUID(settings.DEV_TENANT_ID)


async def get_current_user(
    authorization: str | None = Header(None),
) -> TokenData | None:
    """
    Extract the full user token data from JWT.
    Returns None if no token provided (dev mode).
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :]
        return _decode_bearer_token_or_401(token)
    return None


def require_role(*allowed_roles: str):
    """
    RBAC dependency factory for role-based access. Usage:

        @router.post("/admin-only", dependencies=[Depends(require_role("admin"))])
        @router.post("/operator-or-admin", dependencies=[Depends(require_role("operator", "admin"))])
    """

    async def _check(
        authorization: str | None = Header(None),
    ) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            # Allow dev mode without auth
            return
        token = authorization[len("Bearer ") :]
        data = _decode_bearer_token_or_401(token)

        # Normalize role names (case-insensitive)
        user_role = data.role.lower()
        allowed_normalized = [r.lower() for r in allowed_roles]

        if user_role not in allowed_normalized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{data.role}' is not authorized. Required: {', '.join(allowed_roles)}",
            )

    return _check


def require_permission(*permissions: Permission):
    """
    RBAC dependency factory for permission-based access. Usage:

        @router.post("/delete", dependencies=[Depends(require_permission(Permission.INCIDENT_DELETE))])
        @router.get("/users", dependencies=[Depends(require_permission(Permission.USER_LIST))])
    """

    async def _check(
        authorization: str | None = Header(None),
    ) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            # Allow dev mode without auth
            return
        token = authorization[len("Bearer ") :]
        data = _decode_bearer_token_or_401(token)

        if not has_any_permission(data.role, *permissions):
            perm_names = ", ".join(p.value for p in permissions)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{data.role}' lacks required permission(s): {perm_names}",
            )

    return _check


async def get_db_session(
    tenant_id: uuid.UUID = Depends(get_tenant_id),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a tenant-scoped async DB session."""
    async with get_tenant_session(tenant_id) as session:
        yield session


async def get_redis(request: Request) -> aioredis.Redis:
    """Return the shared Redis connection from app state."""
    return request.app.state.redis


# Type aliases for cleaner route signatures
TenantId: TypeAlias = Annotated[uuid.UUID, Depends(get_tenant_id)]
TenantSession: TypeAlias = Annotated[AsyncSession, Depends(get_db_session)]
Redis: TypeAlias = Annotated[aioredis.Redis, Depends(get_redis)]
CurrentUser: TypeAlias = Annotated[TokenData | None, Depends(get_current_user)]

# RBAC type aliases
RequireAdmin: TypeAlias = Annotated[None, Depends(require_role("admin"))]
RequireOperator: TypeAlias = Annotated[None, Depends(require_role("operator", "admin"))]
