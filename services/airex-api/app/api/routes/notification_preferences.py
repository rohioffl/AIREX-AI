"""
Notification preferences API endpoints.

Allows users to manage their notification preferences for email and Slack.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import CurrentUser, TenantId, TenantSession
from airex_core.models.notification_preference import NotificationPreference
from airex_core.models.user import User
from sqlalchemy import select

logger = structlog.get_logger()

router = APIRouter()


class NotificationPreferenceResponse(BaseModel):
    user_id: uuid.UUID
    email_enabled: bool
    email_critical_only: bool
    slack_enabled: bool
    slack_webhook_url: str | None
    slack_critical_only: bool
    notify_on_received: bool
    notify_on_investigating: bool
    notify_on_recommendation_ready: bool
    notify_on_awaiting_approval: bool
    notify_on_executing: bool
    notify_on_verifying: bool
    notify_on_resolved: bool
    notify_on_rejected: bool
    notify_on_failed: bool
    metadata: dict | None
    created_at: str
    updated_at: str


class NotificationPreferenceUpdateRequest(BaseModel):
    email_enabled: bool | None = None
    email_critical_only: bool | None = None
    slack_enabled: bool | None = None
    slack_webhook_url: str | None = None
    slack_critical_only: bool | None = None
    notify_on_received: bool | None = None
    notify_on_investigating: bool | None = None
    notify_on_recommendation_ready: bool | None = None
    notify_on_awaiting_approval: bool | None = None
    notify_on_executing: bool | None = None
    notify_on_verifying: bool | None = None
    notify_on_resolved: bool | None = None
    notify_on_rejected: bool | None = None
    notify_on_failed: bool | None = None
    metadata: dict | None = None


@router.get("/me", response_model=NotificationPreferenceResponse)
async def get_my_preferences(
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> NotificationPreferenceResponse:
    """Get current user's notification preferences."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.tenant_id == tenant_id,
            NotificationPreference.user_id == current_user.user_id,
        )
    )
    pref = result.scalar_one_or_none()

    # Return defaults if no preferences exist
    if pref is None:
        return NotificationPreferenceResponse(
            user_id=current_user.user_id,
            email_enabled=True,
            email_critical_only=False,
            slack_enabled=False,
            slack_webhook_url=None,
            slack_critical_only=False,
            notify_on_received=False,
            notify_on_investigating=False,
            notify_on_recommendation_ready=True,
            notify_on_awaiting_approval=True,
            notify_on_executing=False,
            notify_on_verifying=False,
            notify_on_resolved=True,
            notify_on_rejected=True,
            notify_on_failed=True,
            metadata=None,
            created_at="",
            updated_at="",
        )

    return NotificationPreferenceResponse(
        user_id=pref.user_id,
        email_enabled=pref.email_enabled,
        email_critical_only=pref.email_critical_only,
        slack_enabled=pref.slack_enabled,
        slack_webhook_url=pref.slack_webhook_url,
        slack_critical_only=pref.slack_critical_only,
        notify_on_received=pref.notify_on_received,
        notify_on_investigating=pref.notify_on_investigating,
        notify_on_recommendation_ready=pref.notify_on_recommendation_ready,
        notify_on_awaiting_approval=pref.notify_on_awaiting_approval,
        notify_on_executing=pref.notify_on_executing,
        notify_on_verifying=pref.notify_on_verifying,
        notify_on_resolved=pref.notify_on_resolved,
        notify_on_rejected=pref.notify_on_rejected,
        notify_on_failed=pref.notify_on_failed,
        metadata=pref.metadata,
        created_at=pref.created_at.isoformat(),
        updated_at=pref.updated_at.isoformat(),
    )


@router.put("/me", response_model=NotificationPreferenceResponse)
async def update_my_preferences(
    body: NotificationPreferenceUpdateRequest,
    tenant_id: TenantId,
    session: TenantSession,
    current_user: CurrentUser,
) -> NotificationPreferenceResponse:
    """Update current user's notification preferences."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.tenant_id == tenant_id,
            NotificationPreference.user_id == current_user.user_id,
        )
    )
    pref = result.scalar_one_or_none()

    if pref is None:
        # Create new preferences
        pref = NotificationPreference(
            tenant_id=tenant_id,
            user_id=current_user.user_id,
            email_enabled=body.email_enabled if body.email_enabled is not None else True,
            email_critical_only=body.email_critical_only if body.email_critical_only is not None else False,
            slack_enabled=body.slack_enabled if body.slack_enabled is not None else False,
            slack_webhook_url=body.slack_webhook_url,
            slack_critical_only=body.slack_critical_only if body.slack_critical_only is not None else False,
            notify_on_received=body.notify_on_received if body.notify_on_received is not None else False,
            notify_on_investigating=body.notify_on_investigating if body.notify_on_investigating is not None else False,
            notify_on_recommendation_ready=body.notify_on_recommendation_ready if body.notify_on_recommendation_ready is not None else True,
            notify_on_awaiting_approval=body.notify_on_awaiting_approval if body.notify_on_awaiting_approval is not None else True,
            notify_on_executing=body.notify_on_executing if body.notify_on_executing is not None else False,
            notify_on_verifying=body.notify_on_verifying if body.notify_on_verifying is not None else False,
            notify_on_resolved=body.notify_on_resolved if body.notify_on_resolved is not None else True,
            notify_on_rejected=body.notify_on_rejected if body.notify_on_rejected is not None else True,
            notify_on_failed=body.notify_on_failed if body.notify_on_failed is not None else True,
            metadata=body.metadata,
        )
        session.add(pref)
    else:
        # Update existing preferences
        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(pref, key, value)

    await session.flush()

    logger.info(
        "notification_preferences_updated",
        tenant_id=str(tenant_id),
        user_id=str(current_user.user_id),
    )

    return NotificationPreferenceResponse(
        user_id=pref.user_id,
        email_enabled=pref.email_enabled,
        email_critical_only=pref.email_critical_only,
        slack_enabled=pref.slack_enabled,
        slack_webhook_url=pref.slack_webhook_url,
        slack_critical_only=pref.slack_critical_only,
        notify_on_received=pref.notify_on_received,
        notify_on_investigating=pref.notify_on_investigating,
        notify_on_recommendation_ready=pref.notify_on_recommendation_ready,
        notify_on_awaiting_approval=pref.notify_on_awaiting_approval,
        notify_on_executing=pref.notify_on_executing,
        notify_on_verifying=pref.notify_on_verifying,
        notify_on_resolved=pref.notify_on_resolved,
        notify_on_rejected=pref.notify_on_rejected,
        notify_on_failed=pref.notify_on_failed,
        metadata=pref.metadata,
        created_at=pref.created_at.isoformat(),
        updated_at=pref.updated_at.isoformat(),
    )
