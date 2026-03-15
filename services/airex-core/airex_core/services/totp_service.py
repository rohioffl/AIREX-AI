"""
TOTP/MFA service for AIREX.

Provides secret generation, URI construction, code verification,
encryption-at-rest, and short-lived MFA challenge tokens.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from functools import lru_cache
from typing import Any

import pyotp
import structlog
from cryptography.fernet import Fernet

from airex_core.core.config import settings

logger = structlog.get_logger()

_ISSUER = "AIREX"
_CHALLENGE_TTL_SECONDS = 300  # 5 minutes
_TOTP_WINDOW = 1  # ±1 interval for clock skew tolerance


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    Return a cached Fernet instance for TOTP secret encryption.

    Key source priority:
      1. settings.TOTP_ENCRYPTION_KEY (dedicated 32-byte hex env var)
      2. PBKDF2-derived from settings.SECRET_KEY (fallback)
    """
    dedicated = getattr(settings, "TOTP_ENCRYPTION_KEY", None)
    if dedicated:
        raw_key = dedicated.encode("utf-8")[:32].ljust(32, b"\x00")
    else:
        # Derive 32 bytes via PBKDF2 — avoids null-padding weak keys
        raw_key = hashlib.pbkdf2_hmac(
            "sha256",
            settings.SECRET_KEY.encode("utf-8"),
            b"airex-totp-v1",
            iterations=100_000,
            dklen=32,
        )
    return Fernet(base64.urlsafe_b64encode(raw_key))


def generate_totp_secret() -> str:
    """Generate a random base32-encoded TOTP secret."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    """Return an otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=_ISSUER)


def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a TOTP code with ±1 window tolerance for clock skew.

    Returns False for empty, non-numeric, or invalid codes.
    """
    if not code or not code.strip().isdigit():
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=_TOTP_WINDOW)


def encrypt_secret(secret: str) -> str:
    """Encrypt a TOTP secret for storage at rest."""
    return _get_fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted: str) -> str:
    """Decrypt a stored TOTP secret."""
    return _get_fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")


def create_mfa_challenge_token(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """
    Create a short-lived signed token returned when MFA is required.

    The token encodes tenant_id, user_id, type=mfa_challenge, and expiry.
    Signed with HMAC-SHA256 keyed on SECRET_KEY to prevent forgery.
    """
    payload = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "type": "mfa_challenge",
        "exp": int(time.time()) + _CHALLENGE_TTL_SECONDS,
    }
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("utf-8").rstrip("=")

    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"{body}.{sig}"


def verify_mfa_challenge_token(token: str) -> dict[str, Any]:
    """
    Verify and decode an MFA challenge token.

    Raises ValueError if the token is invalid, tampered, or expired.
    """
    try:
        body, sig = token.rsplit(".", 1)
    except ValueError:
        raise ValueError("Invalid MFA challenge token format")

    expected_sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Invalid MFA challenge token signature")

    # Restore stripped base64 padding
    padding = 4 - len(body) % 4
    if padding != 4:
        body += "=" * padding

    try:
        payload = json.loads(base64.urlsafe_b64decode(body).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid MFA challenge token payload") from exc

    if payload.get("type") != "mfa_challenge":
        raise ValueError("Token is not an MFA challenge token")

    if int(time.time()) > payload["exp"]:
        raise ValueError("MFA challenge token has expired")

    return payload
