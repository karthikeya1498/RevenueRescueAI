"""Core cryptographic security, password hashing, and JWT token management.

Author: Karthikeya
Architectural layer: core security infrastructure.

Security Rules:
- Plaintext passwords are NEVER stored, logged, or serialized.
- Strong one-way password hashing via BCrypt with cryptographic salt.
- JWT tokens signed with HMAC-SHA256 containing strict expiry and role claims.
- Constant-time password verification prevents timing side-channel attacks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.errors import UnauthorizedException


def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and stripped whitespace."""
    return email.strip().lower()


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using BCrypt with an automatically generated salt."""
    if not plain_password:
        raise ValueError("Password cannot be empty.")
    # BCrypt takes bytes and returns bytes
    pwd_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored BCrypt hash in constant time."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: UUID,
    email: str,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token containing identity and role claims."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role.value if hasattr(role, "value") else str(role),
        "type": "access",
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT refresh token for session continuation."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and cryptographically verify a JWT token.

    Raises:
        UnauthorizedException: If token is expired, invalid, or malformed.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except ExpiredSignatureError:
        raise UnauthorizedException("Authentication token has expired. Please log in again.")
    except JWTError:
        raise UnauthorizedException("Authentication token is invalid or malformed.")
