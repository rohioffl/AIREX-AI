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

from app.api.dependencies import (
    CurrentUser,
    RequireAdmin,
    TenantId,
    TenantSession,
)
from airex_core.core.security import (
    UserResponse,
    hash_password,
)
from airex_core.models.enums import UserRole
from airex_core.models.user import User

logger = structlog.get_logger()

router = APIRouter()


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


@router.get("/", response_model=UserListResponse, dependencies=[Depends(RequireAdmin)])
async def list_users(
    tenant_id: TenantId,
    session: TenantSession,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
) -> UserListResponse:
    """List all users in the tenant (admin only)."""
    # Count total
    count_q = select(func.count()).select_from(User).where(User.tenant_id == tenant_id)
    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    # Fetch users
    query = (
        select(User)
        .where(User.tenant_id == tenant_id)
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
            if u.invitation_expires_at and u.invitation_expires_at < datetime.now(timezone.utc):
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


@router.get(
    "/{user_id}", response_model=UserResponse, dependencies=[Depends(RequireAdmin)]
)
async def get_user(
    user_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> UserResponse:
    """Get user details (admin only)."""
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
        if user.invitation_expires_at and user.invitation_expires_at < datetime.now(timezone.utc):
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


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    dependencies=[Depends(RequireAdmin)],
)
async def create_user(
    body: UserCreateRequest,
    tenant_id: TenantId,
    session: TenantSession,
) -> UserResponse:
    """Create a new user (admin only)."""
    # Validate role
    try:
        UserRole(body.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {body.role}. Must be one of: {', '.join(r.value for r in UserRole)}",
        )

    # Check if email already exists
    result = await session.execute(select(User).where(User.email == body.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Generate invitation token if password not provided
    from airex_core.core.security import generate_invitation_token
    
    invitation_token = None
    invitation_expires_at = None
    hashed_password_value = None
    
    if body.password:
        # Direct creation with password (backward compatibility)
        hashed_password_value = hash_password(body.password)
    else:
        # Invitation flow: generate token
        invitation_token = generate_invitation_token()
        invitation_expires_at = datetime.now(timezone.utc) + timedelta(days=7)  # 7 day expiry

    user = User(
        tenant_id=tenant_id,
        email=body.email,
        hashed_password=hashed_password_value,
        display_name=body.display_name,
        role=body.role.lower(),
        is_active=body.is_active,
        invitation_token=invitation_token,
        invitation_expires_at=invitation_expires_at,
    )
    session.add(user)
    await session.flush()

    # Send invitation email if using invitation flow
    if invitation_token:
        try:
            from airex_core.services.notification_service import send_user_invitation_email
            from airex_core.core.config import settings
            
            invitation_url = f"{settings.FRONTEND_URL or 'http://localhost:5173'}/set-password?token={invitation_token}"
            await send_user_invitation_email(
                email=body.email,
                display_name=body.display_name,
                invitation_url=invitation_url,
            )
            logger.info("user_invitation_email_sent", email=body.email, user_id=str(user.id))
        except Exception as exc:
            logger.warning("user_invitation_email_failed", email=body.email, error=str(exc))

    logger.info(
        "user_created_by_admin",
        email=body.email,
        user_id=str(user.id),
        role=body.role,
        has_invitation=invitation_token is not None,
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


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(RequireAdmin)],
)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> UserResponse:
    """Update user (admin only). Cannot change own role or deactivate self."""
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
        if user.invitation_expires_at and user.invitation_expires_at < datetime.now(timezone.utc):
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


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequireAdmin)],
)
async def delete_user(
    user_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> None:
    """Delete (deactivate) a user (admin only). Cannot delete self."""
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


@router.post(
    "/{user_id}/resend-invitation",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RequireAdmin)],
)
async def resend_invitation(
    user_id: uuid.UUID,
    tenant_id: TenantId,
    session: TenantSession,
) -> dict:
    """Resend invitation email to a user (admin only)."""
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
