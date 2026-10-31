"""Comprehensive automated test suite for Authentication, Authorization, RBAC, and User Management.

Author: Karthikeya
Architectural layer: test suite / security.

Covers:
- Registration, validation, and privilege escalation defense
- Password hashing (BCrypt), verification, and constant-time checks
- Login, generic error messages, and inactive account rejection
- JWT token issuance, claims, expiration, tampering, and refresh rotation
- Role-Based Access Control (RBAC): Operator vs Admin permissions
- Profile retrieval, display name updates, and password changes
"""

from datetime import timedelta
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import UserRole, UserStatus
from app.core.security import create_access_token, hash_password, verify_password
from app.main import create_app
from app.models.domain import User


@pytest.fixture
def auth_test_context():
    """Create isolated in-memory test database, session factory, and configured TestClient."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    app = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield {
        "client": client,
        "session_factory": session_factory,
        "engine": engine,
    }

    app.dependency_overrides.clear()


# ==============================================================================
# SECTION A: REGISTRATION TESTS
# ==============================================================================


def test_registration_success(auth_test_context) -> None:
    """Valid operator registration returns 201 and safe profile without password hash."""
    client = auth_test_context["client"]

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "Operator.One@Northstar.io",
            "password": "SecurePassword123!",
            "name": "Alex Morgan",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "operator.one@northstar.io"  # Normalized to lowercase
    assert data["name"] == "Alex Morgan"
    assert data["role"] == "ROLE_OPERATOR"
    assert data["status"] == "active"
    assert "password" not in data
    assert "password_hash" not in data


def test_registration_duplicate_email_rejected(auth_test_context) -> None:
    """Duplicate email registration must be rejected with HTTP 409 DUPLICATE_ENTITY."""
    client = auth_test_context["client"]

    payload = {
        "email": "duplicate@northstar.io",
        "password": "SecurePassword123!",
        "name": "Operator Dup",
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["error_code"] == "DUPLICATE_ENTITY"


def test_registration_weak_password_rejected(auth_test_context) -> None:
    """Passwords shorter than 8 characters must be rejected."""
    client = auth_test_context["client"]

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak@northstar.io",
            "password": "short",
            "name": "Weak User",
        },
    )
    assert response.status_code == 422  # Pydantic schema validation failure


def test_registration_prevents_privilege_escalation(auth_test_context) -> None:
    """Client attempting to register as ROLE_ADMIN must be rejected via extra='forbid'."""
    client = auth_test_context["client"]

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "hacker@evil.io",
            "password": "Password123!",
            "name": "Hacker",
            "role": "ROLE_ADMIN",  # Injected disallowed field
        },
    )
    assert response.status_code == 422
    assert "extra_forbidden" in str(response.json())


# ==============================================================================
# SECTION B: PASSWORD HASHING TESTS
# ==============================================================================


def test_password_hashing_and_verification() -> None:
    """BCrypt hash generation, constant-time verification, and salted uniqueness."""
    raw_password = "SuperSecretPassword2026!"
    hash1 = hash_password(raw_password)
    hash2 = hash_password(raw_password)

    # Hashes are different due to unique cryptographic salts
    assert hash1 != hash2
    assert hash1.startswith("$2b$") or hash1.startswith("$2a$")
    assert raw_password not in hash1

    # Verification works
    assert verify_password(raw_password, hash1) is True
    assert verify_password(raw_password, hash2) is True
    assert verify_password("WrongPassword123!", hash1) is False
    assert verify_password("", hash1) is False
    assert verify_password(raw_password, "invalid_hash_string") is False


# ==============================================================================
# SECTION C: LOGIN TESTS
# ==============================================================================


def test_login_success(auth_test_context) -> None:
    """Valid login credentials issue signed JWT access and refresh tokens."""
    client = auth_test_context["client"]

    # Register user first
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "login.test@northstar.io",
            "password": "MyLoginPassword123!",
            "name": "Login User",
        },
    )

    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "LOGIN.TEST@NORTHSTAR.IO",  # Case-insensitive
            "password": "MyLoginPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 3600
    assert data["user"]["email"] == "login.test@northstar.io"
    assert "password_hash" not in data["user"]


def test_login_invalid_password_returns_generic_error(auth_test_context) -> None:
    """Invalid password returns generic 401 without exposing account existence."""
    client = auth_test_context["client"]

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@northstar.io",
            "password": "CorrectPassword123!",
            "name": "User",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "user@northstar.io",
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error_code"] == "UNAUTHORIZED"
    assert data["message"] == "Invalid email or password."


def test_login_nonexistent_email_returns_identical_generic_error(auth_test_context) -> None:
    """Nonexistent user returns identical 401 to prevent username enumeration."""
    client = auth_test_context["client"]

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nonexistent@northstar.io",
            "password": "AnyPassword123!",
        },
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password."


def test_login_suspended_account_rejected(auth_test_context) -> None:
    """Suspended or deactivated accounts cannot authenticate."""
    client = auth_test_context["client"]
    session_factory = auth_test_context["session_factory"]

    # Register
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "suspended@northstar.io",
            "password": "Password123!",
            "name": "Suspended User",
        },
    ).json()

    # Manually suspend account in DB
    with session_factory() as session:
        user = session.get(User, UUID(reg["id"]))
        user.status = UserStatus.SUSPENDED
        session.commit()

    # Attempt login
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "suspended@northstar.io",
            "password": "Password123!",
        },
    )
    assert response.status_code == 401
    assert "suspended" in response.json()["message"]


# ==============================================================================
# SECTION D: TOKEN & REFRESH TESTS
# ==============================================================================


def test_token_refresh_lifecycle(auth_test_context) -> None:
    """Valid refresh token successfully issues new access and refresh tokens."""
    client = auth_test_context["client"]

    # Register & Login
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh@northstar.io",
            "password": "Password123!",
            "name": "Refresh User",
        },
    )
    login_data = client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@northstar.io", "password": "Password123!"},
    ).json()

    refresh_token = login_data["refresh_token"]

    # Request refreshed token
    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    new_data = response.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    assert new_data["access_token"] != login_data["access_token"]


def test_tampered_or_malformed_token_rejected(auth_test_context) -> None:
    """Tampered token signature or malformed payload returns HTTP 401."""
    client = auth_test_context["client"]

    # Tampered signature
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.tampered_signature"},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "UNAUTHORIZED"

    # Missing authorization header
    no_auth = client.get("/api/v1/auth/me")
    assert no_auth.status_code == 401


def test_expired_token_rejected(auth_test_context) -> None:
    """Expired JWT token returns HTTP 401 Expired."""
    client = auth_test_context["client"]
    session_factory = auth_test_context["session_factory"]

    # Register user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "expired@northstar.io",
            "password": "Password123!",
            "name": "Expired User",
        },
    ).json()

    # Generate token already expired in the past (-10 minutes)
    with session_factory() as session:
        user = session.get(User, UUID(reg["id"]))
        expired_token = create_access_token(
            user.id,
            user.email,
            user.role,
            expires_delta=timedelta(minutes=-10),
        )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["message"].lower()


# ==============================================================================
# SECTION E: AUTHORIZATION & RBAC TESTS
# ==============================================================================


def test_rbac_operator_vs_admin_permissions(auth_test_context) -> None:
    """Operators can access their profile but are strictly blocked from Admin user management."""
    client = auth_test_context["client"]
    session_factory = auth_test_context["session_factory"]

    # 1. Register operator
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "operator@northstar.io",
            "password": "Password123!",
            "name": "Operator User",
        },
    )
    op_login = client.post(
        "/api/v1/auth/login",
        json={"email": "operator@northstar.io", "password": "Password123!"},
    ).json()
    op_token = op_login["access_token"]

    # Operator accessing /api/v1/auth/me succeeds
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {op_token}"})
    assert me_resp.status_code == 200

    # Operator attempting to access admin-only /api/v1/users is rejected with 403 Forbidden
    admin_resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {op_token}"})
    assert admin_resp.status_code == 403
    assert admin_resp.json()["error_code"] == "FORBIDDEN"

    # 2. Register second user and elevate to ROLE_ADMIN via database
    admin_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@northstar.io",
            "password": "AdminPassword123!",
            "name": "Admin User",
        },
    ).json()

    with session_factory() as session:
        admin_entity = session.get(User, UUID(admin_reg["id"]))
        admin_entity.role = UserRole.ADMIN
        session.commit()

    # Admin logins and accesses /api/v1/users successfully
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@northstar.io", "password": "AdminPassword123!"},
    ).json()
    admin_token = admin_login["access_token"]

    list_resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp.status_code == 200
    users_list = list_resp.json()
    assert users_list["pagination"]["total"] == 2

    # Admin updates operator role to ROLE_AUDITOR
    role_change = client.patch(
        f"/api/v1/users/{op_login['user']['id']}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "ROLE_AUDITOR"},
    )
    assert role_change.status_code == 200
    assert role_change.json()["role"] == "ROLE_AUDITOR"


# ==============================================================================
# SECTION F: PROFILE & PASSWORD CHANGE TESTS
# ==============================================================================


def test_profile_update_and_password_change(auth_test_context) -> None:
    """Authenticated user can update display name and change password."""
    client = auth_test_context["client"]

    # Register & Login
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "profile.test@northstar.io",
            "password": "InitialPassword123!",
            "name": "Initial Name",
        },
    )
    login_data = client.post(
        "/api/v1/auth/login",
        json={"email": "profile.test@northstar.io", "password": "InitialPassword123!"},
    ).json()
    token = login_data["access_token"]

    # Update profile name
    patch_resp = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated Operator Name"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Operator Name"

    # Change password with wrong current password fails
    wrong_pwd = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "WrongCurrentPassword!",
            "new_password": "BrandNewPassword2026!",
        },
    )
    assert wrong_pwd.status_code == 401

    # Change password with correct current password succeeds
    success_pwd = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "InitialPassword123!",
            "new_password": "BrandNewPassword2026!",
        },
    )
    assert success_pwd.status_code == 200
    assert success_pwd.json()["success"] is True

    # Old password no longer works
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "profile.test@northstar.io", "password": "InitialPassword123!"},
    )
    assert old_login.status_code == 401

    # New password works
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "profile.test@northstar.io", "password": "BrandNewPassword2026!"},
    )
    assert new_login.status_code == 200
