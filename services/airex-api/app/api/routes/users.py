"""
Admin user management endpoints.

Requires ADMIN role for all operations.
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    TenantId,
    TenantSession,
    authorize_tenant_admin,
    get_auth_session,
    get_authenticated_user,
)
from airex_core.core.rbac import normalize_role_name
from airex_core.core.security import (
    TokenData,
    UserResponse,
    hash_password,
)
from airex_core.models.enums import UserRole
from airex_core.models.organization_membership import OrganizationMembership
from airex_core.models.tenant import Tenant
from airex_core.models.tenant_membership import TenantMembership
from airex_core.models.user import User

logger = structlog.get_logger()

router = APIRouter()


def _is_admin_like_role(role: str | None) -> bool:
    return normalize_role_name(role or "") in {"admin", "platform_admin"}


async def _require_tenant_admin_scope(
    auth_session: AsyncSession,
    current_user: TokenData,
    tenant_id: uuid.UUID,
) -> None:
    if not await authorize_tenant_admin(auth_session, current_user, tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin required",
        )


async def _get_requester_admin_org_ids(
    session: AsyncSession,
    current_user: TokenData,
) -> set[uuid.UUID]:
    admin_org_ids: set[uuid.UUID] = set()

    if normalize_role_name(current_user.role) == "admin":
        home_org_result = await session.execute(
            select(Tenant.organization_id).where(Tenant.id == current_user.tenant_id)
        )
        home_org_id = home_org_result.scalar_one_or_none()
        if home_org_id is not None:
            admin_org_ids.add(home_org_id)

    membership_result = await session.execute(
        select(
            OrganizationMembership.organization_id,
            OrganizationMembership.role,
        ).where(OrganizationMembership.user_id == current_user.user_id)
    )
    for row in membership_result.all():
        if _is_admin_like_role(getattr(row, "role", None)):
            admin_org_ids.add(row.organization_id)

    return admin_org_ids


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str | None = None  # Optional for invitation flow
    display_name: str
    role: str = "operator"
    is_active: bool = True


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


@router.get("/", response_model=UserListResponse)
async def list_users(
    tenant_id: TenantId,
    session: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    include_inactive: bool = Query(default=False, description="Include inactive (deleted) users"),
) -> UserListResponse:
    """List all users in the tenant (admin only).

    By default, only active users are returned. Set include_inactive=true to see deleted users.
    """
    await _require_tenant_admin_scope(auth_session, current_user, tenant_id)

    # Build base query conditions
    query_filter = User.tenant_id == tenant_id
    if not include_inactive:
        query_filter = query_filter & User.is_active
    
    # Count total (matching filters)
    count_q = select(func.count(User.id)).where(query_filter)
    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    # Fetch users
    query = (
        select(User)
        .where(query_filter)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(query)
    users = list(result.scalars().all())

    items = []
    for u in users:
        # Determine invitation status
        invitation_status = None
        if u.invitation_token:
            if u.invitation_expires_at and u.invitation_expires_at < datetime.now(
                timezone.utc
            ):
                invitation_status = "expired"
            else:
                invitation_status = "pending"
        elif u.hashed_password:
            invitation_status = "accepted"

        items.append(
            UserResponse(
                id=u.id,
                tenant_id=u.tenant_id,
                email=u.email,
                display_name=u.display_name,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
                updated_at=u.updated_at,
                invitation_token=u.invitation_token,
                invitation_expires_at=u.invitation_expires_at,
                invitation_status=invitation_status,
            )
        )

    return UserListResponse(items=items, total=total)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> UserResponse:
    """Get user details (admin only)."""
    await _require_tenant_admin_scope(auth_session, current_user, tenant_id)

    result = await session.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.id == user_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Determine invitation status
    invitation_status = None
    if user.invitation_token:
        if user.invitation_expires_at and user.invitation_expires_at < datetime.now(
            timezone.utc
        ):
            invitation_status = "expired"
        else:
            invitation_status = "pending"
    elif user.hashed_password:
        invitation_status = "accepted"

    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        invitation_token=user.invitation_token,
        invitation_expires_at=user.invitation_expires_at,
        invitation_status=invitation_status,
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(
    body: UserCreateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> UserResponse:
    """Create a new user (admin only)."""
    await _require_tenant_admin_scope(auth_session, current_user, tenant_id)

    # Validate role
    try:
        UserRole(body.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {body.role}. Must be one of: {', '.join(r.value for r in UserRole)}",
        )

    normalized_email = body.email.strip().lower()

    # Check if email already exists (case-insensitive)
    result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    existing = result.scalar_one_or_none()
    
    # Initialize invitation variables for both paths
    from airex_core.core.security import generate_invitation_token
    
    invitation_token = None
    invitation_expires_at = None
    hashed_password_value = None
    
    # If user exists and is active, return conflict
    if existing and existing.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # If user exists but is inactive, reactivate and update them
    if existing and not existing.is_active:
        # Verify tenant matches
        if existing.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered in a different tenant",
            )
        
        # Reactivate and update the existing user
        user = existing
        user.display_name = body.display_name
        user.role = body.role.lower()
        user.is_active = body.is_active
        
        # Generate invitation token if password not provided
        if body.password:
            # Direct creation with password (backward compatibility)
            hashed_password_value = hash_password(body.password)
            user.hashed_password = hashed_password_value
            # Clear any existing invitation tokens
            user.invitation_token = None
            user.invitation_expires_at = None
        else:
            # Invitation flow: generate new token
            invitation_token = generate_invitation_token()
            invitation_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            user.invitation_token = invitation_token
            user.invitation_expires_at = invitation_expires_at
            # Clear password if user was previously activated
            if user.hashed_password:
                user.hashed_password = None
        
        await session.flush()
        
        logger.info(
            "user_reactivated_by_admin",
            email=body.email,
            user_id=str(user.id),
            role=body.role,
            has_invitation=invitation_token is not None,
        )
    else:
        # Create new user
        # Generate invitation token if password not provided
        if body.password:
            # Direct creation with password (backward compatibility)
            hashed_password_value = hash_password(body.password)
        else:
            # Invitation flow: generate token
            invitation_token = generate_invitation_token()
            invitation_expires_at = datetime.now(timezone.utc) + timedelta(
                days=7
            )  # 7 day expiry
        
        user = User(
            tenant_id=tenant_id,
            email=normalized_email,
            hashed_password=hashed_password_value,
            display_name=body.display_name,
            role=body.role.lower(),
            is_active=body.is_active,
            invitation_token=invitation_token,
            invitation_expires_at=invitation_expires_at,
        )
        session.add(user)
        await session.flush()
        
        logger.info(
            "user_created_by_admin",
            email=body.email,
            user_id=str(user.id),
            role=body.role,
            has_invitation=invitation_token is not None,
        )

    # Send invitation email if using invitation flow
    if invitation_token:
        try:
            from airex_core.services.notification_service import (
                send_user_invitation_email,
            )
            from airex_core.core.config import settings

            invitation_url = f"{settings.FRONTEND_URL or 'http://localhost:5173'}/set-password?token={invitation_token}"
            await send_user_invitation_email(
                email=body.email,
                display_name=body.display_name,
                invitation_url=invitation_url,
            )
            logger.info(
                "user_invitation_email_sent", email=body.email, user_id=str(user.id)
            )
        except Exception as exc:
            logger.warning(
                "user_invitation_email_failed", email=body.email, error=str(exc)
            )

    # Determine invitation status
    invitation_status = None
    if invitation_token:
        invitation_status = "pending"
    elif user.hashed_password:
        invitation_status = "accepted"

    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        invitation_token=invitation_token,
        invitation_expires_at=invitation_expires_at,
        invitation_status=invitation_status,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> UserResponse:
    """Update user (admin only). Cannot change own role or deactivate self."""
    await _require_tenant_admin_scope(auth_session, current_user, tenant_id)

    result = await session.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.id == user_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent self-modification of role/active status
    if current_user and current_user.user_id == user_id:
        if body.role is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change your own role",
            )
        if body.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot deactivate your own account",
            )

    # Update fields
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role is not None:
        # Validate role
        try:
            UserRole(body.role.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {body.role}",
            )
        user.role = body.role.lower()
    if body.is_active is not None:
        user.is_active = body.is_active

    # updated_at is automatically updated by database trigger
    await session.flush()

    logger.info(
        "user_updated_by_admin",
        user_id=str(user_id),
        updated_fields=list(body.model_dump(exclude_unset=True).keys()),
    )

    # Determine invitation status
    invitation_status = None
    if user.invitation_token:
        if user.invitation_expires_at and user.invitation_expires_at < datetime.now(
            timezone.utc
        ):
            invitation_status = "expired"
        else:
            invitation_status = "pending"
    elif user.hashed_password:
        invitation_status = "accepted"

    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        invitation_token=user.invitation_token,
        invitation_expires_at=user.invitation_expires_at,
        invitation_status=invitation_status,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> None:
    """Delete (deactivate) a user (admin only). Cannot delete self."""
    await _require_tenant_admin_scope(auth_session, current_user, tenant_id)

    result = await session.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.id == user_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent self-deletion
    if current_user and current_user.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete your own account",
        )

    # Soft delete: deactivate instead of hard delete
    user.is_active = False
    await session.flush()

    logger.info("user_deactivated_by_admin", user_id=str(user_id))


@router.post("/{user_id}/resend-invitation", status_code=status.HTTP_200_OK)
async def resend_invitation(
    user_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: TokenData = Depends(get_authenticated_user),
    auth_session: AsyncSession = Depends(get_auth_session),
) -> dict:
    """Resend invitation email to a user (admin only)."""
    await _require_tenant_admin_scope(auth_session, current_user, tenant_id)

    from airex_core.core.security import generate_invitation_token
    from airex_core.services.notification_service import send_user_invitation_email
    from airex_core.core.config import settings

    result = await session.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.id == user_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Generate new invitation token
    invitation_token = generate_invitation_token()
    user.invitation_token = invitation_token
    user.invitation_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await session.flush()

    # Send invitation email
    invitation_url = f"{settings.FRONTEND_URL or 'http://localhost:5173'}/set-password?token={invitation_token}"
    try:
        await send_user_invitation_email(
            email=user.email,
            display_name=user.display_name,
            invitation_url=invitation_url,
        )
        logger.info("invitation_resent", email=user.email, user_id=str(user_id))
        return {"message": "Invitation email sent successfully"}
    except Exception as exc:
        logger.warning("invitation_resend_failed", email=user.email, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invitation email",
        )


class AccessibleTenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    cloud: str
    is_active: bool
    organization_id: uuid.UUID | None
    membership_role: str | None  # None if access is via org membership or home tenant


@router.get(
    "/{user_id}/accessible-tenants",
    response_model=list[AccessibleTenantResponse],
)
async def list_accessible_tenants(
    user_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[AccessibleTenantResponse]:
    """List all tenants accessible to a user (admin only).

    Returns tenants the user can access via: home tenant, org membership, or
    explicit tenant membership.
    """
    is_platform_admin = normalize_role_name(current_user.role) == "platform_admin"
    visible_org_ids: set[uuid.UUID] | None = None
    if not is_platform_admin:
        visible_org_ids = await _get_requester_admin_org_ids(session, current_user)
        if not visible_org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin or platform admin required",
            )

    results: dict[uuid.UUID, AccessibleTenantResponse] = {}

    # 1. Home tenant (from the user's own tenant_id on the User record)
    user_result = await session.execute(
        select(User.id, User.tenant_id).where(User.id == user_id)
    )
    user_row = user_result.one_or_none()
    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    home_tenant_id = user_row.tenant_id
    if home_tenant_id is not None:
        tenant_result = await session.execute(
            select(Tenant).where(Tenant.id == home_tenant_id)
        )
        home_tenant = tenant_result.scalar_one_or_none()
        if home_tenant is not None and (
            is_platform_admin or home_tenant.organization_id in visible_org_ids
        ):
            results[home_tenant.id] = AccessibleTenantResponse(
                id=home_tenant.id,
                name=home_tenant.name,
                display_name=home_tenant.display_name,
                cloud=home_tenant.cloud,
                is_active=home_tenant.is_active,
                organization_id=home_tenant.organization_id,
                membership_role=None,
            )

    # 2. Tenants accessible via organization membership
    org_memberships = await session.execute(
        select(OrganizationMembership.organization_id).where(
            OrganizationMembership.user_id == user_id
        )
    )
    org_ids = list(org_memberships.scalars().all())
    if org_ids:
        org_tenants_result = await session.execute(
            select(Tenant).where(Tenant.organization_id.in_(org_ids))
        )
        for tenant in org_tenants_result.scalars().all():
            if not is_platform_admin and tenant.organization_id not in visible_org_ids:
                continue
            if tenant.id not in results:
                results[tenant.id] = AccessibleTenantResponse(
                    id=tenant.id,
                    name=tenant.name,
                    display_name=tenant.display_name,
                    cloud=tenant.cloud,
                    is_active=tenant.is_active,
                    organization_id=tenant.organization_id,
                    membership_role=None,
                )

    # 3. Explicit tenant memberships
    tenant_memberships_result = await session.execute(
        select(TenantMembership.tenant_id, TenantMembership.role).where(
            TenantMembership.user_id == user_id
        )
    )
    explicit_memberships = tenant_memberships_result.all()
    if explicit_memberships:
        explicit_tenant_ids = [row.tenant_id for row in explicit_memberships]
        explicit_tenants_result = await session.execute(
            select(Tenant).where(Tenant.id.in_(explicit_tenant_ids))
        )
        tenant_map = {t.id: t for t in explicit_tenants_result.scalars().all()}
        for row in explicit_memberships:
            if row.tenant_id not in tenant_map:
                continue
            tenant = tenant_map[row.tenant_id]
            if not is_platform_admin and tenant.organization_id not in visible_org_ids:
                continue
            if row.tenant_id not in results:
                tenant = tenant_map[row.tenant_id]
                results[row.tenant_id] = AccessibleTenantResponse(
                    id=tenant.id,
                    name=tenant.name,
                    display_name=tenant.display_name,
                    cloud=tenant.cloud,
                    is_active=tenant.is_active,
                    organization_id=tenant.organization_id,
                    membership_role=row.role,
                )

    if not is_platform_admin and not results:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user's tenant access",
        )

    return sorted(results.values(), key=lambda t: t.display_name)
