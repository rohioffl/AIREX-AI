"""Organization and organization-scoped tenant APIs."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    RequirePlatformAdmin,
    authorize_org_access,
    authorize_org_admin,
    get_authenticated_user,
    get_auth_session,
    get_home_organization_id,
    has_org_membership,
)
from airex_core.core.rbac import normalize_role_name
from airex_core.core.config import settings
from airex_core.core.security import TokenData, generate_invitation_token
from airex_core.models.organization import Organization
from airex_core.models.organization_membership import OrganizationMembership
from airex_core.models.tenant import Tenant
from airex_core.models.tenant_membership import TenantMembership
from airex_core.models.user import User
from airex_core.services.audit_service import record_event
from airex_core.services.notification_service import send_user_invitation_email

router = APIRouter()


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    tenant_count: int = 0


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    slug: str | None = Field(None, min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    status: str | None = Field(None, pattern=r"^(active|disabled|suspended)$")


class OrganizationTenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    cloud: str
    is_active: bool
    organization_id: uuid.UUID


class OrganizationTenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(..., min_length=2, max_length=255)
    cloud: str = Field(..., pattern=r"^(aws|gcp)$")
    escalation_email: str = ""
    slack_channel: str = ""
    ssh_user: str = "ubuntu"
    aws_config: dict = {}
    gcp_config: dict = {}
    servers: list = []


def _organization_listing_query():
    return (
        select(
            Organization.id,
            Organization.name,
            Organization.slug,
            Organization.status,
            func.count(Tenant.id).label("tenant_count"),
        )
        .outerjoin(Tenant, Tenant.organization_id == Organization.id)
        .group_by(
            Organization.id,
            Organization.name,
            Organization.slug,
            Organization.status,
        )
        .order_by(Organization.name.asc())
    )


def _organization_response_from_row(row: Any) -> OrganizationResponse:
    return OrganizationResponse(
        id=row.id,
        name=row.name,
        slug=row.slug,
        status=row.status,
        tenant_count=int(getattr(row, "tenant_count", 0) or 0),
    )


@router.get("/organizations", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[OrganizationResponse]:
    """List organizations visible to the current user."""
    if current_user.role.lower() == "platform_admin":
        result = await session.execute(_organization_listing_query())
        return [_organization_response_from_row(row) for row in result.all()]

    org_ids: set[uuid.UUID] = set()
    home_org_id = await get_home_organization_id(session, current_user)
    if home_org_id is not None:
        org_ids.add(home_org_id)

    membership_result = await session.execute(
        select(OrganizationMembership.organization_id).where(
            OrganizationMembership.user_id == current_user.user_id
        )
    )
    org_ids.update(membership_result.scalars().all())

    if not org_ids:
        return []

    result = await session.execute(
        _organization_listing_query().where(Organization.id.in_(list(org_ids)))
    )
    return [_organization_response_from_row(row) for row in result.all()]


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreateRequest,
    _: RequirePlatformAdmin,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> OrganizationResponse:
    """Create a new organization. Requires platform_admin role."""
    existing = await session.execute(
        select(Organization).where(Organization.slug == body.slug.lower().strip())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization slug already exists")

    org = Organization(name=body.name.strip(), slug=body.slug.lower().strip(), status="active")
    session.add(org)
    await session.flush()
    return OrganizationResponse(id=org.id, name=org.name, slug=org.slug, status=org.status)


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> OrganizationResponse:
    """Get a single organization if visible to the current user."""
    org_result = await session.execute(select(Organization).where(Organization.id == organization_id))
    organization = org_result.scalar_one_or_none()
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if not await authorize_org_access(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for organization")
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        status=organization.status,
        tenant_count=getattr(organization, "tenant_count", 0),
    )


@router.put("/organizations/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: uuid.UUID,
    body: OrganizationUpdateRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> OrganizationResponse:
    """Update an organization."""
    if not await authorize_org_admin(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")

    org_result = await session.execute(select(Organization).where(Organization.id == organization_id))
    organization = org_result.scalar_one_or_none()
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.slug and body.slug.lower().strip() != organization.slug:
        existing = await session.execute(
            select(Organization.id).where(Organization.slug == body.slug.lower().strip())
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization slug already exists")

    if body.name is not None:
        organization.name = body.name.strip()
    if body.slug is not None:
        organization.slug = body.slug.lower().strip()
    if body.status is not None:
        organization.status = body.status
    session.add(organization)
    await session.flush()

    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        status=organization.status,
        tenant_count=getattr(organization, "tenant_count", 0),
    )


@router.get("/organizations/{organization_id}/tenants", response_model=list[OrganizationTenantResponse])
async def list_organization_tenants(
    organization_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[OrganizationTenantResponse]:
    """List tenants in the organization visible to the user."""
    if not await authorize_org_access(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for organization")

    can_view_all = (
        current_user.role.lower() == "platform_admin"
        or await authorize_org_admin(session, current_user, organization_id)
        or await has_org_membership(
            session,
            user_id=current_user.user_id,
            organization_id=organization_id,
        )
    )

    if can_view_all:
        query = (
            select(Tenant)
            .where(Tenant.organization_id == organization_id)
            .order_by(Tenant.display_name.asc())
        )
        result = await session.execute(query)
        tenants = result.scalars().all()
    else:
        membership_result = await session.execute(
            select(TenantMembership.tenant_id)
            .join(Tenant, Tenant.id == TenantMembership.tenant_id)
            .where(
                Tenant.organization_id == organization_id,
                TenantMembership.user_id == current_user.user_id,
            )
        )
        accessible_tenant_ids = {current_user.tenant_id, *membership_result.scalars().all()}
        result = await session.execute(
            select(Tenant)
            .where(
                Tenant.organization_id == organization_id,
                Tenant.id.in_(list(accessible_tenant_ids)),
            )
            .order_by(Tenant.display_name.asc())
        )
        tenants = result.scalars().all()

    return [
        OrganizationTenantResponse(
            id=tenant.id,
            name=tenant.name,
            display_name=tenant.display_name,
            cloud=tenant.cloud,
            is_active=tenant.is_active,
            organization_id=tenant.organization_id,
        )
        for tenant in tenants
    ]


@router.post(
    "/organizations/{organization_id}/tenants",
    response_model=OrganizationTenantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_tenant(
    organization_id: uuid.UUID,
    body: OrganizationTenantCreateRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> OrganizationTenantResponse:
    """Create a tenant under an organization."""
    if not await authorize_org_admin(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")

    org_result = await session.execute(select(Organization.id).where(Organization.id == organization_id))
    if org_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    existing = await session.execute(select(Tenant.id).where(Tenant.name == body.name.lower().strip()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant name already exists")

    tenant = Tenant(
        organization_id=organization_id,
        name=body.name.lower().strip(),
        display_name=body.display_name.strip(),
        cloud=body.cloud,
        escalation_email=body.escalation_email,
        slack_channel=body.slack_channel,
        ssh_user=body.ssh_user,
        aws_config=body.aws_config,
        gcp_config=body.gcp_config,
        servers=body.servers,
        is_active=True,
    )
    session.add(tenant)
    await session.flush()

    return OrganizationTenantResponse(
        id=tenant.id,
        name=tenant.name,
        display_name=tenant.display_name,
        cloud=tenant.cloud,
        is_active=tenant.is_active,
        organization_id=tenant.organization_id,
    )


# ─── Org Member Management ────────────────────────────────────────────────────

_MEMBER_ROLES = {"viewer", "operator", "admin"}


class OrgMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    email: str | None = None
    display_name: str | None = None
    is_active: bool | None = None
    invitation_status: str | None = None
    created_at: datetime


class OrgMemberAddRequest(BaseModel):
    user_id: uuid.UUID
    role: str = Field(..., pattern=r"^(viewer|operator|admin)$")


class InviteOrgMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(..., pattern=r"^(viewer|operator|admin)$")
    home_tenant_id: uuid.UUID | None = None
    display_name: str = Field(default="", max_length=200)


class InviteOrgMemberResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str
    organization_id: uuid.UUID
    home_tenant_id: uuid.UUID | None = None
    invitation_url: str | None = None
    expires_at: datetime | None = None
    status: str = "invited"


class OrgMemberUpdateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(viewer|operator|admin)$")


def _invitation_status_for_user(user: User | None) -> str | None:
    if user is None:
        return None
    if user.invitation_token:
        if user.invitation_expires_at and user.invitation_expires_at < datetime.now(timezone.utc):
            return "expired"
        return "pending"
    if user.hashed_password:
        return "accepted"
    return None


@router.get("/organizations/{organization_id}/members", response_model=list[OrgMemberResponse])
async def list_org_members(
    organization_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[OrgMemberResponse]:
    """List members of an organization."""
    if not await authorize_org_admin(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")

    result = await session.execute(
        select(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.created_at.asc())
    )
    rows = result.all()
    return [
        OrgMemberResponse(
            id=membership.id,
            user_id=membership.user_id,
            organization_id=membership.organization_id,
            role=membership.role,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            invitation_status=_invitation_status_for_user(user),
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]


@router.post(
    "/organizations/{organization_id}/members",
    response_model=OrgMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_org_member(
    organization_id: uuid.UUID,
    body: OrgMemberAddRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> OrgMemberResponse:
    """Add a user as a member of the organization."""
    if not await authorize_org_admin(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")

    org_result = await session.execute(select(Organization.id).where(Organization.id == organization_id))
    if org_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    user_result = await session.execute(select(User).where(User.id == body.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == body.user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    membership = OrganizationMembership(
        organization_id=organization_id,
        user_id=body.user_id,
        role=body.role,
    )
    session.add(membership)
    await session.flush()

    await record_event(
        session,
        action="org_member.added",
        actor_id=current_user.user_id,
        actor_email=current_user.sub,
        actor_role=current_user.role,
        organization_id=organization_id,
        entity_type="org_member",
        entity_id=str(body.user_id),
        after_state={"role": body.role},
    )

    return OrgMemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        organization_id=membership.organization_id,
        role=membership.role,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        invitation_status=_invitation_status_for_user(user),
        created_at=membership.created_at,
    )


@router.post(
    "/organizations/{organization_id}/invite-user",
    response_model=InviteOrgMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_org_member(
    organization_id: uuid.UUID,
    body: InviteOrgMemberRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> InviteOrgMemberResponse:
    """Invite a new organization member without requiring tenant selection in the UI."""
    if not await authorize_org_admin(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")

    org_result = await session.execute(select(Organization.id).where(Organization.id == organization_id))
    if org_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if body.home_tenant_id is not None:
        tenant_result = await session.execute(
            select(Tenant.id, Tenant.organization_id).where(Tenant.id == body.home_tenant_id)
        )
        tenant_row = tenant_result.first()
        if tenant_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Home tenant not found")
        if tenant_row.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Home tenant must belong to the selected organization",
            )
        selected_tenant_id = body.home_tenant_id
    else:
        tenant_result = await session.execute(
            select(Tenant.id)
            .where(Tenant.organization_id == organization_id)
            .order_by(Tenant.is_active.desc(), Tenant.display_name.asc())
        )
        tenant_row = tenant_result.first()
        if tenant_row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Create at least one workspace in this organization before inviting members",
            )
        selected_tenant_id = tenant_row.id

    normalized_email = body.email.strip().lower()
    display_name = body.display_name.strip() or normalized_email.split("@")[0]
    token = generate_invitation_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    existing_user_result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    existing_user = existing_user_result.scalar_one_or_none()
    invitation_url: str | None = None
    response_expires_at: datetime | None = None
    response_status = "invited"

    if existing_user is None:
        user = User(
            tenant_id=selected_tenant_id,
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
        invitation_url = f"{settings.FRONTEND_URL}/set-password?token={token}"
        response_expires_at = expires_at
    else:
        user = existing_user
        if existing_user.is_active:
            response_status = "access_granted"
        else:
            user.tenant_id = selected_tenant_id
            user.display_name = display_name
            user.role = body.role
            user.is_active = False
            user.hashed_password = None
            user.invitation_token = token
            user.invitation_expires_at = expires_at
            invitation_url = f"{settings.FRONTEND_URL}/set-password?token={token}"
            response_expires_at = expires_at
        session.add(user)
        await session.flush()

    membership_result = await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=user.id,
            role=body.role,
        )
        session.add(membership)
    else:
        membership.role = body.role
        session.add(membership)

    await session.flush()

    if response_status == "invited" and invitation_url is not None:
        await send_user_invitation_email(
            email=user.email,
            display_name=display_name,
            invitation_url=invitation_url,
        )

    await record_event(
        session,
        action="org_member.invited" if response_status == "invited" else "org_member.access_granted",
        actor_id=current_user.user_id,
        actor_email=current_user.sub,
        actor_role=current_user.role,
        organization_id=organization_id,
        entity_type="org_member",
        entity_id=str(user.id),
        after_state={
            "role": body.role,
            "email": user.email,
            "bootstrap_tenant_id": str(selected_tenant_id),
            "status": response_status,
        },
    )

    return InviteOrgMemberResponse(
        user_id=user.id,
        email=user.email,
        role=body.role,
        organization_id=organization_id,
        home_tenant_id=selected_tenant_id,
        invitation_url=invitation_url,
        expires_at=response_expires_at,
        status=response_status,
    )


@router.patch("/organizations/{organization_id}/members/{user_id}", response_model=OrgMemberResponse)
async def update_org_member(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    body: OrgMemberUpdateRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> OrgMemberResponse:
    """Update the role of an organization member."""
    if not await authorize_org_admin(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")

    result = await session.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    old_role = membership.role
    membership.role = body.role
    session.add(membership)
    await session.flush()

    await record_event(
        session,
        action="org_member.role_updated",
        actor_id=current_user.user_id,
        actor_email=current_user.sub,
        actor_role=current_user.role,
        organization_id=organization_id,
        entity_type="org_member",
        entity_id=str(user_id),
        before_state={"role": old_role},
        after_state={"role": body.role},
    )

    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    return OrgMemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        organization_id=membership.organization_id,
        role=membership.role,
        email=user.email if user else None,
        display_name=user.display_name if user else None,
        is_active=user.is_active if user else None,
        invitation_status=_invitation_status_for_user(user),
        created_at=membership.created_at,
    )


@router.delete("/organizations/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_org_member(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> None:
    """Remove a user from the organization."""
    if not await authorize_org_admin(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")

    # Fetch role before deleting for audit record
    fetch_result = await session.execute(
        select(OrganizationMembership.role).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    removed_role = fetch_result.scalar_one_or_none()
    if removed_role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    await session.execute(
        delete(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
    )

    await record_event(
        session,
        action="org_member.removed",
        actor_id=current_user.user_id,
        actor_email=current_user.sub,
        actor_role=current_user.role,
        organization_id=organization_id,
        entity_type="org_member",
        entity_id=str(user_id),
        before_state={"role": removed_role},
    )


# ─── Org Analytics ────────────────────────────────────────────────────────────


class OrgAnalyticsResponse(BaseModel):
    organization_id: uuid.UUID
    tenant_count: int
    active_tenant_count: int
    member_count: int


@router.get("/organizations/{organization_id}/analytics", response_model=OrgAnalyticsResponse)
async def get_org_analytics(
    organization_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> OrgAnalyticsResponse:
    """Return aggregate analytics for an organization."""
    if not await authorize_org_access(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for organization")

    has_full_org_access = (
        normalize_role_name(current_user.role) == "platform_admin"
        or await authorize_org_admin(session, current_user, organization_id)
    )

    visible_tenant_query = select(Tenant.id, Tenant.is_active).where(
        Tenant.organization_id == organization_id
    )
    if not has_full_org_access:
        visible_tenant_query = visible_tenant_query.where(
            or_(
                Tenant.id == current_user.tenant_id,
                Tenant.id.in_(
                    select(TenantMembership.tenant_id).where(
                        TenantMembership.user_id == current_user.user_id
                    )
                ),
            )
        )

    visible_tenants_result = await session.execute(visible_tenant_query)
    visible_tenant_rows = visible_tenants_result.all()
    visible_tenant_ids = [row.id for row in visible_tenant_rows]

    member_ids: set[uuid.UUID] = set()
    if visible_tenant_ids:
        home_members_result = await session.execute(
            select(User.id).where(User.tenant_id.in_(visible_tenant_ids))
        )
        explicit_members_result = await session.execute(
            select(TenantMembership.user_id).where(
                TenantMembership.tenant_id.in_(visible_tenant_ids)
            )
        )
        member_ids.update(home_members_result.scalars().all())
        member_ids.update(explicit_members_result.scalars().all())

    return OrgAnalyticsResponse(
        organization_id=organization_id,
        tenant_count=len(visible_tenant_ids),
        active_tenant_count=sum(1 for row in visible_tenant_rows if row.is_active),
        member_count=len(member_ids),
    )


# ─── Shared helper ────────────────────────────────────────────────────────────


async def _require_org_access(
    session: AsyncSession,
    current_user: TokenData,
    organization_id: uuid.UUID,
) -> None:
    """Raise 403 if the user cannot access the organization."""
    if not await authorize_org_admin(session, current_user, organization_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")
