"""Tests for Google sign-in auth route — existing-users-only policy."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from fastapi import HTTPException

from app.api.routes import auth
from airex_core.core.config import settings
from airex_core.core.security import GoogleLoginRequest
from airex_core.models.user import User


def _mock_session(user: User | None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=user)
    session.execute = AsyncMock(return_value=result)
    return session


def _make_user(email: str, is_active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(settings.DEV_TENANT_ID),
        email=email,
        hashed_password="x",
        display_name="Test User",
        role="operator",
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_google_login_succeeds_for_existing_user(monkeypatch):
    user = _make_user("existing@example.com")
    session = _mock_session(user)

    monkeypatch.setattr(
        auth,
        "_verify_google_id_token",
        lambda _: {"email": "existing@example.com", "email_verified": True},
    )

    response = await auth.google_login(GoogleLoginRequest(id_token="token"), session)

    assert response.access_token
    assert response.refresh_token
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_google_login_rejects_unknown_email(monkeypatch):
    session = _mock_session(None)

    monkeypatch.setattr(
        auth,
        "_verify_google_id_token",
        lambda _: {"email": "unknown@example.com", "email_verified": True},
    )

    with pytest.raises(HTTPException) as exc:
        await auth.google_login(GoogleLoginRequest(id_token="token"), session)

    assert exc.value.status_code == 401
    assert "administrator" in exc.value.detail


@pytest.mark.asyncio
async def test_google_login_rejects_unverified_email(monkeypatch):
    session = _mock_session(None)

    monkeypatch.setattr(
        auth,
        "_verify_google_id_token",
        lambda _: {"email": "unverified@example.com", "email_verified": False},
    )

    with pytest.raises(HTTPException) as exc:
        await auth.google_login(GoogleLoginRequest(id_token="token"), session)

    assert exc.value.status_code == 401
    assert "verified" in exc.value.detail


@pytest.mark.asyncio
async def test_google_login_rejects_disabled_account(monkeypatch):
    user = _make_user("disabled@example.com", is_active=False)
    session = _mock_session(user)

    monkeypatch.setattr(
        auth,
        "_verify_google_id_token",
        lambda _: {"email": "disabled@example.com", "email_verified": True},
    )

    with pytest.raises(HTTPException) as exc:
        await auth.google_login(GoogleLoginRequest(id_token="token"), session)

    assert exc.value.status_code == 403
    assert "disabled" in exc.value.detail


def test_verify_google_id_token_requires_client_id(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")

    with pytest.raises(HTTPException) as exc:
        auth._verify_google_id_token("token")

    assert exc.value.status_code == 503
    assert "not configured" in exc.value.detail
