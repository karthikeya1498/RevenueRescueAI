# RevenueRescueAI — API Error Handling & Fault Contracts
## Phase 1.3: Standard Error Envelope, Error Codes, and Client Retry Guidance

**Document Version:** 1.0.0  
**Status:** Approved Error Handling Standard  
**Primary Authors:** Senior Backend Architect, API Designer, Security Engineer  

---

## 1. Executive Summary & Philosophy

In financial systems, inconsistent error handling causes confusion, broken automated retry loops, and security leaks. If an API returns an unhandled HTTP 500 containing raw database SQL errors or stack traces, attackers gain structural intelligence and automated clients cannot determine whether a payment was charged or dropped.

RevenueRescueAI enforces **Four Error Handling Invariants**:
1. **Single Uniform Envelope:** Every 4xx and 5xx error response returns the identical JSON envelope structure.
2. **Deterministic Error Codes:** Clients branch logic based on machine-readable `error.code` strings, not fragile regex parsing of human messages.
3. **Explicit Retryability Guidance:** Every error contract clearly defines whether a client may retry immediately, retry with exponential backoff, or permanently halt.
4. **Zero Information Leakage:** Database errors, stack traces, passwords, and internal infrastructure IP addresses are completely masked.

---

## 2. Standard Error Response Envelope

All error responses adhere to the standard JSON structure:

```json
{
  "success": false,
  "error": {
    "code": "POLICY_REJECTED",
    "message": "The proposed action violates safety policy invariant INV-002: Maximum retry budget exceeded.",
    "details": [
      {
        "field": "prior_attempts",
        "issue": "Case has already executed 2 of 2 permitted retries."
      }
    ],
    "request_id": "req_8f31a_4490"
  }
}
```

### Envelope Field Definitions:
- `success` (Boolean): Always `false` on error responses.
- `error.code` (String): Standard machine-readable uppercase error token.
- `error.message` (String): Clear, human-readable, user-safe explanation.
- `error.details` (Array of Objects): Optional list of field-level validation errors or invariant violations.
- `error.request_id` (String): The correlation ID for tracing the error in backend logs.

---

## 3. Standard Error Code Catalogue

| Error Code | HTTP Status | Meaning & Occurrence Scenario | Client Retryable? | Recommended Client Action |
| :--- | :--- | :--- | :--- | :--- |
| **`INVALID_REQUEST`** | `400 Bad Request` | Request is syntactically invalid or missing query params. | No | Fix request syntax before resending. |
| **`VALIDATION_ERROR`** | `422 Unprocessable`| Pydantic schema validation failure (e.g., negative amount). | No | Fix field formats and re-submit. |
| **`UNAUTHORIZED`** | `401 Unauthorized` | Missing, expired, or invalid Bearer token / HMAC signature. | No (Auth required) | Refresh authentication token. |
| **`FORBIDDEN`** | `403 Forbidden` | Authenticated actor lacks required role (e.g., Operator on Admin route). | No | Request elevated role permissions. |
| **`RESOURCE_NOT_FOUND`** | `404 Not Found` | Requested `case_id` or transaction does not exist. | No | Verify ID existence before querying. |
| **`CONFLICT`** | `409 Conflict` | Case is in a terminal state (`RECOVERED`, `FAILED`, `TERMINATED`). | No (Terminal) | Halt actions; case is locked. |
| **`DUPLICATE_EVENT`** | `200 / 409 Conflict`| Ingested webhook event ID was already processed. | No (Handled) | Ignore; event was safely deduplicated. |
| **`IDEMPOTENCY_CONFLICT`**| `409 Conflict` | Same `Idempotency-Key` sent with a different payload. | No | Generate a new, unique key for different payloads. |
| **`POLICY_REJECTED`** | `400 Bad Request` | Action vetoed by Deterministic Policy Gate. | No | Review policy invariants (INV-001..16). |
| **`RETRY_LIMIT_REACHED`**| `400 Bad Request` | Attempted 3rd retry on case where 2 retries were spent. | No (Terminal) | Escalate case to human operator queue. |
| **`ACTION_EXPIRED`** | `410 Gone` | Action attempted outside the 72-hour attribution window. | No | Deny automated recovery attribution. |
| **`OUTCOME_UNCERTAIN`** | `504 Gateway Timeout`| Provider timed out during charge execution. | **No Blind Retry!** | Query provider status endpoint using idempotency key. |
| **`PROVIDER_UNAVAILABLE`**| `502 Bad Gateway` | Payment provider simulator or gateway network is down. | **Yes (Exponential Backoff)** | Retry with 4h backoff + jitter. |
| **`RATE_LIMIT_EXCEEDED`**| `429 Too Many Req`| Caller exceeded requests per minute quota. | **Yes (After Retry-After)** | Respect `Retry-After` header. |
| **`INTERNAL_SERVER_ERROR`**| `500 Server Error`| Unhandled internal exception. | **Yes (Exponential Backoff)** | Alert SRE; provide `request_id`. |

---

## 4. Invariant Protection & Safe Failure Behaviors

### 4.1 Invariant INV-008: Uncertain Outcome Handling (HTTP 504)
When a call to an external payment provider times out:
```json
{
  "success": false,
  "error": {
    "code": "OUTCOME_UNCERTAIN",
    "message": "Payment provider timed out before confirming transaction outcome. Case moved to verification pending.",
    "details": [
      {
        "idempotency_key": "rec_att_case001_seq1",
        "action_required": "Do not retry blindly. Check status via verification endpoint."
      }
    ],
    "request_id": "req_504_timeout_99"
  }
}
```
**Strict Behavioral Rule:** The client is explicitly warned **never to dispatch a blind retry**. The case is moved to `VERIFICATION_PENDING` until a status inquiry verifies whether funds were captured.

### 4.2 Invariant INV-002: Bounded Retry Limit Reached (HTTP 400)
```json
{
  "success": false,
  "error": {
    "code": "RETRY_LIMIT_REACHED",
    "message": "Case has exhausted its maximum budget of 2 retries. Automatic recovery halted.",
    "details": [
      {
        "case_id": "f7a28190-8812-4c22-b912-334455667788",
        "attempts_recorded": 2,
        "max_allowed": 2
      }
    ],
    "request_id": "req_retry_limit_02"
  }
}
```

---

## 5. Security & Masking Rules

Under no circumstances may an error response contain:
1. SQL query syntax, database table names, or constraint names.
2. Python traceback lines or stack traces.
3. Cardholder PANs, CVVs, or bank routing numbers.
4. Provider secrets, webhook secrets, or internal authorization tokens.
