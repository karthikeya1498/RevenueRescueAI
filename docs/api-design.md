# RevenueRescueAI — API Design Specification & Architectural Conventions
## Phase 1.3: REST Conventions, Protocols, Serialization, and Standards

**Document Version:** 1.0.0  
**Status:** Approved API Architecture  
**Primary Authors:** Senior Backend Architect, API Designer, Technical Documentation Specialist  
**Target Audience:** Frontend Engineers, Backend Engineers, QA Engineers, Technical Interviewers, Novice Developers  

---

## 1. Executive Summary & Core Philosophy

The RevenueRescueAI API is the contract connecting the frontend React dashboard, background workers, the payment simulator, and administrative operators.

In financial software engineering, APIs cannot be designed casually. An ambiguous endpoint name, an inconsistent timestamp format, or a floating-point rounding mismatch can cause duplicate charges, broken ledger reconciliations, or security vulnerabilities.

The API architecture adheres to **Five Inviolable Principles**:
1. **Financial Exactness:** All monetary values are represented strictly as 64-bit integer minor units (`amount_minor >= 0`). Floating-point arithmetic is forbidden across all API contracts.
2. **Deterministic Resource Paths:** Predictable, noun-based RESTful resources with explicit semantic HTTP verbs.
3. **Idempotent Financial Operations:** Any endpoint that modifies financial state, executes retries, or ingests payments requires an `Idempotency-Key` to make duplicate executions physically impossible.
4. **Structured Error Envelopes:** Every error response follows a uniform JSON envelope with a machine-readable code, user-safe message, and end-to-end request tracing ID.
5. **Zero Internal Exposure:** Database internals (e.g., internal SQLAlchemy class names, raw stack traces, database auto-increment IDs) are never exposed through API responses.

---

## 2. API Protocol & Versioning Strategy

### 2.1 Transport Protocol
- **HTTPS Only:** In production and staging, all traffic is encrypted with **TLS 1.3**. Plain HTTP requests are redirected to HTTPS.
- **WebSocket Secure (WSS):** Real-time event streaming utilizes `wss://` over the standard HTTPS port (Port 443 / 8000).

### 2.2 URI Versioning Standard
All application API routes carry a mandatory version prefix:
```http
/api/v1/{resource}
```
- **Why URI Versioning?** URI versioning (`/api/v1/`) makes the contract explicit in browser logs, network traces, and API gateways. If breaking changes are introduced in the future, `/api/v2/` can run concurrently without breaking existing frontend clients.
- **Health Exception:** Liveness and readiness endpoints (`/health` and `/ready`) remain unversioned at the root level to conform to standard container orchestrator healthcheck probes.

---

## 3. Resource Naming Conventions & HTTP Methods

Endpoints follow resource-oriented REST conventions using lowercase, hyphen-separated plural nouns:

| HTTP Verb | Semantic Purpose | Idempotent? | Safe? | Typical Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | Retrieve a resource or filtered collection. | **Yes** | **Yes** | `200 OK`, `404 Not Found` |
| `POST` | Create a resource, dispatch an action, or submit a webhook. | **No** (Requires `Idempotency-Key`) | **No** | `200 OK`, `201 Created`, `202 Accepted` |
| `PUT` | Replace an existing resource completely. | **Yes** | **No** | `200 OK` (Avoided in MVP) |
| `PATCH` | Partially update specified fields of a resource. | **Yes** | **No** | `200 OK` |
| `DELETE` | Soft-delete or close a resource. | **Yes** | **No** | `200 OK`, `204 No Content` |

### Endpoint Naming Pattern:
- List collection: `GET /api/v1/cases`
- Retrieve single instance: `GET /api/v1/cases/{case_id}`
- Sub-resource collection: `GET /api/v1/cases/{case_id}/attempts`
- Explicit lifecycle action: `POST /api/v1/cases/{case_id}/actions/retry`
- Webhook ingress: `POST /api/v1/webhooks/provider`

---

## 4. Data Representation & Serialization Rules

### 4.1 JSON Naming Conventions
- **`snake_case` Everywhere:** All JSON request bodies and response payloads use `snake_case` for property names (`amount_minor`, `case_key`, `created_at`, `failure_code`).
- **No Mixed Casing:** CamelCase (`amountMinor`) and PascalCase (`AmountMinor`) are strictly forbidden in HTTP payloads.

### 4.2 Timestamps: ISO-8601 UTC Only
All timestamps are serialized as ISO-8601 strings with explicit UTC timezone markers:
```json
"occurred_at": "2026-10-30T12:04:11.450Z"
```
- Timestamps without timezone offsets are rejected with HTTP 422.
- The UI layer is responsible for converting UTC timestamps into the operator's local browser timezone.

### 4.3 Monetary Value Representation
Every monetary amount in the API is expressed using two complementary fields:
1. `amount_minor` (Integer): The authoritative value in minor currency units (e.g., `842000` cents = $8,420.00 USD).
2. `currency` (String): The ISO-4217 uppercase 3-character currency code (`USD`, `EUR`, `GBP`).

```json
{
  "amount_minor": 842000,
  "currency": "USD"
}
```
**Strict Rule:** No API payload may ever transmit a floating-point number representing money (e.g., `"amount": 8420.00` is strictly rejected).

### 4.4 Null Values vs. Omitted Fields
- **Nullable Fields:** If a field has no value (e.g., `closed_at` on an open case), it is serialized explicitly as `null`.
- **Extra Fields:** Request bodies reject unexpected fields (`extra="forbid"` in Pydantic) to prevent accidental typos or prototype injection.

---

## 5. Pagination, Sorting, and Filtering Standards

### 5.1 Offset-Based Pagination Standard
Collections support standard query parameters:
- `limit` (Integer, Default: `20`, Max: `100`): Number of items per page.
- `offset` (Integer, Default: `0`, Min: `0`): Number of items to skip.

#### Standard Pagination Response Envelope:
```json
{
  "items": [ ... ],
  "pagination": {
    "total": 400,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

### 5.2 Sorting Standard
Sorting uses the `sort` query parameter:
- Format: `sort=field:asc` or `sort=field:desc`.
- Example: `GET /api/v1/cases?sort=last_state_changed_at:desc`
- Whitelisted sort fields: `opened_at`, `last_state_changed_at`, `priority`, `amount_minor`.

### 5.3 Filtering Standard
Filter parameters are passed as explicit query parameters:
- State filtering: `GET /api/v1/cases?state=action_pending`
- Risk level filtering: `GET /api/v1/cases?risk_level=high`
- Date range filtering: `GET /api/v1/cases?from_date=2026-10-01T00:00:00Z&to_date=2026-10-30T23:59:59Z`
- Text search: `GET /api/v1/cases?search=Northstar` (searches customer display name and external transaction IDs).

---

## 6. End-to-End Request Observability & Headers

Every API interaction carries standard tracing and diagnostic headers:

| Header Name | Type | Mandatory? | Purpose |
| :--- | :--- | :--- | :--- |
| `X-Request-ID` | Request / Response | Yes | Unique UUIDv4 correlation ID generated by the client or gateway for distributed tracing. |
| `Idempotency-Key` | Request | On Mutating POSTs | Unique token preventing duplicate financial execution. |
| `Authorization` | Request | On Protected Endpoints| Bearer token (`Bearer <token>`) providing user authentication. |
| `X-Signature-SHA256`| Request | On Webhooks | Cryptographic HMAC signature verifying provider authenticity. |
| `Content-Type` | Request / Response | Yes | `application/json; charset=utf-8`. |
