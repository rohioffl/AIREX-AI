"""Platform-admin-only summary APIs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentUser, RequirePlatformAdmin, Redis, get_auth_session
from app.api.routes.dlq import DLQ_KEY
from airex_core.llm.client import CB_REDIS_KEY
from airex_core.core.platform_admin_db import get_platform_admin_session
from airex_core.core.security import hash_password
from airex_core.models.enums import IncidentState
from airex_core.models.incident import Incident
from airex_core.models.organization import Organization
from airex_core.models.platform_admin import PlatformAdmin
from airex_core.models.tenant import Tenant
from airex_core.models.user import User

router = APIRouter()

class PlatformAdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    role: str = "platform_admin"

class PlatformAdminListResponse(BaseModel):
    items: list[PlatformAdminUserResponse]


class PlatformAdminCreateRequest(BaseModel):
    email: EmailStr
    display_name: str
    password: str


class PlatformAdminUpdateRequest(BaseModel):
    display_name: str | None = None
    password: str | None = None
    is_active: bool | None = None


class PlatformAnalyticsResponse(BaseModel):
    total_users: int
    active_users: int
    total_platform_admins: int
    active_platform_admins: int
    total_organizations: int
    active_organizations: int
    total_tenants: int
    active_tenants: int
    active_incidents: int
    critical_incidents: int
    failed_incidents_24h: int
    total_incidents_24h: int
    platform_error_rate_24h: float
    dlq_entries: int
    llm_circuit_breaker_open: bool


@router.get("/analytics", response_model=PlatformAnalyticsResponse)
async def get_platform_analytics(
    _: RequirePlatformAdmin,
    redis: Redis,
    session: AsyncSession = Depends(get_auth_session),
    platform_admin_session: AsyncSession = Depends(get_platform_admin_session),
) -> PlatformAnalyticsResponse:
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    active_states = [
        IncidentState.RECEIVED,
        IncidentState.INVESTIGATING,
        IncidentState.RECOMMENDATION_READY,
        IncidentState.AWAITING_APPROVAL,
        IncidentState.EXECUTING,
        IncidentState.VERIFYING,
    ]
    failed_states = [
        IncidentState.FAILED_ANALYSIS,
        IncidentState.FAILED_EXECUTION,
        IncidentState.FAILED_VERIFICATION,
    ]

    total_users = (await session.execute(select(func.count(User.id)))).scalar_one() or 0
    active_users = (
        await session.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
    ).scalar_one() or 0
    total_platform_admins = (
        await platform_admin_session.execute(select(func.count(PlatformAdmin.id)))
    ).scalar_one() or 0
    active_platform_admins = (
        await platform_admin_session.execute(
            select(func.count(PlatformAdmin.id)).where(PlatformAdmin.is_active.is_(True))
        )
    ).scalar_one() or 0
    total_organizations = (
        await session.execute(select(func.count(Organization.id)))
    ).scalar_one() or 0
    active_organizations = (
        await session.execute(
            select(func.count(Organization.id)).where(Organization.status == "active")
        )
    ).scalar_one() or 0
    total_tenants = (await session.execute(select(func.count(Tenant.id)))).scalar_one() or 0
    active_tenants = (
        await session.execute(select(func.count(Tenant.id)).where(Tenant.is_active.is_(True)))
    ).scalar_one() or 0
    active_incidents = (
        await session.execute(
            select(func.count(Incident.id)).where(
                Incident.deleted_at.is_(None),
                Incident.state.in_(active_states),
            )
        )
    ).scalar_one() or 0
    critical_incidents = (
        await session.execute(
            select(func.count(Incident.id)).where(
                Incident.deleted_at.is_(None),
                Incident.state.in_(active_states),
                Incident.severity == "CRITICAL",
            )
        )
    ).scalar_one() or 0
    failed_incidents_24h = (
        await session.execute(
            select(func.count(Incident.id)).where(
                Incident.deleted_at.is_(None),
                Incident.state.in_(failed_states),
                Incident.updated_at >= day_ago,
            )
        )
    ).scalar_one() or 0
    total_incidents_24h = (
        await session.execute(
            select(func.count(Incident.id)).where(
                Incident.deleted_at.is_(None),
                Incident.created_at >= day_ago,
            )
        )
    ).scalar_one() or 0

    redis_client = cast(Any, redis)
    dlq_entries = await redis_client.llen(DLQ_KEY)
    cb_state_raw = await redis_client.get(CB_REDIS_KEY)
    cb_state: dict[str, Any] = {}
    if cb_state_raw:
        try:
            cb_state = json.loads(
                cb_state_raw.decode() if isinstance(cb_state_raw, bytes) else str(cb_state_raw)
            )
        except json.JSONDecodeError:
            cb_state = {}

    return PlatformAnalyticsResponse(
        total_users=total_users,
        active_users=active_users,
        total_platform_admins=total_platform_admins,
        active_platform_admins=active_platform_admins,
        total_organizations=total_organizations,
        active_organizations=active_organizations,
        total_tenants=total_tenants,
        active_tenants=active_tenants,
        active_incidents=active_incidents,
        critical_incidents=critical_incidents,
        failed_incidents_24h=failed_incidents_24h,
        total_incidents_24h=total_incidents_24h,
        platform_error_rate_24h=(
            failed_incidents_24h / total_incidents_24h if total_incidents_24h else 0.0
        ),
        dlq_entries=dlq_entries,
        llm_circuit_breaker_open=bool(cb_state.get("is_open", False)),
    )


def _serialize_platform_admin(admin: PlatformAdmin) -> PlatformAdminUserResponse:
    return PlatformAdminUserResponse(
        id=admin.id,
        email=admin.email,
        display_name=admin.display_name,
        is_active=admin.is_active,
        role="platform_admin",
    )


def _validate_platform_admin_password(password: str) -> str:
    normalized = password.strip()
    if len(normalized) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )
    return normalized


@router.get("/admins", response_model=PlatformAdminListResponse)
async def list_platform_admins(
    _: RequirePlatformAdmin,
    session: AsyncSession = Depends(get_platform_admin_session),
) -> PlatformAdminListResponse:
    result = await session.execute(select(PlatformAdmin).order_by(PlatformAdmin.created_at.desc()))
    admins = result.scalars().all()
    return PlatformAdminListResponse(items=[_serialize_platform_admin(admin) for admin in admins])


@router.post("/admins", response_model=PlatformAdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_admin(
    body: PlatformAdminCreateRequest,
    _: RequirePlatformAdmin,
    session: AsyncSession = Depends(get_platform_admin_session),
) -> PlatformAdminUserResponse:
    normalized_email = body.email.strip().lower()
    existing = await session.execute(
        select(PlatformAdmin).where(func.lower(PlatformAdmin.email) == normalized_email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Platform admin with this email already exists",
        )

    admin = PlatformAdmin(
        email=normalized_email,
        display_name=body.display_name.strip() or "Platform Admin",
        hashed_password=hash_password(_validate_platform_admin_password(body.password)),
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    return _serialize_platform_admin(admin)


@router.patch("/admins/{admin_id}", response_model=PlatformAdminUserResponse)
async def update_platform_admin(
    admin_id: uuid.UUID,
    body: PlatformAdminUpdateRequest,
    _: RequirePlatformAdmin,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_platform_admin_session),
) -> PlatformAdminUserResponse:
    result = await session.execute(select(PlatformAdmin).where(PlatformAdmin.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform admin not found")

    if body.display_name is not None:
        display_name = body.display_name.strip()
        if not display_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name cannot be empty",
            )
        admin.display_name = display_name

    if body.password is not None:
        admin.hashed_password = hash_password(
            _validate_platform_admin_password(body.password)
        )

    if body.is_active is not None and body.is_active != admin.is_active:
        if not body.is_active and current_user and current_user.user_id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own platform admin account",
            )
        if not body.is_active:
            active_count = (
                await session.execute(
                    select(func.count(PlatformAdmin.id)).where(PlatformAdmin.is_active.is_(True))
                )
            ).scalar_one() or 0
            if active_count <= 1 and admin.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least one active platform admin account must remain",
                )
        admin.is_active = body.is_active

    await session.flush()
    return _serialize_platform_admin(admin)
