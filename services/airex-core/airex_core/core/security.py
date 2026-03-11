"""Security primitives for password hashing and JWT handling.

This module centralizes token serialization/deserialization and password
verification behavior for authentication flows.
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from jose.exceptions import ExpiredSignatureError
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from airex_core.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = structlog.get_logger(__name__)


# ── Schemas ──────────────────────────────────────────────────


class TokenData(BaseModel):
    tenant_id: uuid.UUID
    sub: str
    user_id: uuid.UUID | None = None
    role: str = "operator"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    tenant_id: uuid.UUID | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    role: str
    is_active: bool | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    invitation_token: str | None = None
    invitation_expires_at: datetime | None = None
    invitation_status: str | None = None  # "pending", "accepted", "expired"


# ── Password hashing ────────────────────────────────────────


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its hash."""
    return pwd_context.verify(plain, hashed)


def generate_invitation_token() -> str:
    """Generate a secure invitation token (URL-safe random string).
    
    Returns a token that can be used directly in URLs.
    The token is stored as-is in the database for lookup.
    """
    import secrets
    
    # Generate a secure random token (32 bytes = 43 chars base64)
    # Using URL-safe base64 encoding for use in URLs
    token = secrets.token_urlsafe(32)
    return token


# ── JWT ──────────────────────────────────────────────────────

REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(
    tenant_id: uuid.UUID,
    subject: str,
    user_id: uuid.UUID | None = None,
    role: str = "operator",
) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "tenant_id": str(tenant_id),
        "sub": subject,
        "exp": expire,
        "type": "access",
    }
    if user_id:
        payload["user_id"] = str(user_id)
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(tenant_id: uuid.UUID, subject: str) -> str:
    """Create a long-lived JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "tenant_id": str(tenant_id),
        "sub": subject,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    """Decode and validate an access JWT.

    Raises:
        ValueError: If the token cannot be decoded or contains invalid claims.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        tenant_id = uuid.UUID(payload["tenant_id"])
        subject: str = payload["sub"]
        user_id = uuid.UUID(payload["user_id"]) if "user_id" in payload else None
        role = payload.get("role", "operator")
        return TokenData(tenant_id=tenant_id, sub=subject, user_id=user_id, role=role)
    except ExpiredSignatureError as exc:
        logger.debug(
            "auth_access_token_expired",
            correlation_id=None,
        )
        raise ValueError(f"Invalid token: {exc}") from exc
    except (JWTError, KeyError, ValueError) as exc:
        logger.warning(
            "auth_access_token_decode_failed",
            correlation_id=None,
            error_type=type(exc).__name__,
        )
        raise ValueError(f"Invalid token: {exc}") from exc


def decode_refresh_token(token: str) -> TokenData:
    """Decode and validate a refresh JWT.

    Raises:
        ValueError: If token type/claims are invalid or decoding fails.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        tenant_id = uuid.UUID(payload["tenant_id"])
        subject: str = payload["sub"]
        return TokenData(tenant_id=tenant_id, sub=subject)
    except ExpiredSignatureError as exc:
        logger.debug(
            "auth_refresh_token_expired",
            correlation_id=None,
        )
        raise ValueError(f"Invalid refresh token: {exc}") from exc
    except (JWTError, KeyError, ValueError) as exc:
        logger.warning(
            "auth_refresh_token_decode_failed",
            correlation_id=None,
            error_type=type(exc).__name__,
        )
        raise ValueError(f"Invalid refresh token: {exc}") from exc
