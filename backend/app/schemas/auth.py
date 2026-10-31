"""Authentication, authorization, and user management Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / contract.

Security Rules:
- Password hashes are NEVER exposed in any response schema.
- Password inputs enforce length bounds (minimum 8 characters).
- Client registration cannot specify privileged roles or account status.
- Extra unrecognized attributes are rejected via extra="forbid".
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import UserRole, UserStatus


class UserRegisterRequestDTO(BaseModel):
    """Client request schema for operator registration."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        ...,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Valid email address for operator identification",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password meeting minimum 8 characters requirement",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Full operator name or display identifier",
    )


class UserLoginRequestDTO(BaseModel):
    """Client request schema for authenticating with email and password."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(
        ...,
        max_length=320,
        description="Registered user email",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Account password",
    )


class RefreshTokenRequestDTO(BaseModel):
    """Client request schema for issuing a new access token via refresh token."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1, description="Valid JWT refresh token")


class ChangePasswordRequestDTO(BaseModel):
    """Client request schema for authenticated password modification."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=1, max_length=128, description="Existing password")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (minimum 8 characters)",
    )


class UpdateProfileRequestDTO(BaseModel):
    """Client request schema for updating own profile information."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200, description="Updated display name")


class UpdateUserRoleRequestDTO(BaseModel):
    """Admin-only request schema for modifying a user's RBAC role."""

    model_config = ConfigDict(extra="forbid")

    role: UserRole = Field(..., description="Target role (ROLE_ADMIN, ROLE_OPERATOR, ROLE_AUDITOR, ROLE_INGESTOR)")


class UpdateUserStatusRequestDTO(BaseModel):
    """Admin-only request schema for activating, suspending, or deactivating an account."""

    model_config = ConfigDict(extra="forbid")

    status: UserStatus = Field(..., description="Target status (active, suspended, inactive)")


class UserResponseDTO(BaseModel):
    """Safe user profile response representation (never returns password hashes)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique internal user UUID")
    email: str = Field(..., description="Normalized user email")
    name: str = Field(..., description="User full name")
    role: UserRole = Field(..., description="Assigned RBAC role")
    status: UserStatus = Field(..., description="Current account status")
    created_at: datetime = Field(..., description="Account creation UTC timestamp")
    updated_at: datetime = Field(..., description="Last account update UTC timestamp")
    last_login_at: datetime | None = Field(None, description="Last successful login UTC timestamp")


class TokenResponseDTO(BaseModel):
    """Authentication response payload containing access and refresh tokens."""

    access_token: str = Field(..., description="Bearer JWT access token for API authorization")
    refresh_token: str = Field(..., description="Bearer JWT refresh token for session continuation")
    token_type: str = Field(default="Bearer", description="Token authorization type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    user: UserResponseDTO = Field(..., description="Authenticated user profile")
