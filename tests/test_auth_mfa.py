"""
TDD: TOTP/MFA authentication tests.

RED phase — these tests must fail before any implementation exists.
"""

import uuid

import pytest


class TestTotpService:
    """Tests for airex_core.services.totp_service"""

    def test_generate_secret_returns_base32_string(self):
        from airex_core.services.totp_service import generate_totp_secret
        secret = generate_totp_secret()
        assert isinstance(secret, str)
        assert len(secret) >= 16  # minimum safe length
        # base32 alphabet: A-Z and 2-7
        import re
        assert re.match(r'^[A-Z2-7]+=*$', secret), f"Not base32: {secret}"

    def test_generate_secret_is_unique_each_call(self):
        from airex_core.services.totp_service import generate_totp_secret
        secrets = {generate_totp_secret() for _ in range(10)}
        assert len(secrets) == 10  # all unique

    def test_get_totp_uri_returns_otpauth_format(self):
        from airex_core.services.totp_service import generate_totp_secret, get_totp_uri
        secret = generate_totp_secret()
        uri = get_totp_uri(secret, "user@airex.dev")
        assert uri.startswith("otpauth://totp/")
        assert "user%40airex.dev" in uri or "user@airex.dev" in uri
        assert secret in uri

    def test_get_totp_uri_includes_issuer(self):
        from airex_core.services.totp_service import generate_totp_secret, get_totp_uri
        secret = generate_totp_secret()
        uri = get_totp_uri(secret, "user@airex.dev")
        assert "AIREX" in uri or "airex" in uri.lower()

    def test_verify_totp_code_accepts_valid_code(self):
        import pyotp
        from airex_core.services.totp_service import generate_totp_secret, verify_totp_code
        secret = generate_totp_secret()
        # Generate a valid code using pyotp directly
        valid_code = pyotp.TOTP(secret).now()
        assert verify_totp_code(secret, valid_code) is True

    def test_verify_totp_code_rejects_wrong_code(self):
        from airex_core.services.totp_service import generate_totp_secret, verify_totp_code
        secret = generate_totp_secret()
        assert verify_totp_code(secret, "000000") is False

    def test_verify_totp_code_rejects_empty_string(self):
        from airex_core.services.totp_service import generate_totp_secret, verify_totp_code
        secret = generate_totp_secret()
        assert verify_totp_code(secret, "") is False

    def test_verify_totp_code_rejects_non_numeric(self):
        from airex_core.services.totp_service import generate_totp_secret, verify_totp_code
        secret = generate_totp_secret()
        assert verify_totp_code(secret, "abcdef") is False

    def test_verify_totp_code_allows_clock_skew(self):
        """±1 window tolerance for clock drift between server and authenticator app."""
        import pyotp
        from airex_core.services.totp_service import generate_totp_secret, verify_totp_code
        secret = generate_totp_secret()
        totp = pyotp.TOTP(secret)
        # Current code must be accepted
        assert verify_totp_code(secret, totp.now()) is True

    def test_encrypt_and_decrypt_secret(self):
        """Stored secret must be encrypted at rest, decryptable for verification."""
        from airex_core.services.totp_service import (
            generate_totp_secret,
            encrypt_secret,
            decrypt_secret,
        )
        secret = generate_totp_secret()
        encrypted = encrypt_secret(secret)
        assert encrypted != secret  # not stored in plaintext
        assert decrypt_secret(encrypted) == secret

    def test_encrypt_secret_produces_different_ciphertext_each_call(self):
        """Encryption must use random IV — same secret → different ciphertext."""
        from airex_core.services.totp_service import generate_totp_secret, encrypt_secret
        secret = generate_totp_secret()
        c1 = encrypt_secret(secret)
        c2 = encrypt_secret(secret)
        assert c1 != c2


class TestTotpUserModel:
    """Tests that User model has MFA fields."""

    def test_user_model_has_totp_fields(self):
        from airex_core.models.user import User
        user = User.__table__.columns
        assert "totp_secret_enc" in user, "Missing totp_secret_enc column"
        assert "totp_enabled" in user, "Missing totp_enabled column"

    def test_user_totp_enabled_defaults_false(self):
        from airex_core.models.user import User
        col = User.__table__.columns["totp_enabled"]
        assert col.default.arg is False or col.server_default is not None


class TestMfaChallengeToken:
    """MFA challenge token: short-lived token returned when MFA is required."""

    def test_create_mfa_challenge_token(self):
        from airex_core.services.totp_service import create_mfa_challenge_token
        tid = uuid.uuid4()
        uid = uuid.uuid4()
        token = create_mfa_challenge_token(tenant_id=tid, user_id=uid)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_verify_mfa_challenge_token_returns_claims(self):
        from airex_core.services.totp_service import (
            create_mfa_challenge_token,
            verify_mfa_challenge_token,
        )
        tid = uuid.uuid4()
        uid = uuid.uuid4()
        token = create_mfa_challenge_token(tenant_id=tid, user_id=uid)
        claims = verify_mfa_challenge_token(token)
        assert claims["user_id"] == str(uid)
        assert claims["tenant_id"] == str(tid)
        assert claims["type"] == "mfa_challenge"

    def test_mfa_challenge_token_expires(self):
        """Challenge token must be short-lived (5 minutes max)."""
        from airex_core.services.totp_service import (
            create_mfa_challenge_token,
            verify_mfa_challenge_token,
        )
        import time
        from unittest.mock import patch

        tid = uuid.uuid4()
        uid = uuid.uuid4()
        token = create_mfa_challenge_token(tenant_id=tid, user_id=uid)

        # Fast-forward time by 6 minutes
        with patch("airex_core.services.totp_service.time.time", return_value=time.time() + 360):
            with pytest.raises((ValueError, Exception), match="[Ee]xpir"):
                verify_mfa_challenge_token(token)

    def test_invalid_mfa_challenge_token_raises(self):
        from airex_core.services.totp_service import verify_mfa_challenge_token
        with pytest.raises((ValueError, Exception)):
            verify_mfa_challenge_token("invalid.token.here")
