"""
Notification service for Slack and Email.

Sends notifications on critical incident state changes based on per-user
NotificationPreference settings and writes NotificationDeliveryLog audit rows.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from html import escape
from typing import Any

import aiohttp
import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.config import settings
from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.models.notification_delivery_log import NotificationDeliveryLog
from airex_core.models.notification_preference import NotificationPreference
from airex_core.models.user import User

logger = structlog.get_logger()


def _state_to_pref_key(state: IncidentState) -> str:
    """Map an IncidentState to the matching notify_on_X attribute on NotificationPreference."""
    mapping = {
        IncidentState.RECEIVED: "notify_on_received",
        IncidentState.INVESTIGATING: "notify_on_investigating",
        IncidentState.RECOMMENDATION_READY: "notify_on_recommendation_ready",
        IncidentState.AWAITING_APPROVAL: "notify_on_awaiting_approval",
        IncidentState.EXECUTING: "notify_on_executing",
        IncidentState.VERIFYING: "notify_on_verifying",
        IncidentState.RESOLVED: "notify_on_resolved",
        IncidentState.REJECTED: "notify_on_rejected",
        IncidentState.FAILED_ANALYSIS: "notify_on_failed",
        IncidentState.FAILED_EXECUTION: "notify_on_failed",
        IncidentState.FAILED_VERIFICATION: "notify_on_failed",
    }
    return mapping.get(state, "notify_on_failed")


async def send_slack_notification(
    incident_id: str,
    tenant_id: str,
    state: IncidentState,
    severity: SeverityLevel,
    title: str,
    message: str | None = None,
) -> bool:
    """
    Send Slack notification via webhook.

    Returns True if sent successfully, False otherwise.
    """
    correlation_id = incident_id

    if not settings.SLACK_WEBHOOK_URL:
        return False

    color_map = {
        SeverityLevel.CRITICAL: "#ff0000",
        SeverityLevel.HIGH: "#ff8800",
        SeverityLevel.MEDIUM: "#ffaa00",
        SeverityLevel.LOW: "#00aa00",
    }

    state_emoji = {
        IncidentState.RECEIVED: "🔔",
        IncidentState.INVESTIGATING: "🔍",
        IncidentState.RECOMMENDATION_READY: "💡",
        IncidentState.AWAITING_APPROVAL: "⏳",
        IncidentState.EXECUTING: "⚙️",
        IncidentState.VERIFYING: "✅",
        IncidentState.RESOLVED: "✅",
        IncidentState.REJECTED: "❌",
        IncidentState.FAILED_ANALYSIS: "⚠️",
        IncidentState.FAILED_EXECUTION: "⚠️",
        IncidentState.FAILED_VERIFICATION: "⚠️",
    }

    payload: dict[str, Any] = {
        "text": f"{state_emoji.get(state, '📋')} Incident {state.value}",
        "attachments": [
            {
                "color": color_map.get(severity, "#888888"),
                "fields": [
                    {"title": "Incident ID", "value": incident_id, "short": True},
                    {"title": "State", "value": state.value, "short": True},
                    {"title": "Severity", "value": severity.value, "short": True},
                    {"title": "Title", "value": title, "short": False},
                ],
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }
        ],
    }

    if message:
        payload["attachments"][0]["fields"].append(
            {"title": "Details", "value": message, "short": False}
        )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                settings.SLACK_WEBHOOK_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status == 200:
                    logger.info(
                        "slack_notification_sent",
                        correlation_id=correlation_id,
                        incident_id=incident_id,
                        tenant_id=tenant_id,
                        state=state.value,
                    )
                    return True
                else:
                    logger.warning(
                        "slack_notification_failed",
                        correlation_id=correlation_id,
                        incident_id=incident_id,
                        status=response.status,
                    )
                    return False
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.error(
            "slack_notification_error",
            correlation_id=correlation_id,
            incident_id=incident_id,
            error=str(exc),
        )
        return False


async def _send_slack_to_url(
    webhook_url: str,
    incident_id: str,
    tenant_id: str,
    state: IncidentState,
    severity: SeverityLevel,
    title: str,
    message: str | None = None,
) -> bool:
    """Send a Slack notification to an arbitrary webhook URL (per-user)."""
    color_map = {
        SeverityLevel.CRITICAL: "#ff0000",
        SeverityLevel.HIGH: "#ff8800",
        SeverityLevel.MEDIUM: "#ffaa00",
        SeverityLevel.LOW: "#00aa00",
    }
    state_emoji = {
        IncidentState.RECEIVED: "🔔",
        IncidentState.INVESTIGATING: "🔍",
        IncidentState.RECOMMENDATION_READY: "💡",
        IncidentState.AWAITING_APPROVAL: "⏳",
        IncidentState.EXECUTING: "⚙️",
        IncidentState.VERIFYING: "✅",
        IncidentState.RESOLVED: "✅",
        IncidentState.REJECTED: "❌",
        IncidentState.FAILED_ANALYSIS: "⚠️",
        IncidentState.FAILED_EXECUTION: "⚠️",
        IncidentState.FAILED_VERIFICATION: "⚠️",
    }
    from datetime import datetime, timezone
    payload: dict[str, Any] = {
        "text": f"{state_emoji.get(state, '📋')} Incident {state.value}",
        "attachments": [
            {
                "color": color_map.get(severity, "#888888"),
                "fields": [
                    {"title": "Incident ID", "value": incident_id, "short": True},
                    {"title": "State", "value": state.value, "short": True},
                    {"title": "Severity", "value": severity.value, "short": True},
                    {"title": "Title", "value": title, "short": False},
                ],
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }
        ],
    }
    if message:
        payload["attachments"][0]["fields"].append(
            {"title": "Details", "value": message, "short": False}
        )
    try:
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                return response.status == 200
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.warning(
            "per_user_slack_notification_error",
            incident_id=incident_id,
            error=str(exc),
        )
        return False


def _email_configured() -> bool:
    """Return True when the shared email sender has enough config to send mail."""
    return bool(settings.EMAIL_FROM)


def _email_region() -> str:
    """Return the SES region, falling back to the general AWS region."""
    return settings.AWS_SES_REGION or settings.AWS_REGION


async def _send_email_via_ses(
    *,
    subject: str,
    recipient: str,
    text_content: str,
    html_content: str,
    success_event: str,
    error_event: str,
    log_context: dict[str, Any],
) -> bool:
    """Send an email using AWS SES with the task's IAM role credentials."""
    if not _email_configured():
        logger.warning("email_not_configured", recipient=recipient)
        return False

    def _send() -> None:
        ses_client = boto3.client("ses", region_name=_email_region())
        ses_client.send_email(
            Source=settings.EMAIL_FROM,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_content, "Charset": "UTF-8"},
                    "Html": {"Data": html_content, "Charset": "UTF-8"},
                },
            },
        )

    try:
        await asyncio.to_thread(_send)
    except (BotoCoreError, ClientError, OSError) as exc:
        logger.error(error_event, recipient=recipient, error=str(exc), **log_context)
        return False

    logger.info(success_event, recipient=recipient, **log_context)
    return True


