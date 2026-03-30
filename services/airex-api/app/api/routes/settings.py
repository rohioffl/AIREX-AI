"""
Settings API endpoints.

Allows reading and updating application settings (admin only).
"""

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import CurrentUser, RequirePlatformAdmin
from airex_core.core.config import settings

logger = structlog.get_logger()

router = APIRouter()


def _update_llm_clients() -> None:
    from airex_core.services import chat_service, postmortem_service, recommendation_service

    for service in (chat_service, postmortem_service, recommendation_service):
        service.llm_client.circuit_breaker.threshold = settings.LLM_CIRCUIT_BREAKER_THRESHOLD
        service.llm_client.circuit_breaker.cooldown = settings.LLM_CIRCUIT_BREAKER_COOLDOWN


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
    email_provider: str
    email_region: str | None
    email_from: str | None


class SettingsUpdate(BaseModel):
    """Settings that can be updated."""
    llm_provider: str | None = None
    llm_primary_model: str | None = None
    llm_fallback_model: str | None = None
    llm_circuit_breaker_threshold: int | None = None
    llm_circuit_breaker_cooldown: int | None = None
    investigation_timeout: int | None = None
    execution_timeout: int | None = None
    verification_timeout: int | None = None
    max_investigation_retries: int | None = None
    max_execution_retries: int | None = None
    max_verification_retries: int | None = None
    lock_ttl: int | None = None
    slack_webhook_url: str | None = None
    email_from: str | None = None


@router.get("/", response_model=SettingsResponse)
async def get_settings(
    _: RequirePlatformAdmin,
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
        email_provider="aws_ses",
        email_region=getattr(settings, "AWS_SES_REGION", None) or getattr(settings, "AWS_REGION", None),
        email_from=getattr(settings, "EMAIL_FROM", None),
    )


@router.patch("/")
async def update_settings(
    _: RequirePlatformAdmin,
    update: SettingsUpdate,
    current_user: CurrentUser,
) -> dict:
    """
    Update application settings (admin only).
    
    Note: Most settings are environment variables and require restart.
    This endpoint validates the request but settings are read-only at runtime.
    For production, update .env and restart the service.
    """
    # Validate ranges
    if update.llm_circuit_breaker_threshold is not None and (update.llm_circuit_breaker_threshold < 1 or update.llm_circuit_breaker_threshold > 20):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="llm_circuit_breaker_threshold must be between 1 and 20",
        )
    if update.llm_circuit_breaker_cooldown is not None and (update.llm_circuit_breaker_cooldown < 5 or update.llm_circuit_breaker_cooldown > 3600):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="llm_circuit_breaker_cooldown must be between 5 and 3600 seconds",
        )
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
    if update.max_execution_retries is not None and (update.max_execution_retries < 0 or update.max_execution_retries > 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_execution_retries must be between 0 and 10",
        )
    if update.max_verification_retries is not None and (update.max_verification_retries < 0 or update.max_verification_retries > 10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_verification_retries must be between 0 and 10",
        )
    if update.lock_ttl is not None and (update.lock_ttl < 30 or update.lock_ttl > 600):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="lock_ttl must be between 30 and 600 seconds",
        )

    applied_updates = update.model_dump(exclude_unset=True)
    field_mapping = {
        "llm_provider": "LLM_PROVIDER",
        "llm_primary_model": "LLM_PRIMARY_MODEL",
        "llm_fallback_model": "LLM_FALLBACK_MODEL",
        "llm_circuit_breaker_threshold": "LLM_CIRCUIT_BREAKER_THRESHOLD",
        "llm_circuit_breaker_cooldown": "LLM_CIRCUIT_BREAKER_COOLDOWN",
        "investigation_timeout": "INVESTIGATION_TIMEOUT",
        "execution_timeout": "EXECUTION_TIMEOUT",
        "verification_timeout": "VERIFICATION_TIMEOUT",
        "max_investigation_retries": "MAX_INVESTIGATION_RETRIES",
        "max_execution_retries": "MAX_EXECUTION_RETRIES",
        "max_verification_retries": "MAX_VERIFICATION_RETRIES",
        "lock_ttl": "LOCK_TTL",
        "slack_webhook_url": "SLACK_WEBHOOK_URL",
        "email_from": "EMAIL_FROM",
    }
    for field_name, value in applied_updates.items():
        setattr(settings, field_mapping[field_name], value)
    _update_llm_clients()
    
    logger.info(
        "settings_updated_runtime",
        user=current_user.sub if current_user else "unknown",
        updates=applied_updates,
    )
    
    return {
        "status": "updated",
        "message": "Settings applied in-memory for the running API process.",
        "applied_updates": applied_updates,
    }
