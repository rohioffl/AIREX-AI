"""Platform admin authentication endpoints.

Completely isolated from the tenant user system — queries ONLY the
platform_admins table via its own database session.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.platform_admin_db import get_platform_admin_session
from airex_core.core.rate_limit import auth_rate_limit
from airex_core.core.security import (
    GoogleLoginRequest,
    LoginRequest,
    TokenResponse,
    create_access_token,
    create_refresh_token,
    verify_password,
)
from airex_core.core.config import settings
from airex_core.models.platform_admin import PlatformAdmin

logger = structlog.get_logger()

router = APIRouter()

# Sentinel tenant UUID embedded in platform admin JWTs — not a real tenant.
_PLATFORM_SENTINEL_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _verify_google_id_token(token: str) -> dict[str, object]:
    """Verify a Google ID token and return its claims."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )
    try:
        claims = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            settings.GOOGLE_OAUTH_CLIENT_ID,
        )
        return dict(claims)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token",
        ) from exc


@router.post("/admin/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def platform_admin_login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_platform_admin_session),
) -> TokenResponse:
    """Authenticate a platform admin via email + password.

    Only succeeds for accounts in the platform_admins table.
    Tenant users cannot login through this endpoint.
    """
    normalized_email = body.email.strip().lower()
    result = await session.execute(
        select(PlatformAdmin).where(func.lower(PlatformAdmin.email) == normalized_email)
    )
    pa = result.scalar_one_or_none()

    if pa is None or not verify_password(body.password, pa.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not pa.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(
        tenant_id=_PLATFORM_SENTINEL_TENANT_ID,
        subject=pa.email,
        user_id=pa.id,
        role="platform_admin",
    )
    refresh_token = create_refresh_token(
        tenant_id=_PLATFORM_SENTINEL_TENANT_ID,
        subject=pa.email,
    )

    logger.info("platform_admin_login", email=pa.email, admin_id=str(pa.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/admin/google", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def platform_admin_google_login(
    body: GoogleLoginRequest,
    session: AsyncSession = Depends(get_platform_admin_session),
) -> TokenResponse:
    """Sign in a platform admin with a Google ID token.

    Only succeeds if the Google account email matches a record in the
    platform_admins table. Tenant users cannot login through this endpoint.
    """
    claims = _verify_google_id_token(body.id_token)

    email = claims.get("email")
    if not isinstance(email, str) or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email is required",
        )

    if claims.get("email_verified") is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified",
        )

    normalized_email = email.strip().lower()
    result = await session.execute(
        select(PlatformAdmin).where(func.lower(PlatformAdmin.email) == normalized_email)
    )
    pa = result.scalar_one_or_none()

    if pa is None:
        logger.warning("platform_admin_google_login_no_account", attempted_email=normalized_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No platform admin account found for '{normalized_email}'.",
        )

    if not pa.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(
        tenant_id=_PLATFORM_SENTINEL_TENANT_ID,
        subject=pa.email,
        user_id=pa.id,
        role="platform_admin",
    )
    refresh_token = create_refresh_token(
        tenant_id=_PLATFORM_SENTINEL_TENANT_ID,
        subject=pa.email,
    )

    logger.info("platform_admin_google_login", email=pa.email, admin_id=str(pa.id))

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