async def send_email_notification(
    incident_id: str,
    tenant_id: str,
    state: IncidentState,
    severity: SeverityLevel,
    title: str,
    recipient: str,
    message: str | None = None,
) -> bool:
    """
    Send email notification via AWS SES.

    Returns True if sent successfully, False otherwise.
    """
    correlation_id = incident_id

    text_content = f"""
Incident {incident_id} - {state.value}

Severity: {severity.value}
Title: {title}
{message or ""}

View details: /incidents/{incident_id}
"""

    html_content = f"""
<html>
<body>
<h2>Incident {escape(incident_id)} - {escape(state.value)}</h2>
<p><strong>Severity:</strong> {escape(severity.value)}</p>
<p><strong>Title:</strong> {escape(title)}</p>
{f"<p>{escape(message)}</p>" if message else ""}
<p><a href="/incidents/{escape(incident_id)}">View Details</a></p>
</body>
</html>
"""

    return await _send_email_via_ses(
        subject=f"[AIREX] {severity.value}: {title}",
        recipient=recipient,
        text_content=text_content,
        html_content=html_content,
        success_event="email_notification_sent",
        error_event="email_notification_error",
        log_context={
            "correlation_id": correlation_id,
            "incident_id": incident_id,
            "tenant_id": tenant_id,
            "state": state.value,
        },
    )


