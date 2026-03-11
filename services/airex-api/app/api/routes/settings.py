"""
Settings API endpoints.

Allows reading and updating application settings (admin only).
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import CurrentUser, RequireAdmin, TenantId
from airex_core.core.config import settings

logger = structlog.get_logger()

router = APIRouter()


class SettingsResponse(BaseModel):
    """Read-only settings view."""
    # AI / LLM
    llm_provider: str
    llm_primary_model: str
    llm_fallback_model: str
    llm_circuit_breaker_threshold: int
    llm_circuit_breaker_cooldown: int
    
    # Pipeline
    investigation_timeout: int
    execution_timeout: int
    verification_timeout: int
    max_investigation_retries: int
    max_execution_retries: int
    max_verification_retries: int
    
    # Rate Limiting
    lock_ttl: int
    
    # Notifications
    slack_webhook_url: str | None
    email_smtp_host: str | None
    email_smtp_port: int | None
    email_from: str | None


class SettingsUpdate(BaseModel):
    """Settings that can be updated."""
    investigation_timeout: int | None = None
    execution_timeout: int | None = None
    verification_timeout: int | None = None
    max_investigation_retries: int | None = None
    max_execution_retries: int | None = None
    max_verification_retries: int | None = None
    lock_ttl: int | None = None
    slack_webhook_url: str | None = None
    email_smtp_host: str | None = None
    email_smtp_port: int | None = None
    email_from: str | None = None


@router.get("/", response_model=SettingsResponse, dependencies=[Depends(RequireAdmin)])
async def get_settings(
    tenant_id: TenantId,
    current_user: CurrentUser,
) -> SettingsResponse:
    """
    Get current application settings (admin only).
    
    Returns read-only view of settings. Some settings are environment-only
    and cannot be changed at runtime.
    """
    return SettingsResponse(
        llm_provider=settings.LLM_PROVIDER,
        llm_primary_model=settings.LLM_PRIMARY_MODEL,
        llm_fallback_model=settings.LLM_FALLBACK_MODEL,
        llm_circuit_breaker_threshold=settings.LLM_CIRCUIT_BREAKER_THRESHOLD,
        llm_circuit_breaker_cooldown=settings.LLM_CIRCUIT_BREAKER_COOLDOWN,
        investigation_timeout=settings.INVESTIGATION_TIMEOUT,
        execution_timeout=settings.EXECUTION_TIMEOUT,
        verification_timeout=settings.VERIFICATION_TIMEOUT,
        max_investigation_retries=settings.MAX_INVESTIGATION_RETRIES,
        max_execution_retries=settings.MAX_EXECUTION_RETRIES,
        max_verification_retries=settings.MAX_VERIFICATION_RETRIES,
        lock_ttl=settings.LOCK_TTL,
        slack_webhook_url=getattr(settings, "SLACK_WEBHOOK_URL", None),
        email_smtp_host=getattr(settings, "EMAIL_SMTP_HOST", None),
        email_smtp_port=getattr(settings, "EMAIL_SMTP_PORT", None),
        email_from=getattr(settings, "EMAIL_FROM", None),
    )


@router.patch("/", dependencies=[Depends(RequireAdmin)])
async def update_settings(
    tenant_id: TenantId,
    current_user: CurrentUser,
    update: SettingsUpdate,
) -> dict:
    """
    Update application settings (admin only).
    
    Note: Most settings are environment variables and require restart.
    This endpoint validates the request but settings are read-only at runtime.
    For production, update .env and restart the service.
    """
    # Validate ranges
    if update.investigation_timeout is not None and (update.investigation_timeout < 10 or update.investigation_timeout > 300):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="investigation_timeout must be between 10 and 300 seconds",
        )
    if update.execution_timeout is not None and (update.execution_timeout < 5 or update.execution_timeout > 120):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="execution_timeout must be between 5 and 120 seconds",
        )
    if update.max_investigation_retries is not None and (update.max_investigation_retries < 0 or update.max_investigation_retries > 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_investigation_retries must be between 0 and 10",
        )
    
    logger.info(
        "settings_update_requested",
        tenant_id=str(tenant_id),
        user=current_user.sub if current_user else "unknown",
        updates=update.model_dump(exclude_unset=True),
    )
    
    # In a real implementation, you might store these in a database
    # For now, return a message that settings require environment variable changes
    return {
        "status": "accepted",
        "message": "Settings are environment variables. Update .env file and restart the service for changes to take effect.",
        "requested_updates": update.model_dump(exclude_unset=True),
    }
