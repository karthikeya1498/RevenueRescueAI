"""Authentication and User Management HTTP Controller.

Author: Karthikeya
Architectural layer: API controller / routing.

Endpoints:
- POST  /api/v1/auth/register        (Public operator registration)
- POST  /api/v1/auth/login           (Public credential login & token issuance)
- POST  /api/v1/auth/refresh         (Public token refresh)
- POST  /api/v1/auth/logout          (Authenticated session termination)
- GET   /api/v1/auth/me              (Authenticated profile retrieval)
- PATCH /api/v1/auth/me              (Authenticated display name update)
- POST  /api/v1/auth/change-password (Authenticated password change)
- GET   /api/v1/users                (ROLE_ADMIN only: list users)
- PATCH /api/v1/users/{id}/role      (ROLE_ADMIN only: change role)
- PATCH /api/v1/users/{id}/status    (ROLE_ADMIN only: change status)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_authenticated
from app.core.database import get_db
from app.core.enums import UserRole, UserStatus
from app.mappers.users import UserMapper
from app.models.domain import User
from app.schemas.auth import (
    ChangePasswordRequestDTO,
    RefreshTokenRequestDTO,
    TokenResponseDTO,
    UpdateProfileRequestDTO,
    UpdateUserRoleRequestDTO,
    UpdateUserStatusRequestDTO,
    UserLoginRequestDTO,
    UserRegisterRequestDTO,
    UserResponseDTO,
)
from app.schemas.common import PaginatedResponse, StatusResponseDTO
from app.services.auth_service import AuthService

router = APIRouter(tags=["authentication"])


@router.post(
    "/api/v1/auth/register",
    response_model=UserResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
)
def register_user(
    payload: UserRegisterRequestDTO,
    db: Session = Depends(get_db),
) -> UserResponseDTO:
    """Register a new user account with default operator role and hashed password."""
    service = AuthService(db)
    return service.register(payload)


@router.post(
    "/api/v1/auth/login",
    response_model=TokenResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and issue JWT tokens",
)
def login_user(
    payload: UserLoginRequestDTO,
    db: Session = Depends(get_db),
) -> TokenResponseDTO:
    """Verify credentials and issue signed JWT access and refresh tokens."""
    service = AuthService(db)
    return service.login(payload)


@router.post(
    "/api/v1/auth/refresh",
    response_model=TokenResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
)
def refresh_access_token(
    payload: RefreshTokenRequestDTO,
    db: Session = Depends(get_db),
) -> TokenResponseDTO:
    """Issue a renewed access token using a valid refresh token."""
    service = AuthService(db)
    return service.refresh_token(payload)


@router.post(
    "/api/v1/auth/logout",
    response_model=StatusResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Logout authenticated user",
)
def logout_user(
    current_user: User = Depends(require_authenticated),
) -> StatusResponseDTO:
    """Record user logout event and instruct client to discard credentials."""
    return StatusResponseDTO(
        success=True,
        message="Successfully logged out. Client token discarded.",
    )


@router.get(
    "/api/v1/auth/me",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
@router.get(
    "/api/v1/users/me",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile (Users path)",
)
def get_my_profile(
    current_user: User = Depends(require_authenticated),
) -> UserResponseDTO:
    """Retrieve profile details for the currently authenticated user."""
    return UserMapper.to_response(current_user)


@router.patch(
    "/api/v1/auth/me",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
)
@router.patch(
    "/api/v1/users/me",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile (Users path)",
)
def update_my_profile(
    payload: UpdateProfileRequestDTO,
    current_user: User = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> UserResponseDTO:
    """Update mutable profile details for the currently authenticated user."""
    service = AuthService(db)
    return service.update_profile(current_user.id, payload)


@router.post(
    "/api/v1/auth/change-password",
    response_model=StatusResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Change user password",
)
def change_password(
    payload: ChangePasswordRequestDTO,
    current_user: User = Depends(require_authenticated),
    db: Session = Depends(get_db),
) -> StatusResponseDTO:
    """Change account password after validating existing credentials."""
    service = AuthService(db)
    return service.change_password(current_user.id, payload)


# --- Administrator RBAC Endpoints ---


@router.get(
    "/api/v1/users",
    response_model=PaginatedResponse[UserResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="List all users (Admin only)",
)
def list_users(
    role: UserRole | None = None,
    user_status: UserStatus | None = Query(None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedResponse[UserResponseDTO]:
    """Retrieve paginated collection of users. Requires ROLE_ADMIN."""
    service = AuthService(db)
    return service.list_users(role=role, status=user_status, page=page, size=size)


@router.patch(
    "/api/v1/users/{user_id}/role",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Update user role (Admin only)",
)
def update_user_role(
    user_id: UUID,
    payload: UpdateUserRoleRequestDTO,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponseDTO:
    """Modify a user's RBAC role. Requires ROLE_ADMIN."""
    service = AuthService(db)
    return service.update_user_role(admin_user.id, user_id, payload)


@router.patch(
    "/api/v1/users/{user_id}/status",
    response_model=UserResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Update user account status (Admin only)",
)
def update_user_status(
    user_id: UUID,
    payload: UpdateUserStatusRequestDTO,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserResponseDTO:
    """Modify a user's account status. Requires ROLE_ADMIN."""
    service = AuthService(db)
    return service.update_user_status(admin_user.id, user_id, payload)