async def notify_incident_state_change(
    session: AsyncSession,
    incident_id: str,
    tenant_id: str,
    old_state: IncidentState,
    new_state: IncidentState,
    severity: SeverityLevel,
    title: str,
) -> None:
    """
    Send per-user notifications on state transitions.

    Loads all NotificationPreference rows for the tenant, checks each user's
    per-state flag and critical_only filter, dispatches email and/or Slack,
    and writes a NotificationDeliveryLog audit row per attempt.
    """
    pref_key = _state_to_pref_key(new_state)
    message = f"State changed from {old_state.value} to {new_state.value}"
    is_critical = severity == SeverityLevel.CRITICAL

    # Load all preferences + matching users in one query
    result = await session.execute(
        select(NotificationPreference, User)
        .join(User, (User.tenant_id == NotificationPreference.tenant_id) & (User.id == NotificationPreference.user_id))
        .where(NotificationPreference.tenant_id == uuid.UUID(tenant_id))
    )
    rows = result.all()

    for pref, user in rows:
        if not user.is_active:
            continue

        state_flag: bool = getattr(pref, pref_key, False)
        if not state_flag:
            continue

        # ── Email dispatch ────────────────────────────────────────────────────
        if pref.email_enabled:
            if pref.email_critical_only and not is_critical:
                pass  # skip non-critical when filter is on
            else:
                ok = await send_email_notification(
                    incident_id=incident_id,
                    tenant_id=tenant_id,
                    state=new_state,
                    severity=severity,
                    title=title,
                    recipient=user.email,
                    message=message,
                )
                log = NotificationDeliveryLog(
                    tenant_id=uuid.UUID(tenant_id),
                    id=uuid.uuid4(),
                    incident_id=uuid.UUID(incident_id),
                    user_id=user.id,
                    channel="email",
                    state_transition=f"{old_state.value}->{new_state.value}",
                    status="sent" if ok else "failed",
                    error_message=None if ok else "SES delivery failed",
                )
                session.add(log)

        # ── Slack dispatch ────────────────────────────────────────────────────
        if pref.slack_enabled and pref.slack_webhook_url:
            if pref.slack_critical_only and not is_critical:
                pass  # skip non-critical when filter is on
            else:
                ok = await _send_slack_to_url(
                    webhook_url=pref.slack_webhook_url,
                    incident_id=incident_id,
                    tenant_id=tenant_id,
                    state=new_state,
                    severity=severity,
                    title=title,
                    message=message,
                )
                log = NotificationDeliveryLog(
                    tenant_id=uuid.UUID(tenant_id),
                    id=uuid.uuid4(),
                    incident_id=uuid.UUID(incident_id),
                    user_id=user.id,
                    channel="slack",
                    state_transition=f"{old_state.value}->{new_state.value}",
                    status="sent" if ok else "failed",
                    error_message=None if ok else "Slack webhook delivery failed",
                )
                session.add(log)

    # Also fire the global Slack webhook (tenant-level) if configured
    await send_slack_notification(
        incident_id=incident_id,
        tenant_id=tenant_id,
        state=new_state,
        severity=severity,
        title=title,
        message=message,
    )


async def send_user_invitation_email(
    email: str,
    display_name: str,
    invitation_url: str,
) -> bool:
    """
    Send user invitation email with password setup link.

    Returns True if sent successfully, False otherwise.
    """
    if not _email_configured():
        logger.warning("email_not_configured", email=email)
        return False

    text_content = f"""
Welcome to AIREX, {display_name}!

You've been invited to join the AIREX incident management platform.

To get started, please set your password by clicking the link below:
{invitation_url}

This invitation link will expire in 7 days.

If you didn't expect this invitation, please contact your administrator.

Best regards,
AIREX Team
"""

    html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
  <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #6366f1;">Welcome to AIREX, {escape(display_name)}!</h2>
    <p>You've been invited to join the AIREX incident management platform.</p>
    <p>To get started, please set your password by clicking the button below:</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{escape(invitation_url, quote=True)}" style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
        Set Your Password
      </a>
    </div>
    <p style="font-size: 12px; color: #666;">
      This invitation link will expire in 7 days.<br>
      If you didn't expect this invitation, please contact your administrator.
    </p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
    <p style="font-size: 12px; color: #999; text-align: center;">
      Best regards,<br>
      AIREX Team
    </p>
  </div>
</body>
</html>
"""

    return await _send_email_via_ses(
        subject="Welcome to AIREX - Set Your Password",
        recipient=email,
        text_content=text_content,
        html_content=html_content,
        success_event="user_invitation_email_sent",
        error_event="user_invitation_email_error",
        log_context={
            "email": email,
            "display_name": display_name,
        },
    )


async def send_password_reset_email(
    email: str,
    display_name: str,
    reset_url: str,
) -> bool:
    """
    Send password reset email with reset link.

    Returns True if sent successfully, False otherwise.
    """
    if not _email_configured():
        logger.warning("email_not_configured", email=email)
        return False

    text_content = f"""
Hello {display_name},

You requested to reset your password for your AIREX account.

Click the link below to set a new password:
{reset_url}

This link will expire in 24 hours.

If you didn't request this, please ignore this email or contact your administrator.

Best regards,
AIREX Team
"""

    html_content = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
  <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    <h2 style="color: #6366f1;">Reset Your Password</h2>
    <p>Hello {escape(display_name)},</p>
    <p>You requested to reset your password for your AIREX account.</p>
    <p>Click the button below to set a new password:</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{escape(reset_url, quote=True)}" style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
        Reset Password
      </a>
    </div>
    <p style="font-size: 12px; color: #666;">
      This link will expire in 24 hours.<br>
      If you didn't request this, please ignore this email or contact your administrator.
    </p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
    <p style="font-size: 12px; color: #999; text-align: center;">
      Best regards,<br>
      AIREX Team
    </p>
  </div>
</body>
</html>
"""

    return await _send_email_via_ses(
        subject="AIREX - Reset Your Password",
        recipient=email,
        text_content=text_content,
        html_content=html_content,
        success_event="password_reset_email_sent",
        error_event="password_reset_email_error",
        log_context={
            "email": email,
            "display_name": display_name,
        },
    )
