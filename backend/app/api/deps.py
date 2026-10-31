"""Security dependencies, authentication context extraction, and RBAC enforcement.

Author: Karthikeya
Architectural layer: API controller dependencies.

Security Invariants:
- Extracts caller identity strictly from validated JWT claims.
- Denies by default: all role-restricted routes enforce explicit role verification.
- Enforces active account checks on every protected request.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import UserRole, UserStatus
from app.core.errors import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.models.domain import User
from app.repositories.users import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract, decode, and verify Bearer JWT token to retrieve authenticated user.

    Raises:
        UnauthorizedException: If token is missing, invalid, expired, or account is inactive.
    """
    if not token:
        raise UnauthorizedException("Authentication credentials missing or invalid.")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise UnauthorizedException("Invalid token type. Expected access token.")

    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedException("Invalid token claims: subject identifier missing.")

    try:
        user_id = UUID(sub)
    except ValueError:
        raise UnauthorizedException("Invalid token subject: not a valid UUID.")

    repo = UserRepository(db)
    user = repo.find_by_id(user_id)
    if user is None:
        raise UnauthorizedException("Authenticated user account no longer exists.")

    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedException(f"Account is {user.status.value}. Access denied.")

    return user


def require_roles(allowed_roles: list[UserRole]) -> Callable[[User], User]:
    """Dependency factory enforcing Role-Based Access Control (RBAC).

    Raises:
        ForbiddenException: If current user's role is not within the permitted list.
    """

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            role_names = [r.value for r in allowed_roles]
            raise ForbiddenException(
                f"Access forbidden: required role in {role_names}, but user possesses '{current_user.role.value}'."
            )
        return current_user

    return role_dependency


# Pre-configured RBAC dependencies matching Phase 1.3 RBAC Matrix
require_admin = require_roles([UserRole.ADMIN])
require_operator = require_roles([UserRole.ADMIN, UserRole.OPERATOR])
require_auditor = require_roles([UserRole.ADMIN, UserRole.AUDITOR])
require_authenticated = get_current_user
