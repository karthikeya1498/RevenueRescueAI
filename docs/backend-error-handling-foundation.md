# RevenueRescueAI — Global Error Handling Foundation & RFC-7807 Standard

## 1. Executive Summary & Design Goals

In modern API engineering, inconsistent error responses create massive friction for frontend developers and client integrators. If one endpoint returns `{ "error": "not found" }` while another returns `{ "message": "fail", "code": 404 }` and a third returns a raw HTML 500 stack trace, building reliable UI error states is virtually impossible.

RevenueRescueAI implements a **Unified Global Error Handling Foundation** compliant with the **RFC-7807 (Problem Details for HTTP APIs)** standard:
1. **Predictable JSON Structure:** Every single client error (4xx) and server error (5xx) returns an identical, strongly typed JSON payload.
2. **Correlation ID Everywhere:** Every error response contains the client's `request_id` or `correlation_id` to allow immediate distributed log lookup.
3. **Zero Stack Trace Leaks:** Raw Python tracebacks and internal SQL syntax errors are strictly logged to secure server logs and NEVER sent across the wire to HTTP clients.

---

## 2. Standard RFC-7807 Problem Detail Contract

All error responses from the backend follow this exact Pydantic schema:

```json
{
  "success": false,
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "RecoveryCase with identifier 'case_live_99214a' not found.",
  "request_id": "req_01HP8A2Z14",
  "timestamp": "2026-10-31T04:45:00.123456+00:00",
  "details": [
    {
      "field": "id",
      "message": "Resource does not exist",
      "code": "NOT_FOUND"
    }
  ]
}
```

### Schema Attributes:
- **`success` (`bool`):** Always `false` on error responses, allowing frontend code to check `if (!response.success)` uniformly.
- **`error_code` (`str`):** Stable, machine-readable uppercase string (e.g., `POLICY_VIOLATION`, `VALIDATION_FAILED`, `INTERNAL_SERVER_ERROR`).
- **`message` (`str`):** Concise, human-readable summary of the error safe for display in UI toast banners.
- **`request_id` (`str`):** Inbound `X-Request-ID` or generated correlation ID for developer support ticket matching.
- **`timestamp` (`str`):** Timezone-aware ISO-8601 UTC timestamp of when the error occurred.
- **`details` (`list[ErrorDetail]`):** Granular array of field-level or rule-level failures (especially useful for form validation).

---

## 3. Domain Exception Hierarchy

All custom errors inherit from the root `RevenueRescueException` class in [`app/core/errors.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/core/errors.py):

```
                        RevenueRescueException
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
EntityNotFoundException   DuplicateEntityException   PolicyViolationException
  (HTTP 404 Not Found)      (HTTP 409 Conflict)     (HTTP 422 Unprocessable)
         │                        │                        │
         ▼                        ▼                        ▼
DatabaseConnectionException InvalidStateTransitionException
(HTTP 503 Unavailable)      (HTTP 400 Bad Request)
```

### Custom Exception Catalogue:

| Exception Class | HTTP Status | Error Code | Example Trigger Scenario |
| :--- | :---: | :--- | :--- |
| `EntityNotFoundException` | `404` | `RESOURCE_NOT_FOUND` | Querying `/api/v1/cases/case_nonexistent`. |
| `DuplicateEntityException` | `409` | `DUPLICATE_ENTITY` | Ingesting a webhook with an existing `provider_event_id`. |
| `PolicyViolationException` | `422` | `POLICY_VIOLATION` | Attempting a 3rd payment retry when policy limit is 2. |
| `InvalidStateTransitionException` | `400` | `INVALID_STATE_TRANSITION` | Attempting to transition from `RECOVERED` to `DIAGNOSING`. |
| `DatabaseConnectionException` | `503` | `DATABASE_UNAVAILABLE` | Database engine probe fails during query execution. |

---

## 4. Automatic Request Validation Error Formatting

When a client submits malformed JSON (e.g., passing a negative amount or missing a mandatory string field), FastAPI catches `RequestValidationError` and formats the Pydantic error tree into the standard schema:

```json
{
  "success": false,
  "error_code": "VALIDATION_FAILED",
  "message": "The request payload failed input schema validation.",
  "request_id": "req_88192a",
  "timestamp": "2026-10-31T04:45:00.123456+00:00",
  "details": [
    {
      "field": "amount_cents",
      "message": "Input should be greater than 0",
      "code": "greater_than"
    },
    {
      "field": "customer_id",
      "message": "Field required",
      "code": "missing"
    }
  ]
}
```

---

## 5. Defense Against Stack Trace Leaks (500 Internal Errors)

If an unhandled exception occurs (such as a `ZeroDivisionError` or unexpected library failure), the global exception handler intercepts the error:

1. **Server-Side Action:** Logs the full stack trace with `logger.error(..., exc_info=exc)` alongside the `request_id`.
2. **Client-Side Response:** Returns a clean, redacted payload:
   ```json
   {
     "success": false,
     "error_code": "INTERNAL_SERVER_ERROR",
     "message": "An unexpected internal error occurred. Please contact support with the request ID.",
     "request_id": "req_crash_99",
     "timestamp": "2026-10-31T04:45:00.123456+00:00",
     "details": []
   }
   ```
**Security Invariant:** Attackers cannot glean database table structures, Python file paths, or third-party package versions from error responses.
