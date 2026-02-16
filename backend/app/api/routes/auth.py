"""
Authentication endpoints: register, login, token refresh.
"""

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import TenantSession
from app.core.config import settings
from app.core.security import (
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
from app.models.user import User

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
    # Check if email already exists
    result = await session.execute(
        select(User).where(User.email == body.email)
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
        email=body.email,
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
    result = await session.execute(
        select(User).where(User.email == body.email)
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
    result = await session.execute(
        select(User).where(User.email == data.sub)
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
