# Frontend Authentication Integration Guide — RevenueRescueAI

## 1. Overview and Integration Architecture

This guide specifies how the Next.js / React frontend communicates with the RevenueRescueAI backend authentication services. The backend provides a stateless JWT-based authentication system with dual tokens (Access Token and Refresh Token).

The frontend interface must never attempt to perform security or authorization checks on its own as authoritative; the backend security boundary is the single source of truth.

---

## 2. Authentication Flow & State Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Operator
    participant UI as Next.js Frontend
    participant Storage as In-Memory State / Secure Storage
    participant API as Backend Auth API

    User->>UI: Enter email & password
    UI->>API: POST /api/v1/auth/login
    alt Invalid Credentials
        API-->>UI: 401 Unauthorized {"error": {"code": "UNAUTHORIZED", "message": "Invalid credentials"}}
        UI->>User: Display "Invalid email or password"
    else Successful Login
        API-->>UI: 200 OK {access_token, refresh_token, token_type: "bearer", expires_in: 3600}
        UI->>Storage: Store access_token in memory<br/>Store refresh_token in secure storage
        UI->>API: GET /api/v1/auth/me (with Authorization: Bearer <access_token>)
        API-->>UI: 200 OK User Profile {id, name, email, role, status}
        UI->>User: Redirect to Operations Dashboard
    end
```

---

## 3. Request and Response Specifications

### 3.1 Operator Registration (Sign Up)
- **URL:** `/api/v1/auth/register`
- **Method:** `POST`
- **Headers:** `Content-Type: application/json`

#### Request Payload:
```json
{
  "name": "Jordan Lee",
  "email": "jordan.lee@revenuerescue.ai",
  "password": "StrongPassword2026!"
}
```

#### Response Payload (`HTTP 201 Created`):
```json
{
  "id": "e4b99824-345f-4a3d-82d8-bf5cc86d9972",
  "name": "Jordan Lee",
  "email": "jordan.lee@revenuerescue.ai",
  "role": "ROLE_OPERATOR",
  "status": "ACTIVE",
  "created_at": "2026-10-31T11:00:00Z",
  "updated_at": "2026-10-31T11:00:00Z",
  "last_login_at": null
}
```

---

### 3.2 Operator Login
- **URL:** `/api/v1/auth/login`
- **Method:** `POST`
- **Headers:** `Content-Type: application/json`

#### Request Payload:
```json
{
  "email": "jordan.lee@revenuerescue.ai",
  "password": "StrongPassword2026!"
}
```

#### Response Payload (`HTTP 200 OK`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlNGI5OTgyNC0zNDVmLTRhM2QtODJkOC1iZjVjYzg2ZDk5NzIiLCJlbWFpbCI6ImpvcmRhbi5sZWVAcmV2ZW51ZXJlc2N1ZS5haSIsInJvbGUiOiJST0xFX09QRVJBVE9SIiwidG9rZW5fdHlwZSI6ImFjY2VzcyIsImp0aSI6ImY2YjI4YWYxLTkzMDYtNDQ2ZS05NWRmLTQzN2U4MTU2NGNhNCIsImV4cCI6MTc5MzQ1Mjg0OCwiaWF0IjoxNzkzNDQ5MjQ4fQ.signature_bytes",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlNGI5OTgyNC0zNDVmLTRhM2QtODJkOC1iZjVjYzg2ZDk5NzIiLCJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImp0aSI6ImNkMmMwOGVmLTE2NTItNGZkYy1iYjVjLTViNDRlNDg1NDYwMSIsImV4cCI6MTc5NDA1NDA0OCwiaWF0IjoxNzkzNDQ5MjQ4fQ.signature_bytes",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 3.3 Silent Token Refresh (Interceptors)
When the frontend HTTP client receives a `401 Unauthorized` or notices the access token is within 5 minutes of expiring, it executes a refresh request:

- **URL:** `/api/v1/auth/refresh`
- **Method:** `POST`
- **Headers:** `Content-Type: application/json`

#### Request Payload:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Response Payload (`HTTP 200 OK`):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.new_access_token_bytes",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.new_refresh_token_bytes",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### 3.4 Authenticated API Invocations
All subsequent protected requests must append the HTTP Authorization header:
```http
Authorization: Bearer <access_token>
```

Example request to retrieve current operator profile:
```http
GET /api/v1/auth/me HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
```

---

### 3.5 Password Change Request
- **URL:** `/api/v1/auth/change-password`
- **Method:** `POST`
- **Headers:**
  - `Authorization: Bearer <access_token>`
  - `Content-Type: application/json`

#### Request Payload:
```json
{
  "current_password": "StrongPassword2026!",
  "new_password": "EvenStrongerPassword2027#!"
}
```

#### Response (`HTTP 200 OK`):
```json
{
  "message": "Password changed successfully"
}
```

---

## 4. Frontend Error & Session Handling Guide

| HTTP Status | Error Code | Meaning | Recommended Frontend Action |
| :--- | :--- | :--- | :--- |
| `401 Unauthorized` | `UNAUTHORIZED` | Token expired, invalid signature, or wrong login credentials. | If refreshing fails, clear stored tokens and redirect user to `/login` with an informative banner. |
| `403 Forbidden` | `FORBIDDEN` | Authenticated, but user lacks role (e.g. Operator accessing Admin panel) or account is Suspended. | Show access denied alert or redirect to dashboard. Do not clear session if role mismatch; clear session if account suspended. |
| `409 Conflict` | `CONFLICT` | Email already registered. | Show inline error on email field: "An account with this email address already exists." |
| `422 Unprocessable` | `VALIDATION_ERROR` | Password < 8 characters or malformed email. | Display field-specific validation warnings. |
