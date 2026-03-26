"""
Authentication endpoints: register, login, token refresh.
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.rate_limit import auth_rate_limit

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.api.dependencies import (
    TenantSession,
    get_auth_session,
    get_current_user,
    resolve_active_tenant_id,
)
from airex_core.core.config import settings
from airex_core.core.security import (
    AcceptInvitationWithGoogleRequest,
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
from airex_core.core.platform_admin_db import get_platform_admin_session
from airex_core.models.organization import Organization
from airex_core.models.organization_membership import OrganizationMembership
from airex_core.models.platform_admin import PlatformAdmin
from airex_core.models.project import Project
from airex_core.models.tenant import Tenant
from airex_core.models.tenant_membership import TenantMembership
from airex_core.models.user import User

_PLATFORM_SENTINEL_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

logger = structlog.get_logger()

router = APIRouter()


async def _get_org_id(session: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID | None:
    """Return the organization_id for a tenant, or None if not found."""
    result = await session.execute(
        select(Tenant.organization_id).where(Tenant.id == tenant_id)
    )
    return result.scalar_one_or_none()


def _row_value(row: object, attr: str) -> object:
    value = getattr(row, attr, None)
    if attr == "name" and not isinstance(value, str):
        mock_name = getattr(row, "_mock_name", None)
        if isinstance(mock_name, str) and mock_name:
            return mock_name
    return value


def _row_str(row: object, attr: str) -> str:
    value = _row_value(row, attr)
    return value if isinstance(value, str) else str(value)


def _row_optional_str(row: object, attr: str) -> str | None:
    value = _row_value(row, attr)
    return value if value is None or isinstance(value, str) else str(value)


class OrganizationSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str


class TenantSummary(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    organization_id: uuid.UUID
    organization_name: str | None = None
    organization_slug: str | None = None
    role: str | None = None


class ProjectSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class AuthMeResponse(BaseModel):
    user: UserResponse
    active_organization: OrganizationSummary | None = None
    active_tenant: TenantSummary | None = None
    organization_memberships: list[OrganizationSummary] = []
    tenant_memberships: list[TenantSummary] = []
    tenants: list[TenantSummary] = []
    projects: list[ProjectSummary] = []


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    dependencies=[Depends(auth_rate_limit)],
)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_auth_session),
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


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_auth_session),
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

    org_id = await _get_org_id(session, user.tenant_id)
    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
        org_id=org_id,
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


@router.get("/me", response_model=AuthMeResponse)
async def auth_me(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_auth_session),
    platform_admin_session: AsyncSession = Depends(get_platform_admin_session),
    x_active_tenant_id: str | None = Header(None, alias="X-Active-Tenant-Id"),
    x_tenant_id: str | None = Header(None, alias="X-Tenant-Id"),
) -> AuthMeResponse:
    """Return the authenticated user's active SaaS context and memberships."""
    if current_user is None or current_user.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Platform admin fast-path — no tenant context, no RLS session needed
    if (current_user.role or "").lower() == "platform_admin":
        pa_result = await platform_admin_session.execute(
            select(PlatformAdmin).where(PlatformAdmin.id == current_user.user_id)
        )
        pa = pa_result.scalar_one_or_none()
        if pa is None or not pa.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Platform admin not found or disabled",
            )
        return AuthMeResponse(
            user=UserResponse(
                id=pa.id,
                tenant_id=_PLATFORM_SENTINEL_TENANT_ID,
                email=pa.email,
                display_name=pa.display_name,
                role="platform_admin",
                is_active=pa.is_active,
                created_at=pa.created_at,
                updated_at=pa.updated_at,
            ),
        )

    active_tenant_id = await resolve_active_tenant_id(
        session=session,
        current_user=current_user,
        active_tenant_id=x_active_tenant_id or x_tenant_id,
    )

    user_result = await session.execute(select(User).where(User.id == current_user.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    active_tenant_result = await session.execute(
        select(
            Tenant.id,
            Tenant.name,
            Tenant.display_name,
            Tenant.organization_id,
            Organization.name.label("organization_name"),
            Organization.slug.label("organization_slug"),
        )
        .join(Organization, Organization.id == Tenant.organization_id)
        .where(Tenant.id == active_tenant_id)
    )
    active_tenant = active_tenant_result.one_or_none()
    if active_tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    org_membership_result = await session.execute(
        select(
            OrganizationMembership.organization_id,
            OrganizationMembership.role,
            Organization.name.label("organization_name"),
            Organization.slug.label("organization_slug"),
        )
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(OrganizationMembership.user_id == current_user.user_id)
    )
    organization_memberships = [
        OrganizationSummary(
            id=row.organization_id,
            name=row.organization_name,
            slug=row.organization_slug,
            role=row.role,
        )
        for row in org_membership_result.all()
    ]
    active_org_membership = next(
        (
            membership
            for membership in organization_memberships
            if membership.id == active_tenant.organization_id
        ),
        None,
    )

    tenant_membership_result = await session.execute(
        select(
            TenantMembership.tenant_id,
            TenantMembership.role,
            Tenant.name,
            Tenant.display_name,
            Tenant.organization_id,
            Organization.name.label("organization_name"),
            Organization.slug.label("organization_slug"),
        )
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .join(Organization, Organization.id == Tenant.organization_id)
        .where(TenantMembership.user_id == current_user.user_id)
    )
    tenant_memberships = [
        TenantSummary(
            id=row.tenant_id,
            name=_row_str(row, "name"),
            display_name=_row_str(row, "display_name"),
            organization_id=row.organization_id,
            organization_name=_row_optional_str(row, "organization_name"),
            organization_slug=_row_optional_str(row, "organization_slug"),
            role=_row_str(row, "role"),
        )
        for row in tenant_membership_result.all()
    ]
    active_tenant_membership = next(
        (
            membership
            for membership in tenant_memberships
            if membership.id == active_tenant.id
        ),
        None,
    )

    if active_org_membership is not None:
        accessible_tenant_query = (
            select(
                Tenant.id,
                Tenant.name,
                Tenant.display_name,
                Tenant.organization_id,
                Organization.name.label("organization_name"),
                Organization.slug.label("organization_slug"),
            )
            .join(Organization, Organization.id == Tenant.organization_id)
            .where(Tenant.organization_id == active_tenant.organization_id)
            .order_by(Tenant.display_name.asc())
        )
    else:
        accessible_tenant_query = (
            select(
                Tenant.id,
                Tenant.name,
                Tenant.display_name,
                Tenant.organization_id,
                Organization.name.label("organization_name"),
                Organization.slug.label("organization_slug"),
            )
            .join(Organization, Organization.id == Tenant.organization_id)
            .where(
                or_(
                    Tenant.id == current_user.tenant_id,
                    Tenant.id == active_tenant_id,
                    Tenant.id.in_(
                        select(TenantMembership.tenant_id).where(
                            TenantMembership.user_id == current_user.user_id
                        )
                    ),
                )
            )
            .order_by(Tenant.display_name.asc())
        )

    accessible_tenants_result = await session.execute(accessible_tenant_query)
    accessible_tenants = [
        TenantSummary(
            id=row.id,
            name=_row_str(row, "name"),
            display_name=_row_str(row, "display_name"),
            organization_id=row.organization_id,
            organization_name=_row_optional_str(row, "organization_name"),
            organization_slug=_row_optional_str(row, "organization_slug"),
        )
        for row in accessible_tenants_result.all()
    ]

    project_result = await session.execute(
        select(Project.id, Project.name, Project.slug)
        .where(Project.tenant_id == active_tenant_id, Project.is_active.is_(True))
        .order_by(Project.name.asc())
    )
    projects = [
        ProjectSummary(
            id=row.id,
            name=_row_str(row, "name"),
            slug=_row_str(row, "slug"),
        )
        for row in project_result.all()
    ]

    return AuthMeResponse(
        user=UserResponse(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            is_active=user.is_active,
            created_at=getattr(user, "created_at", None),
            updated_at=getattr(user, "updated_at", None),
        ),
        active_organization=OrganizationSummary(
            id=active_tenant.organization_id,
            name=active_tenant.organization_name,
            slug=active_tenant.organization_slug,
            role=active_org_membership.role if active_org_membership else "tenant_member",
        ),
        active_tenant=TenantSummary(
            id=active_tenant.id,
            name=_row_str(active_tenant, "name"),
            display_name=_row_str(active_tenant, "display_name"),
            organization_id=active_tenant.organization_id,
            organization_name=_row_optional_str(active_tenant, "organization_name"),
            organization_slug=_row_optional_str(active_tenant, "organization_slug"),
            role=active_tenant_membership.role if active_tenant_membership else user.role,
        ),
        organization_memberships=organization_memberships,
        tenant_memberships=tenant_memberships,
        tenants=accessible_tenants,
        projects=projects,
    )


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
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

    org_id = await _get_org_id(session, user.tenant_id)
    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
        org_id=org_id,
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


@router.post("/google", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
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

    org_id = await _get_org_id(session, user.tenant_id)
    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
        org_id=org_id,
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


@router.post("/accept-invitation-with-google", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def accept_invitation_with_google(
    body: AcceptInvitationWithGoogleRequest,
    session: TenantSession,
) -> TokenResponse:
    """Accept invitation using Google authentication instead of setting a password.
    
    This allows users to complete their invitation by signing in with Google,
    eliminating the need to set a password. The Google email must match the
    invited user's email.
    """
    # Verify Google ID token
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

    # Verify email matches
    if user.email.lower() != normalized_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Google email '{email}' does not match invited email '{user.email}'",
        )

    # Check if token expired
    if user.invitation_expires_at and user.invitation_expires_at < datetime.now(
        timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation token has expired",
        )

    # Check if account already activated
    if user.hashed_password and not user.invitation_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account already activated. Please use regular login.",
        )

    # Clear invitation token and activate account
    # Note: We don't set a password - user will use Google auth going forward
    user.invitation_token = None
    user.invitation_expires_at = None
    user.is_active = True
    await session.flush()

    logger.info(
        "invitation_accepted_with_google",
        email=user.email,
        user_id=str(user.id),
    )

    # Return tokens so user is logged in
    org_id = await _get_org_id(session, user.tenant_id)
    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
        org_id=org_id,
    )
    refresh_token = create_refresh_token(
        tenant_id=user.tenant_id,
        subject=user.email,
    )

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


@router.post("/set-password", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
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
    org_id = await _get_org_id(session, user.tenant_id)
    access_token = create_access_token(
        tenant_id=user.tenant_id,
        subject=user.email,
        user_id=user.id,
        role=user.role,
        org_id=org_id,
    )
    refresh_token = create_refresh_token(
        tenant_id=user.tenant_id,
        subject=user.email,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/reset-password", dependencies=[Depends(auth_rate_limit)])
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
