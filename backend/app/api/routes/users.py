"""
Admin user management endpoints.

Requires ADMIN role for all operations.
"""

import uuid

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
from app.core.security import (
    UserResponse,
    hash_password,
)
from app.models.enums import UserRole
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter()


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
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

    items = [
        UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            display_name=u.display_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]

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

    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
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

    user = User(
        tenant_id=tenant_id,
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
        role=body.role.lower(),
        is_active=body.is_active,
    )
    session.add(user)
    await session.flush()

    logger.info(
        "user_created_by_admin",
        email=body.email,
        user_id=str(user.id),
        role=body.role,
    )

    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
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

    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
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
