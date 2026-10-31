"""User persistence repository.

Author: Karthikeya
Architectural layer: data access / repository.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import UserRole, UserStatus
from app.models.domain import User


class UserRepository:
    """Encapsulates durable relational queries for the User aggregate."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, user_id: UUID) -> User | None:
        """Find a single user by primary key UUID."""
        return self.session.scalar(select(User).where(User.id == user_id))

    def find_by_email(self, email: str) -> User | None:
        """Find a user by normalized unique email address."""
        return self.session.scalar(select(User).where(User.email == email))

    def save(self, user: User) -> User:
        """Persist or merge user record within active session."""
        self.session.add(user)
        return user

    def list_users(
        self,
        *,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[User]:
        """Return a paginated list of users with optional role and status filters."""
        stmt = select(User)
        if role is not None:
            stmt = stmt.where(User.role == role)
        if status is not None:
            stmt = stmt.where(User.status == status)
        stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def count_users(
        self,
        *,
        role: UserRole | None = None,
        status: UserStatus | None = None,
    ) -> int:
        """Count total matching users for pagination."""
        stmt = select(func.count(User.id))
        if role is not None:
            stmt = stmt.where(User.role == role)
        if status is not None:
            stmt = stmt.where(User.status == status)
        return self.session.scalar(stmt) or 0
