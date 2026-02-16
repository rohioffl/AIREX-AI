"""JWT token creation/verification and password hashing."""

import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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


class UserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    role: str


# ── Password hashing ────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against its hash."""
    return pwd_context.verify(plain, hashed)


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
    """Decode and validate a JWT. Raises ValueError on failure."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        tenant_id = uuid.UUID(payload["tenant_id"])
        subject: str = payload["sub"]
        user_id = uuid.UUID(payload["user_id"]) if "user_id" in payload else None
        role = payload.get("role", "operator")
        return TokenData(tenant_id=tenant_id, sub=subject, user_id=user_id, role=role)
    except (JWTError, KeyError, ValueError) as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


def decode_refresh_token(token: str) -> TokenData:
    """Decode a refresh token. Raises ValueError on failure."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        tenant_id = uuid.UUID(payload["tenant_id"])
        subject: str = payload["sub"]
        return TokenData(tenant_id=tenant_id, sub=subject)
    except (JWTError, KeyError, ValueError) as exc:
        raise ValueError(f"Invalid refresh token: {exc}") from exc
