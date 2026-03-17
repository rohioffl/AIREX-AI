"""Tenant member management API (UUID-based paths)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    authorize_tenant_admin,
    get_authenticated_user,
    get_auth_session,
)
from airex_core.core.security import TokenData
from airex_core.models.tenant import Tenant
from airex_core.models.tenant_membership import TenantMembership

router = APIRouter()


class TenantMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str
    created_at: datetime


class TenantMemberAddRequest(BaseModel):
    user_id: uuid.UUID
    role: str = Field(..., pattern=r"^(viewer|operator|admin)$")


class TenantMemberUpdateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(viewer|operator|admin)$")


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
        select(TenantMembership)
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
        )
        for m in result.scalars().all()
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
