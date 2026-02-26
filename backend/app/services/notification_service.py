"""
Notification service for Slack and Email.

Sends notifications on critical incident state changes.
"""

import json
from datetime import datetime, timezone

import aiohttp
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import IncidentState, SeverityLevel

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
    
    payload = {
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
                        incident_id=incident_id,
                        tenant_id=tenant_id,
                        state=state.value,
                    )
                    return True
                else:
                    logger.warning(
                        "slack_notification_failed",
                        incident_id=incident_id,
                        status=response.status,
                    )
                    return False
    except Exception as exc:
        logger.error(
            "slack_notification_error",
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
    if not all([
        settings.EMAIL_SMTP_HOST,
        settings.EMAIL_FROM,
    ]):
        return False
    
    try:
        import smtplib
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
{f'<p>{message}</p>' if message else ''}
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
            incident_id=incident_id,
            tenant_id=tenant_id,
            recipient=recipient,
            state=state.value,
        )
        return True
    except Exception as exc:
        logger.error(
            "email_notification_error",
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
    should_notify = (
        severity == SeverityLevel.CRITICAL
        or new_state in [
            IncidentState.AWAITING_APPROVAL,
            IncidentState.RESOLVED,
            IncidentState.FAILED_EXECUTION,
            IncidentState.FAILED_VERIFICATION,
        ]
    )
    
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
