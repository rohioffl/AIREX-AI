"""Tenant member management API (UUID-based paths)."""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    authorize_tenant_admin,
    get_authenticated_user,
    get_auth_session,
)
from airex_core.core.config import settings
from airex_core.core.security import TokenData, generate_invitation_token
from airex_core.services.notification_service import send_user_invitation_email
from airex_core.models.tenant import Tenant
from airex_core.models.tenant_membership import TenantMembership
from airex_core.models.user import User

logger = structlog.get_logger()

router = APIRouter()


class TenantMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    created_at: datetime
    email: str | None = None
    display_name: str | None = None
    is_active: bool | None = None


class TenantMemberAddRequest(BaseModel):
    user_id: uuid.UUID
    role: str = Field(..., pattern=r"^(viewer|operator|admin)$")


class TenantMemberUpdateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(viewer|operator|admin)$")


class InviteTenantUserRequest(BaseModel):
    email: EmailStr
    role: str = Field(..., pattern=r"^(viewer|operator|admin)$")
    display_name: str = Field(default="", max_length=200)


class InviteTenantUserResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    invitation_url: str
    expires_at: datetime


@router.get("/tenants/{tenant_id}/members", response_model=list[TenantMemberResponse])
async def list_tenant_members(
    tenant_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[TenantMemberResponse]:
    """List members of a tenant. Requires tenant admin."""
    if not await authorize_tenant_admin(session, current_user, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin required")

    result = await session.execute(
        select(TenantMembership, User.email, User.display_name, User.is_active)
        .outerjoin(User, User.id == TenantMembership.user_id)
        .where(TenantMembership.tenant_id == tenant_id)
        .order_by(TenantMembership.created_at.asc())
    )
    return [
        TenantMemberResponse(
            id=m.id,
            user_id=m.user_id,
            tenant_id=m.tenant_id,
            role=m.role,
            created_at=m.created_at,
            email=email,
            display_name=display_name,
            is_active=is_active,
        )
        for m, email, display_name, is_active in result.all()
    ]


@router.post(
    "/tenants/{tenant_id}/members",
    response_model=TenantMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_tenant_member(
    tenant_id: uuid.UUID,
    body: TenantMemberAddRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> TenantMemberResponse:
    """Add a user as a member of the tenant. Requires tenant admin."""
    if not await authorize_tenant_admin(session, current_user, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin required")

    tenant_result = await session.execute(select(Tenant.id).where(Tenant.id == tenant_id))
    if tenant_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    existing = await session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == body.user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    membership = TenantMembership(tenant_id=tenant_id, user_id=body.user_id, role=body.role)
    session.add(membership)
    await session.flush()
    return TenantMemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.patch(
    "/tenants/{tenant_id}/members/{user_id}",
    response_model=TenantMemberResponse,
)
async def update_tenant_member(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    body: TenantMemberUpdateRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> TenantMemberResponse:
    """Update the role of a tenant member. Requires tenant admin."""
    if not await authorize_tenant_admin(session, current_user, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin required")

    result = await session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    membership.role = body.role
    session.add(membership)
    await session.flush()
    return TenantMemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.delete(
    "/tenants/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_tenant_member(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> None:
    """Remove a user from the tenant. Requires tenant admin."""
    if not await authorize_tenant_admin(session, current_user, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin required")

    result = await session.execute(
        delete(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")


@router.post(
    "/tenants/{tenant_id}/invite-user",
    response_model=InviteTenantUserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_tenant_user(
    tenant_id: uuid.UUID,
    body: InviteTenantUserRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> InviteTenantUserResponse:
    """Invite a new user to a specific tenant.

    Creates a pending user account and tenant membership.
    Returns an invitation URL the org admin can share with the invitee.
    The invitee follows the link to set their password and activate the account.
    No org membership is created — the user can only access this tenant.
    """
    if not await authorize_tenant_admin(session, current_user, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin required")

    tenant_result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    normalized_email = body.email.strip().lower()

    # Check if email already exists
    existing_user_result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    existing_user = existing_user_result.scalar_one_or_none()
    if existing_user is not None:
        if existing_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists. Use 'Add Tenant Member' to grant access.",
            )
        # Re-invite inactive user: refresh token and membership
        token = generate_invitation_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        existing_user.invitation_token = token
        existing_user.invitation_expires_at = expires_at
        existing_user.is_active = False
        session.add(existing_user)

        # Upsert tenant membership
        membership_result = await session.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == existing_user.id,
            )
        )
        membership = membership_result.scalar_one_or_none()
        if membership is None:
            membership = TenantMembership(tenant_id=tenant_id, user_id=existing_user.id, role=body.role)
            session.add(membership)
        else:
            membership.role = body.role

        await session.flush()
        invitation_url = f"{settings.FRONTEND_URL}/set-password?token={token}"
        logger.info("tenant_user_reinvited", email=normalized_email, tenant_id=str(tenant_id), actor=str(current_user.user_id))
        await send_user_invitation_email(
            email=existing_user.email,
            display_name=existing_user.display_name or existing_user.email,
            invitation_url=invitation_url,
        )
        return InviteTenantUserResponse(
            user_id=existing_user.id,
            email=existing_user.email,
            role=body.role,
            invitation_url=invitation_url,
            expires_at=expires_at,
        )

    # Create new pending user with home tenant = this tenant (no password, no org membership)
    token = generate_invitation_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    display_name = body.display_name.strip() or normalized_email.split("@")[0]
    user = User(
        tenant_id=tenant_id,
        email=normalized_email,
        hashed_password=None,
        display_name=display_name,
        role=body.role,
        is_active=False,
        invitation_token=token,
        invitation_expires_at=expires_at,
    )
    session.add(user)
    await session.flush()

    membership = TenantMembership(tenant_id=tenant_id, user_id=user.id, role=body.role)
    session.add(membership)
    await session.flush()

    invitation_url = f"{settings.FRONTEND_URL}/set-password?token={token}"
    logger.info(
        "tenant_user_invited",
        email=normalized_email,
        user_id=str(user.id),
        tenant_id=str(tenant_id),
        role=body.role,
        actor=str(current_user.user_id),
    )
    await send_user_invitation_email(
        email=user.email,
        display_name=display_name,
        invitation_url=invitation_url,
    )
    return InviteTenantUserResponse(
        user_id=user.id,
        email=user.email,
        role=body.role,
        invitation_url=invitation_url,
        expires_at=expires_at,
    )
