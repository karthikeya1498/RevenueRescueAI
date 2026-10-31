# Security Audit Events — RevenueRescueAI

## 1. Overview and Objectives

In a financial recovery operations system, security auditing provides indisputable non-repudiation and forensic visibility. The security event logging subsystem captures authentication occurrences, authorization rejections, and administrative state transitions.

---

## 2. Implemented Audit Event Types

| Event Identifier | Trigger Condition | Severity | Actor | Captured Metadata |
| :--- | :--- | :--- | :--- | :--- |
| `AUTH_REGISTER_SUCCESS` | New operator self-registration | `INFO` | Anonymous / Registered ID | `user_id`, `email`, `role`, `status`, `timestamp` |
| `AUTH_LOGIN_SUCCESS` | Successful password verification | `INFO` | User ID | `user_id`, `email`, `timestamp` |
| `AUTH_LOGIN_FAILURE` | Invalid password or nonexistent user | `WARNING`| Unauthenticated | `email` (normalized), `timestamp`, `failure_reason` |
| `AUTH_LOGOUT` | User logout request | `INFO` | User ID | `user_id`, `timestamp` |
| `AUTH_TOKEN_REFRESH` | Valid refresh token rotation | `INFO` | User ID | `user_id`, `jti`, `timestamp` |
| `AUTH_PASSWORD_CHANGE` | Successful password update | `NOTICE` | User ID | `user_id`, `timestamp` |
| `AUTH_ROLE_CHANGE` | Administrator updates user role | `CRITICAL`| Admin User ID | `target_user_id`, `old_role`, `new_role`, `timestamp` |
| `AUTH_STATUS_CHANGE` | Administrator modifies status | `CRITICAL`| Admin User ID | `target_user_id`, `old_status`, `new_status`, `timestamp` |
| `AUTH_ACCESS_DENIED` | Insufficient role on protected route| `WARNING`| User ID | `user_id`, `required_roles`, `user_role`, `endpoint` |

---

## 3. Data Sanitization & Secret Redaction Rules

Under zero circumstances do audit logs record:
1. **Plaintext Passwords:** Neither current, old, nor new passwords.
2. **Password Hashes:** BCrypt hashes are strictly excluded from logs.
3. **Raw JWT Signatures & Refresh Tokens:** Only token identifiers (`jti`) or token types are logged if needed, never the complete signature.
4. **Credit Card or Bank Details:** Completely segregated from security event logging.

---

## 4. Architectural Integration

During Phase 2.4, security logging is recorded through the standardized structured logger (`backend/app/core/logging.py`) with JSON output formatting:

```json
{
  "timestamp": "2026-10-31T10:45:12.192Z",
  "level": "INFO",
  "logger": "app.services.auth_service",
  "event": "AUTH_LOGIN_SUCCESS",
  "user_id": "c1f7a0b5-77cf-4db0-a3e9-7ddca1f04b12",
  "email": "alex.mercer@company.com"
}
```

In Phase 3 (Audit and Compliance Module), these structured events will also be dual-written to the immutable PostgreSQL `audit_logs` table for compliance retention and tamper-detection analysis.
