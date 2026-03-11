"""
Notification service for Slack and Email.

Sends notifications on critical incident state changes.
"""

from datetime import datetime, timezone
import smtplib
from typing import Any

import aiohttp
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from airex_core.core.config import settings
from airex_core.models.enums import IncidentState, SeverityLevel

logger = structlog.get_logger()


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
    Send email notification via SMTP.

    Returns True if sent successfully, False otherwise.
    """
    correlation_id = incident_id

    if not all(
        [
            settings.EMAIL_SMTP_HOST,
            settings.EMAIL_FROM,
        ]
    ):
        return False

    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AIREX] {severity.value}: {title}"
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = recipient

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
<h2>Incident {incident_id} - {state.value}</h2>
<p><strong>Severity:</strong> {severity.value}</p>
<p><strong>Title:</strong> {title}</p>
{f"<p>{message}</p>" if message else ""}
<p><a href="/incidents/{incident_id}">View Details</a></p>
</body>
</html>
"""

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        # Use async SMTP if available, otherwise sync
        # For production, use aiosmtplib or send via background task
        with smtplib.SMTP(
            settings.EMAIL_SMTP_HOST,
            settings.EMAIL_SMTP_PORT,
        ) as server:
            if settings.EMAIL_SMTP_USER and settings.EMAIL_SMTP_PASSWORD:
                server.starttls()
                server.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(
            "email_notification_sent",
            correlation_id=correlation_id,
            incident_id=incident_id,
            tenant_id=tenant_id,
            recipient=recipient,
            state=state.value,
        )
        return True
    except (OSError, smtplib.SMTPException) as exc:
        logger.error(
            "email_notification_error",
            correlation_id=correlation_id,
            incident_id=incident_id,
            error=str(exc),
        )
        return False


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
    Send notifications for critical state changes.

    Only notifies on:
    - CRITICAL severity incidents
    - State changes to AWAITING_APPROVAL, RESOLVED, or FAILED states
    """
    # Only notify for critical incidents or important state changes
    should_notify = severity == SeverityLevel.CRITICAL or new_state in [
        IncidentState.AWAITING_APPROVAL,
        IncidentState.RESOLVED,
        IncidentState.FAILED_EXECUTION,
        IncidentState.FAILED_VERIFICATION,
    ]

    if not should_notify:
        return

    message = f"State changed from {old_state.value} to {new_state.value}"

    # Send Slack notification
    await send_slack_notification(
        incident_id=incident_id,
        tenant_id=tenant_id,
        state=new_state,
        severity=severity,
        title=title,
        message=message,
    )

    # Email notifications would require tenant/user email lookup
    # For now, skip email unless explicitly configured per tenant
    _ = session


async def send_user_invitation_email(
    email: str,
    display_name: str,
    invitation_url: str,
) -> bool:
    """
    Send user invitation email with password setup link.

    Returns True if sent successfully, False otherwise.
    """
    if not all(
        [
            settings.EMAIL_SMTP_HOST,
            settings.EMAIL_FROM,
        ]
    ):
        logger.warning("email_not_configured", email=email)
        return False

    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Welcome to AIREX - Set Your Password"
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = email

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
    <h2 style="color: #6366f1;">Welcome to AIREX, {display_name}!</h2>
    <p>You've been invited to join the AIREX incident management platform.</p>
    <p>To get started, please set your password by clicking the button below:</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{invitation_url}" style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
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

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        # Use async SMTP if available, otherwise sync
        with smtplib.SMTP(
            settings.EMAIL_SMTP_HOST,
            settings.EMAIL_SMTP_PORT,
        ) as server:
            if settings.EMAIL_SMTP_USER and settings.EMAIL_SMTP_PASSWORD:
                server.starttls()
                server.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(
            "user_invitation_email_sent",
            email=email,
            display_name=display_name,
        )
        return True
    except (OSError, smtplib.SMTPException) as exc:
        logger.error(
            "user_invitation_email_error",
            email=email,
            error=str(exc),
        )
        return False


async def send_password_reset_email(
    email: str,
    display_name: str,
    reset_url: str,
) -> bool:
    """
    Send password reset email with reset link.

    Returns True if sent successfully, False otherwise.
    """
    if not all(
        [
            settings.EMAIL_SMTP_HOST,
            settings.EMAIL_FROM,
        ]
    ):
        logger.warning("email_not_configured", email=email)
        return False

    try:
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "AIREX - Reset Your Password"
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = email

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
    <p>Hello {display_name},</p>
    <p>You requested to reset your password for your AIREX account.</p>
    <p>Click the button below to set a new password:</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{reset_url}" style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
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

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(
            settings.EMAIL_SMTP_HOST,
            settings.EMAIL_SMTP_PORT,
        ) as server:
            if settings.EMAIL_SMTP_USER and settings.EMAIL_SMTP_PASSWORD:
                server.starttls()
                server.login(settings.EMAIL_SMTP_USER, settings.EMAIL_SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(
            "password_reset_email_sent",
            email=email,
            display_name=display_name,
        )
        return True
    except (OSError, smtplib.SMTPException) as exc:
        logger.error(
            "password_reset_email_error",
            email=email,
            error=str(exc),
        )
        return False
