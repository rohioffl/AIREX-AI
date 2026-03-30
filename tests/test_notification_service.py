from unittest.mock import MagicMock

import pytest

from airex_core.models.enums import IncidentState, SeverityLevel
from airex_core.services import notification_service


@pytest.mark.asyncio
async def test_send_email_notification_uses_aws_ses(monkeypatch):
    ses_client = MagicMock()
    boto_client = MagicMock(return_value=ses_client)

    monkeypatch.setattr(notification_service.boto3, "client", boto_client)
    monkeypatch.setattr(notification_service.settings, "AWS_REGION", "ap-south-1")
    monkeypatch.setattr(notification_service.settings, "AWS_SES_REGION", "")
    monkeypatch.setattr(notification_service.settings, "EMAIL_FROM", "alerts@example.com")

    ok = await notification_service.send_email_notification(
        incident_id="incident-123",
        tenant_id="tenant-123",
        state=IncidentState.RESOLVED,
        severity=SeverityLevel.HIGH,
        title="CPU <spike>",
        recipient="operator@example.com",
        message="Investigate <b>now</b>",
    )

    assert ok is True
    boto_client.assert_called_once_with("ses", region_name="ap-south-1")

    payload = ses_client.send_email.call_args.kwargs
    assert payload["Source"] == "alerts@example.com"
    assert payload["Destination"] == {"ToAddresses": ["operator@example.com"]}
    assert payload["Message"]["Subject"]["Data"] == "[AIREX] HIGH: CPU <spike>"
    assert payload["Message"]["Body"]["Text"]["Data"].startswith("\nIncident incident-123")
    assert "&lt;b&gt;now&lt;/b&gt;" in payload["Message"]["Body"]["Html"]["Data"]
    assert "CPU &lt;spike&gt;" in payload["Message"]["Body"]["Html"]["Data"]


@pytest.mark.asyncio
async def test_send_user_invitation_email_uses_aws_ses(monkeypatch):
    ses_client = MagicMock()
    boto_client = MagicMock(return_value=ses_client)

    monkeypatch.setattr(notification_service.boto3, "client", boto_client)
    monkeypatch.setattr(notification_service.settings, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(notification_service.settings, "AWS_SES_REGION", "ap-south-1")
    monkeypatch.setattr(notification_service.settings, "EMAIL_FROM", "noreply@example.com")

    ok = await notification_service.send_user_invitation_email(
        email="new.user@example.com",
        display_name="New <User>",
        invitation_url="https://app.example.com/invite?token=abc&next=/home",
    )

    assert ok is True
    boto_client.assert_called_once_with("ses", region_name="ap-south-1")
    payload = ses_client.send_email.call_args.kwargs
    assert payload["Message"]["Subject"]["Data"] == "Welcome to AIREX - Set Your Password"
    assert "New &lt;User&gt;" in payload["Message"]["Body"]["Html"]["Data"]
    assert "token=abc&amp;next=/home" in payload["Message"]["Body"]["Html"]["Data"]


@pytest.mark.asyncio
async def test_send_password_reset_email_returns_false_when_email_not_configured(monkeypatch):
    boto_client = MagicMock()

    monkeypatch.setattr(notification_service.boto3, "client", boto_client)
    monkeypatch.setattr(notification_service.settings, "EMAIL_FROM", "")

    ok = await notification_service.send_password_reset_email(
        email="user@example.com",
        display_name="User",
        reset_url="https://app.example.com/reset",
    )

    assert ok is False
    boto_client.assert_not_called()
