"""Tenant-scoped project APIs."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    authorize_tenant_access,
    authorize_tenant_admin,
    get_authenticated_user,
    get_auth_session,
)
from airex_core.core.security import TokenData
from airex_core.models.project import Project

router = APIRouter()


class ProjectResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    description: str
    is_active: bool


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = ""


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    slug: str | None = Field(None, min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None
    is_active: bool | None = None


@router.get("/tenants/{tenant_id}/projects", response_model=list[ProjectResponse])
async def list_projects(
    tenant_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> list[ProjectResponse]:
    """List projects for a tenant."""
    if not await authorize_tenant_access(session, current_user, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for tenant")

    result = await session.execute(
        select(Project).where(Project.tenant_id == tenant_id).order_by(Project.name.asc())
    )
    projects = result.scalars().all()
    return [
        ProjectResponse(
            id=project.id,
            tenant_id=project.tenant_id,
            name=project.name,
            slug=project.slug,
            description=project.description,
            is_active=project.is_active,
        )
        for project in projects
    ]


@router.post("/tenants/{tenant_id}/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    tenant_id: uuid.UUID,
    body: ProjectCreateRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> ProjectResponse:
    """Create a project inside a tenant."""
    if not await authorize_tenant_admin(session, current_user, tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin required")

    existing = await session.execute(
        select(Project.id).where(Project.tenant_id == tenant_id, Project.slug == body.slug.lower().strip())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project slug already exists")

    project = Project(
        tenant_id=tenant_id,
        name=body.name.strip(),
        slug=body.slug.lower().strip(),
        description=body.description,
        is_active=True,
    )
    session.add(project)
    await session.flush()
    return ProjectResponse(
        id=project.id,
        tenant_id=project.tenant_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        is_active=project.is_active,
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> ProjectResponse:
    """Get a project detail."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not await authorize_tenant_access(session, current_user, project.tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for tenant")
    return ProjectResponse(
        id=project.id,
        tenant_id=project.tenant_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        is_active=project.is_active,
    )


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdateRequest,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> ProjectResponse:
    """Update a project."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not await authorize_tenant_admin(session, current_user, project.tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin required")

    if body.slug and body.slug.lower().strip() != project.slug:
        existing = await session.execute(
            select(Project.id).where(
                Project.tenant_id == project.tenant_id,
                Project.slug == body.slug.lower().strip(),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project slug already exists")

    if body.name is not None:
        project.name = body.name.strip()
    if body.slug is not None:
        project.slug = body.slug.lower().strip()
    if body.description is not None:
        project.description = body.description
    if body.is_active is not None:
        project.is_active = body.is_active
    session.add(project)
    await session.flush()
    return ProjectResponse(
        id=project.id,
        tenant_id=project.tenant_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        is_active=project.is_active,
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    current_user: TokenData = Depends(get_authenticated_user),
    session: AsyncSession = Depends(get_auth_session),
) -> None:
    """Delete a project."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not await authorize_tenant_admin(session, current_user, project.tenant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant admin required")
    await session.delete(project)
