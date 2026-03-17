"""Tests for authentication: security module, JWT, password hashing."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi import HTTPException

from app.api.dependencies import resolve_active_tenant_id
from airex_core.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        plain = "SecurePass123!"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestJWT:
    def test_create_and_decode_access_token(self):
        tid = uuid.uuid4()
        token = create_access_token(tid, "user@test.com", user_id=uuid.uuid4(), role="admin")
        data = decode_access_token(token)
        assert data.tenant_id == tid
        assert data.sub == "user@test.com"
        assert data.role == "admin"

    def test_create_and_decode_refresh_token(self):
        tid = uuid.uuid4()
        token = create_refresh_token(tid, "user@test.com")
        data = decode_refresh_token(token)
        assert data.tenant_id == tid
        assert data.sub == "user@test.com"

    def test_decode_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid token"):
            decode_access_token("garbage.token.here")

    def test_decode_access_as_refresh_raises(self):
        tid = uuid.uuid4()
        access = create_access_token(tid, "user@test.com")
        with pytest.raises(ValueError, match="Not a refresh token"):
            decode_refresh_token(access)

    def test_decode_refresh_as_access_succeeds(self):
        """Refresh tokens have type=refresh, but decode_access_token
        doesn't check type — this is intentional for flexibility."""
        tid = uuid.uuid4()
        refresh = create_refresh_token(tid, "user@test.com")
        data = decode_access_token(refresh)
        assert data.tenant_id == tid

    def test_token_data_exposes_user_email_alias(self):
        tid = uuid.uuid4()
        uid = uuid.uuid4()
        token = create_access_token(tid, "user@test.com", user_id=uid, role="org_admin")
        data = decode_access_token(token)
        assert data.user_email == "user@test.com"
        assert data.user_id == uid
        assert data.role == "org_admin"


class TestTenantAccessResolution:
    @pytest.mark.asyncio
    async def test_org_user_can_switch_to_any_tenant_in_org(self):
        home_tenant_id = uuid.uuid4()
        target_tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        session = AsyncMock()

        target_tenant = SimpleNamespace(
            id=target_tenant_id,
            organization_id=uuid.uuid4(),
            is_active=True,
        )
        tenant_lookup = MagicMock()
        tenant_lookup.scalar_one_or_none = MagicMock(return_value=target_tenant)

        org_membership_lookup = MagicMock()
        org_membership_lookup.scalar_one_or_none = MagicMock(
            return_value=SimpleNamespace(role="org_admin")
        )

        session.execute = AsyncMock(side_effect=[tenant_lookup, org_membership_lookup])

        token = decode_access_token(
            create_access_token(home_tenant_id, "org@example.com", user_id=user_id, role="org_admin")
        )

        resolved = await resolve_active_tenant_id(
            session=session,
            current_user=token,
            active_tenant_id=str(target_tenant_id),
        )

        assert resolved == target_tenant_id

    @pytest.mark.asyncio
    async def test_tenant_switch_rejects_unauthorized_target(self):
        home_tenant_id = uuid.uuid4()
        target_tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        session = AsyncMock()

        target_tenant = SimpleNamespace(
            id=target_tenant_id,
            organization_id=uuid.uuid4(),
            is_active=True,
        )
        tenant_lookup = MagicMock()
        tenant_lookup.scalar_one_or_none = MagicMock(return_value=target_tenant)

        org_membership_lookup = MagicMock()
        org_membership_lookup.scalar_one_or_none = MagicMock(return_value=None)

        tenant_membership_lookup = MagicMock()
        tenant_membership_lookup.scalar_one_or_none = MagicMock(return_value=None)

        session.execute = AsyncMock(
            side_effect=[tenant_lookup, org_membership_lookup, tenant_membership_lookup]
        )

        token = decode_access_token(
            create_access_token(
                home_tenant_id, "tenant@example.com", user_id=user_id, role="tenant_viewer"
            )
        )

        with pytest.raises(HTTPException) as exc:
            await resolve_active_tenant_id(
                session=session,
                current_user=token,
                active_tenant_id=str(target_tenant_id),
            )

        assert exc.value.status_code == 403


class TestRateLimiter:
    def test_rate_limit_module_imports(self):
        from airex_core.core.rate_limit import (
            webhook_rate_limit,
            approval_rate_limit,
            auth_rate_limit,
        )
        assert callable(webhook_rate_limit)
        assert callable(approval_rate_limit)
        assert callable(auth_rate_limit)


class TestRetryScheduler:
    def test_retry_scheduler_imports(self):
        from airex_core.core.retry_scheduler import retry_failed_incidents, RETRYABLE_STATES
        assert callable(retry_failed_incidents)
        assert len(RETRYABLE_STATES) == 2
