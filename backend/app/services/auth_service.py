"""Authentication and user management application service.

Author: Karthikeya
Architectural layer: application service.

Responsibilities:
- Coordinates user registration, login, token refresh, and profile management.
- Enforces strict server-side role assignment and status verification.
- Enforces generic error messages on authentication failure to prevent user enumeration.
- Employs BCrypt hashing and cryptographic JWT generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import UserRole, UserStatus
from app.core.errors import (
    DuplicateEntityException,
    EntityNotFoundException,
    MalformedRequestException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    normalize_email,
    verify_password,
)
from app.mappers.users import UserMapper
from app.repositories.users import UserRepository
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
from app.schemas.common import PaginatedResponse, PaginationMetadata, StatusResponseDTO

logger = logging.getLogger("revenuerescue.auth")


class AuthService:
    """Application service for secure authentication, token lifecycle, and user profile management."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    def register(
        self,
        dto: UserRegisterRequestDTO,
        default_role: UserRole = UserRole.OPERATOR,
    ) -> UserResponseDTO:
        """Register a new user account with secure password hashing and default role assignment."""
        clean_email = normalize_email(dto.email)
        existing = self.user_repo.find_by_email(clean_email)
        if existing is not None:
            raise DuplicateEntityException("User", clean_email)

        # Enforce server-side password length policy
        settings = get_settings()
        if len(dto.password) < settings.password_min_length:
            raise MalformedRequestException(
                f"Password must be at least {settings.password_min_length} characters.",
                field="password",
            )

        pwd_hash = hash_password(dto.password)
        user = UserMapper.to_entity(dto, pwd_hash, role=default_role, status=UserStatus.ACTIVE)
        self.user_repo.save(user)
        self.session.commit()

        logger.info("Security audit: User registered successfully (email=%s, role=%s)", clean_email, default_role)
        return UserMapper.to_response(user)

    def login(self, dto: UserLoginRequestDTO) -> TokenResponseDTO:
        """Authenticate user credentials and issue short-lived JWT access and refresh tokens.

        Security: Generic error messages prevent account enumeration.
        """
        clean_email = normalize_email(dto.email)
        user = self.user_repo.find_by_email(clean_email)

        # Constant-time comparison or dummy check to prevent timing attack enumeration
        if user is None or not verify_password(dto.password, user.password_hash):
            logger.warning("Security audit: Failed login attempt for identifier '%s'", clean_email)
            raise UnauthorizedException("Invalid email or password.")

        # Account status check
        if user.status != UserStatus.ACTIVE:
            logger.warning("Security audit: Inactive account login attempted for '%s' (status=%s)", clean_email, user.status)
            raise UnauthorizedException("Account is suspended or deactivated. Contact your administrator.")

        # Update last login time
        user.last_login_at = datetime.now(timezone.utc)
        self.session.commit()

        settings = get_settings()
        access_token = create_access_token(user.id, user.email, user.role)
        refresh_token = create_refresh_token(user.id)
        expires_in = settings.jwt_access_token_expire_minutes * 60

        logger.info("Security audit: Successful authentication for user_id=%s, role=%s", user.id, user.role)
        return TokenResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=expires_in,
            user=UserMapper.to_response(user),
        )

    def refresh_token(self, dto: RefreshTokenRequestDTO) -> TokenResponseDTO:
        """Issue a new access token using a valid, cryptographically verified refresh token."""
        payload = decode_token(dto.refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid token type. Expected refresh token.")

        sub = payload.get("sub")
        if not sub:
            raise UnauthorizedException("Malformed token claims. Subject missing.")

        try:
            user_id = UUID(sub)
        except ValueError:
            raise UnauthorizedException("Malformed token subject identifier.")

        user = self.user_repo.find_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise UnauthorizedException("User account associated with token is not active.")

        settings = get_settings()
        new_access_token = create_access_token(user.id, user.email, user.role)
        new_refresh_token = create_refresh_token(user.id)
        expires_in = settings.jwt_access_token_expire_minutes * 60

        return TokenResponseDTO(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=expires_in,
            user=UserMapper.to_response(user),
        )

    def get_profile(self, user_id: UUID) -> UserResponseDTO:
        """Retrieve user profile for authenticated user ID."""
        user = self.user_repo.find_by_id(user_id)
        if user is None:
            raise EntityNotFoundException("User", str(user_id))
        return UserMapper.to_response(user)

    def update_profile(self, user_id: UUID, dto: UpdateProfileRequestDTO) -> UserResponseDTO:
        """Update mutable display name on user's own profile."""
        user = self.user_repo.find_by_id(user_id)
        if user is None:
            raise EntityNotFoundException("User", str(user_id))

        user.name = dto.name.strip()
        self.session.commit()
        return UserMapper.to_response(user)

    def change_password(self, user_id: UUID, dto: ChangePasswordRequestDTO) -> StatusResponseDTO:
        """Safely modify an account password after verifying current credentials."""
        user = self.user_repo.find_by_id(user_id)
        if user is None:
            raise EntityNotFoundException("User", str(user_id))

        if not verify_password(dto.current_password, user.password_hash):
            logger.warning("Security audit: Failed password change attempt for user_id=%s", user_id)
            raise UnauthorizedException("Current password is incorrect.")

        settings = get_settings()
        if len(dto.new_password) < settings.password_min_length:
            raise MalformedRequestException(
                f"New password must be at least {settings.password_min_length} characters.",
                field="new_password",
            )

        user.password_hash = hash_password(dto.new_password)
        self.session.commit()

        logger.info("Security audit: Password successfully changed for user_id=%s", user_id)
        return StatusResponseDTO(success=True, message="Password successfully changed.")

    def list_users(
        self,
        *,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[UserResponseDTO]:
        """Admin operation: Retrieve paginated list of system users."""
        offset = (page - 1) * size
        total = self.user_repo.count_users(role=role, status=status)
        entities = self.user_repo.list_users(role=role, status=status, limit=size, offset=offset)
        items = [UserMapper.to_response(u) for u in entities]

        total_pages = math.ceil(total / size) if total > 0 else 0
        has_more = page < total_pages

        return PaginatedResponse(
            items=items,
            pagination=PaginationMetadata(
                total=total,
                page=page,
                size=size,
                pages=total_pages,
                has_more=has_more,
            ),
        )

    def update_user_role(
        self,
        admin_user_id: UUID,
        target_user_id: UUID,
        dto: UpdateUserRoleRequestDTO,
    ) -> UserResponseDTO:
        """Admin operation: Modify a user's RBAC role."""
        target = self.user_repo.find_by_id(target_user_id)
        if target is None:
            raise EntityNotFoundException("User", str(target_user_id))

        old_role = target.role
        target.role = dto.role
        self.session.commit()

        logger.info(
            "Security audit: Role changed for user_id=%s from %s to %s by admin_id=%s",
            target_user_id,
            old_role,
            dto.role,
            admin_user_id,
        )
        return UserMapper.to_response(target)

    def update_user_status(
        self,
        admin_user_id: UUID,
        target_user_id: UUID,
        dto: UpdateUserStatusRequestDTO,
    ) -> UserResponseDTO:
        """Admin operation: Activate, suspend, or deactivate a user account."""
        target = self.user_repo.find_by_id(target_user_id)
        if target is None:
            raise EntityNotFoundException("User", str(target_user_id))

        old_status = target.status
        target.status = dto.status
        self.session.commit()

        logger.info(
            "Security audit: Status changed for user_id=%s from %s to %s by admin_id=%s",
            target_user_id,
            old_status,
            dto.status,
            admin_user_id,
        )
        return UserMapper.to_response(target)
