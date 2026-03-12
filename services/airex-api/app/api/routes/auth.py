"""
Authentication endpoints: register, login, token refresh.
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.api.dependencies import TenantSession
from airex_core.core.config import settings
from airex_core.core.security import (
    GoogleLoginRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from airex_core.models.user import User

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
)
async def register(
    body: RegisterRequest,
    session: TenantSession,
) -> UserResponse:
    """Register a new user account."""
    normalized_email = body.email.strip().lower()

    # Check if email already exists (case-insensitive)
    result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    tenant_id = body.tenant_id or uuid.UUID(settings.DEV_TENANT_ID)

    user = User(
        tenant_id=tenant_id,
        email=normalized_email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
        role="operator",
    )
    session.add(user)
    await session.flush()

    logger.info("user_registered", email=body.email, user_id=str(user.id))

    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    session: TenantSession,
) -> TokenResponse:
    """Authenticate and return access + refresh tokens."""
    normalized_email = body.email.strip().lower()
    result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
    )
    refresh_token = create_refresh_token(
        tenant_id=user.tenant_id,
        subject=user.email,
    )

    logger.info("user_login", email=user.email, user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: TenantSession,
) -> TokenResponse:
    """Exchange a refresh token for a new access token."""
    try:
        data = decode_refresh_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    # Verify user still exists and is active
    normalized_email = data.sub.strip().lower()
    result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=body.refresh_token,
    )


# ── Google Sign-In ─────────────────────────────────────────


def _verify_google_id_token(token: str) -> dict[str, object]:
    """Verify a Google ID token and return its claims.

    Raises HTTPException 503 if Google sign-in is not configured.
    Raises HTTPException 401 if the token is invalid.
    """
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


@router.post("/google", response_model=TokenResponse)
async def google_login(
    body: GoogleLoginRequest,
    session: TenantSession,
) -> TokenResponse:
    """Sign in with a Google ID token.

    Only works for users already created by an admin.
    Google sign-in does NOT auto-register new accounts.
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
        select(User).where(func.lower(User.email) == normalized_email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("google_login_no_account", attempted_email=normalized_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No account found for '{normalized_email}'. Contact your administrator.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
    )
    refresh_token = create_refresh_token(
        tenant_id=user.tenant_id,
        subject=user.email,
    )

    logger.info("user_google_login", email=user.email, user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ── Password Setup & Reset ──────────────────────────────────────


class SetPasswordRequest(BaseModel):
    invitation_token: str
    password: str


class ResetPasswordRequest(BaseModel):
    email: str


@router.post("/set-password", response_model=TokenResponse)
async def set_password(
    body: SetPasswordRequest,
    session: TenantSession,
) -> TokenResponse:
    """Set password using invitation token."""
    from airex_core.core.security import hash_password

    # Find user by invitation token
    result = await session.execute(
        select(User).where(User.invitation_token == body.invitation_token)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invitation token",
        )

    # Check if token expired
    if user.invitation_expires_at and user.invitation_expires_at < datetime.now(
        timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token has expired",
        )

    # Check if password already set
    if user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password already set. Use reset-password if you forgot it.",
        )

    # Set password and clear invitation
    user.hashed_password = hash_password(body.password)
    user.invitation_token = None
    user.invitation_expires_at = None
    user.is_active = True  # Activate account
    await session.flush()

    logger.info("password_set_via_invitation", email=user.email, user_id=str(user.id))

    # Return tokens so user is logged in
    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
    )
    refresh_token = create_refresh_token(
        tenant_id=user.tenant_id,
        subject=user.email,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    session: TenantSession,
) -> dict:
    """Request password reset (sends email with reset token)."""
    from airex_core.core.security import generate_invitation_token
    from airex_core.services.notification_service import send_password_reset_email
    from airex_core.core.config import settings

    # Find user by email
    normalized_email = body.email.strip().lower()
    result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Don't reveal if email exists (security best practice)
        logger.warning("password_reset_requested_unknown_email", email=body.email)
        return {"message": "If the email exists, a reset link has been sent"}

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Generate reset token (reuse invitation_token field for reset)
    reset_token = generate_invitation_token()
    user.invitation_token = reset_token
    user.invitation_expires_at = datetime.now(timezone.utc) + timedelta(
        hours=24
    )  # 24 hour expiry
    await session.flush()

    # Send reset email
    reset_url = f"{settings.FRONTEND_URL or 'http://localhost:5173'}/set-password?token={reset_token}"
    await send_password_reset_email(
        email=user.email,
        display_name=user.display_name,
        reset_url=reset_url,
    )

    logger.info("password_reset_email_sent", email=user.email, user_id=str(user.id))

    return {"message": "If the email exists, a reset link has been sent"}
