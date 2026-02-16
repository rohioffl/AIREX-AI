"""
FastAPI dependencies for tenant context, DB sessions, Redis, and RBAC.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_tenant_session
from app.core.security import TokenData, decode_access_token


async def get_tenant_id(
    x_tenant_id: str | None = Header(None),
    authorization: str | None = Header(None),
) -> uuid.UUID:
    """
    Extract tenant_id from JWT bearer token or X-Tenant-Id dev header.

    Priority: JWT claim > X-Tenant-Id header > DEV_TENANT_ID fallback.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        try:
            data = decode_access_token(token)
            return data.tenant_id
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

    if x_tenant_id:
        try:
            return uuid.UUID(x_tenant_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Tenant-Id header",
            ) from exc

    return uuid.UUID(settings.DEV_TENANT_ID)


async def get_current_user(
    authorization: str | None = Header(None),
) -> TokenData | None:
    """
    Extract the full user token data from JWT.
    Returns None if no token provided (dev mode).
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
        try:
            return decode_access_token(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
    return None


def require_role(*allowed_roles: str):
    """
    RBAC dependency factory. Usage:

        @router.post("/admin-only", dependencies=[Depends(require_role("admin"))])
    """
    async def _check(
        authorization: str | None = Header(None),
    ):
        if not authorization or not authorization.startswith("Bearer "):
            # Allow dev mode without auth
            return
        token = authorization[len("Bearer "):]
        try:
            data = decode_access_token(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        if data.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{data.role}' is not authorized. Required: {', '.join(allowed_roles)}",
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
TenantId = Annotated[uuid.UUID, Depends(get_tenant_id)]
TenantSession = Annotated[AsyncSession, Depends(get_db_session)]
Redis = Annotated[aioredis.Redis, Depends(get_redis)]
CurrentUser = Annotated[TokenData | None, Depends(get_current_user)]
