"""User entity-to-DTO and DTO-to-entity pure mappers.

Author: Karthikeya
Architectural layer: mapper.

Security Rules:
- Password hashes are NEVER mapped to response DTOs.
- Email is normalized during entity instantiation.
- Role is determined by trusted server assignment.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.enums import UserRole, UserStatus
from app.core.security import normalize_email
from app.models.domain import User
from app.schemas.auth import UserRegisterRequestDTO, UserResponseDTO


class UserMapper:
    """Stateless transformation utility between User entities and DTOs."""

    @staticmethod
    def to_response(entity: User) -> UserResponseDTO:
        """Convert a User persistence entity into a safe UserResponseDTO."""
        return UserResponseDTO(
            id=entity.id,
            email=entity.email,
            name=entity.name,
            role=entity.role,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            last_login_at=entity.last_login_at,
        )

    @staticmethod
    def to_entity(
        dto: UserRegisterRequestDTO,
        password_hash: str,
        role: UserRole = UserRole.OPERATOR,
        status: UserStatus = UserStatus.ACTIVE,
    ) -> User:
        """Instantiate a new detached User persistence entity from registration input."""
        return User(
            id=uuid4(),
            email=normalize_email(dto.email),
            name=dto.name.strip(),
            password_hash=password_hash,
            role=role,
            status=status,
            last_login_at=None,
        )
