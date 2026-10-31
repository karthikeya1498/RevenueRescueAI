# Authentication API Reference — RevenueRescueAI

## 1. Overview

This document provides complete, contract-accurate request and response specifications for the authentication, user profile, and user management endpoints in RevenueRescueAI.

All routes are mounted under `/api/v1`.

---

## 2. Authentication Endpoints (`/api/v1/auth`)

### 2.1 User Registration
- **Endpoint:** `POST /api/v1/auth/register`
- **Security:** Public (No credentials required)
- **Description:** Registers a new operator account. The client-provided role is ignored; the server unconditionally assigns `ROLE_OPERATOR` and `ACTIVE`.

#### Request Body:
```json
{
  "name": "Alex Mercer",
  "email": "alex.mercer@company.com",
  "password": "CorrectHorseBatteryStaple123"
}
```

#### Response (`HTTP 201 Created`):
```json
{
  "id": "c1f7a0b5-77cf-4db0-a3e9-7ddca1f04b12",
  "name": "Alex Mercer",
  "email": "alex.mercer@company.com",
  "role": "ROLE_OPERATOR",
  "status": "ACTIVE",
  "created_at": "2026-10-31T10:45:00Z",
  "updated_at": "2026-10-31T10:45:00Z",
  "last_login_at": null
}
```

#### Error Responses:
- `HTTP 409 Conflict`: Email already exists.
- `HTTP 422 Unprocessable Entity`: Password < 8 characters or malformed email.

---

### 2.2 User Login
- **Endpoint:** `POST /api/v1/auth/login`
- **Security:** Public
- **Description:** Authenticates credentials and returns a dual JWT token pair.

#### Request Body:
```json
{
  "email": "alex.mercer@company.com",
  "password": "CorrectHorseBatteryStaple123"
}
```

#### Response (`HTTP 200 OK`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Error Responses:
- `HTTP 401 Unauthorized`: `"Invalid credentials"` (Generic message preventing username enumeration).
- `HTTP 403 Forbidden`: Account is suspended or inactive.

---

### 2.3 Token Refresh
- **Endpoint:** `POST /api/v1/auth/refresh`
- **Security:** Public
- **Description:** Exchanges a valid refresh token for a newly issued access token and refreshed refresh token (token rotation).

#### Request Body:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Response (`HTTP 200 OK`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 2.4 User Logout
- **Endpoint:** `POST /api/v1/auth/logout`
- **Security:** Public
- **Description:** Acknowledges client-side token discard.

#### Response (`HTTP 200 OK`):
```json
{
  "message": "Logged out successfully"
}
```

---

### 2.5 Get Current User Profile
- **Endpoint:** `GET /api/v1/auth/me`
- **Security:** Authenticated (`Authorization: Bearer <access_token>`)
- **Description:** Returns profile data for the authenticated actor.

#### Response (`HTTP 200 OK`):
```json
{
  "id": "c1f7a0b5-77cf-4db0-a3e9-7ddca1f04b12",
  "name": "Alex Mercer",
  "email": "alex.mercer@company.com",
  "role": "ROLE_OPERATOR",
  "status": "ACTIVE",
  "created_at": "2026-10-31T10:45:00Z",
  "updated_at": "2026-10-31T10:45:00Z",
  "last_login_at": "2026-10-31T10:50:00Z"
}
```

---

### 2.6 Update Current User Profile
- **Endpoint:** `PATCH /api/v1/auth/me`
- **Security:** Authenticated
- **Description:** Updates allowed personal profile fields. Cannot change role or status.

#### Request Body:
```json
{
  "name": "Alexander Mercer, Senior Recovery Specialist"
}
```

#### Response (`HTTP 200 OK`):
Returns updated `UserResponseDTO`.

---

### 2.7 Change Password
- **Endpoint:** `POST /api/v1/auth/change-password`
- **Security:** Authenticated
- **Description:** Changes user password after verifying the existing password.

#### Request Body:
```json
{
  "current_password": "CorrectHorseBatteryStaple123",
  "new_password": "NewUltraSecurePassphrase2026!"
}
```

#### Response (`HTTP 200 OK`):
```json
{
  "message": "Password changed successfully"
}
```

---

## 3. Administrative User Management (`/api/v1/users`)

### 3.1 List All Users
- **Endpoint:** `GET /api/v1/users?skip=0&limit=20`
- **Security:** `ROLE_ADMIN` strictly
- **Description:** Paginated user account lookup.

#### Response (`HTTP 200 OK`):
```json
[
  {
    "id": "c1f7a0b5-77cf-4db0-a3e9-7ddca1f04b12",
    "name": "Alex Mercer",
    "email": "alex.mercer@company.com",
    "role": "ROLE_OPERATOR",
    "status": "ACTIVE",
    "created_at": "2026-10-31T10:45:00Z",
    "updated_at": "2026-10-31T10:45:00Z",
    "last_login_at": "2026-10-31T10:50:00Z"
  }
]
```

---

### 3.2 Update User Role
- **Endpoint:** `PATCH /api/v1/users/{user_id}/role`
- **Security:** `ROLE_ADMIN` strictly
- **Description:** Promotes or demotes an account role.

#### Request Body:
```json
{
  "role": "ROLE_ADMIN"
}
```

#### Response (`HTTP 200 OK`):
Returns updated `UserResponseDTO`.

---

### 3.3 Update User Status
- **Endpoint:** `PATCH /api/v1/users/{user_id}/status`
- **Security:** `ROLE_ADMIN` strictly
- **Description:** Suspends, reactivates, or marks an account inactive.

#### Request Body:
```json
{
  "status": "SUSPENDED"
}
```

#### Response (`HTTP 200 OK`):
Returns updated `UserResponseDTO`.
