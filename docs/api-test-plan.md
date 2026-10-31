# RevenueRescueAI — API Contract & Security Test Plan
## Phase 1.3: End-to-End API Test Specifications, Invariant Scenarios, and Verification Matrix

**Document Version:** 1.0.0  
**Status:** Approved Test Specification (Design Only)  
**Primary Authors:** QA Architect, Senior Backend Engineer, API Designer  

---

## 1. Test Strategy Overview

This test plan defines the formal API test suite designed to validate HTTP contracts, role-based authorization, idempotency deduplication, financial integrity invariants, and error envelopes before frontend or external integration.

### Test Categories:
1. **Contract Validation Tests (CT)**
2. **Authentication & RBAC Tests (AT)**
3. **Idempotency & Concurrency Tests (IT)**
4. **Financial Safety & Invariant Tests (FT)**
5. **API Functionality Tests (Pagination, Sort, Search) (FN)**
6. **Audit Ledger Generation Tests (AU)**
7. **Dashboard Metrics Accuracy Tests (MT)**

---

## 2. Comprehensive API Test Matrix

### 2.1 Category 1: Contract Validation Tests (CT)

| Test ID | Endpoint & Method | Input Scenario | Expected HTTP Status | Expected Response & Assertion |
| :--- | :--- | :--- | :--- | :--- |
| **CT-01** | `POST /api/v1/recovery/decision-preview` | Valid payload with `amount_minor: 842000` and `currency: "USD"`. | `200 OK` | Schema valid; returns `failure_classification` and `recommendation`. |
| **CT-02** | `POST /api/v1/recovery/decision-preview` | Negative monetary amount: `amount_minor: -100`. | `422 Unprocessable` | Error code `VALIDATION_ERROR`; details identify `amount_minor`. |
| **CT-03** | `POST /api/v1/recovery/decision-preview` | Lowercase currency: `currency: "usd"`. | `422 Unprocessable` | Rejected by ISO-4217 regex constraint `^[A-Z]{3}$`. |
| **CT-04** | `POST /api/v1/recovery/decision-preview` | Unexpected field injected: `extra_hack: true`. | `422 Unprocessable` | Rejected by `extra="forbid"` rule. |
| **CT-05** | `POST /api/v1/cases/{id}/actions/retry` | Missing required `justification` field. | `422 Unprocessable` | Error code `VALIDATION_ERROR`; missing required field. |

---

### 2.2 Category 2: Authentication & RBAC Tests (AT)

| Test ID | Endpoint & Method | Caller Identity / Credentials | Expected HTTP Status | Expected Security Effect |
| :--- | :--- | :--- | :--- | :--- |
| **AT-01** | `GET /api/v1/cases` | No `Authorization` header provided. | `401 Unauthorized` | Request rejected before reaching service handler. |
| **AT-02** | `GET /api/v1/cases` | Invalid/expired JWT Bearer token. | `401 Unauthorized` | Token decode failure; error code `UNAUTHORIZED`. |
| **AT-03** | `POST /api/v1/evaluation/run` | Valid token with `ROLE_OPERATOR` (Admin required). | `403 Forbidden` | Access blocked by RBAC gate; error code `FORBIDDEN`. |
| **AT-04** | `POST /api/v1/webhooks/provider`| Missing `X-Signature-SHA256` header. | `401 Unauthorized` | Immediate rejection; webhook secret verified. |
| **AT-05** | `POST /api/v1/webhooks/provider`| Webhook signature has timestamp older than 5 minutes. | `401 Unauthorized` | Replay attack detected and blocked. |

---

### 2.3 Category 3: Idempotency & Concurrency Tests (IT)

| Test ID | Endpoint & Method | Input Scenario | Expected HTTP Status | Expected Side Effect |
| :--- | :--- | :--- | :--- | :--- |
| **IT-01** | `POST /api/v1/cases/{id}/actions/retry`| Initial request with `Idempotency-Key: key_001`. | `200 OK` | Attempt executed; charge created with simulator. |
| **IT-02** | `POST /api/v1/cases/{id}/actions/retry`| Second request with identical `Idempotency-Key: key_001` and payload. | `200 OK` | Header `Idempotent-Replay: true`; zero duplicate charges executed. |
| **IT-03** | `POST /api/v1/cases/{id}/actions/retry`| Same `Idempotency-Key: key_001` sent with a different justification. | `409 Conflict` | Error code `IDEMPOTENCY_CONFLICT`; execution blocked. |
| **IT-04** | `POST /api/v1/cases/{id}/actions/retry`| Two concurrent requests arrive simultaneously with different keys. | First `200 OK`, Second `400 / 409` | Row lock `SELECT FOR UPDATE` serializes; second blocked if budget exceeded. |
| **IT-05** | `POST /api/v1/webhooks/provider` | Duplicate provider webhook with same `external_event_id`. | `200 OK` | Response indicates `"duplicate": true`; zero duplicate cases created. |

---

### 2.4 Category 4: Financial Safety & Invariant Tests (FT)

| Test ID | Endpoint & Method | Input Scenario | Expected HTTP Status | Expected Invariant Enforcement |
| :--- | :--- | :--- | :--- | :--- |
| **FT-01** | `POST /api/v1/cases/{id}/actions/retry`| Case has already executed 2 prior attempts. | `400 Bad Request` | **Invariant INV-002:** Error `RETRY_LIMIT_REACHED`; retry strictly blocked. |
| **FT-02** | `POST /api/v1/cases/{id}/actions/retry`| Case is in terminal state `RECOVERED`. | `409 Conflict` | **Invariant INV-004:** Error `CONFLICT`; terminal cases permanently locked. |
| **FT-03** | `POST /api/v1/verification/verify-evidence` | Evidence submitted with mismatched amount ($50 vs $8,420). | `400 Bad Request` | **Invariant INV-007:** Evidence attribution denied; case remains unrecovered. |
| **FT-04** | `POST /api/v1/verification/verify-evidence` | Evidence submitted after 80 hours (>72h threshold). | `410 Gone` | **Business Rule BR-023:** Window expired; recovery credit rejected. |
| **FT-05** | `POST /api/v1/cases/{id}/actions/retry`| Simulator injects HTTP 504 Gateway Timeout. | `504 Gateway Timeout` | **Invariant INV-008:** Error `OUTCOME_UNCERTAIN`; case moves to `VERIFICATION_PENDING`. |

---

### 2.5 Category 5: API Functionality Tests (FN)

| Test ID | Endpoint & Method | Query Parameters | Expected HTTP Status | Expected Response Structure |
| :--- | :--- | :--- | :--- | :--- |
| **FN-01** | `GET /api/v1/cases` | `limit=10&offset=0` | `200 OK` | Returns 10 items; `pagination.has_more = true`. |
| **FN-02** | `GET /api/v1/cases` | `state=action_pending` | `200 OK` | Every returned case has `state == "action_pending"`. |
| **FN-03** | `GET /api/v1/cases` | `sort=last_state_changed_at:desc` | `200 OK` | Items sorted chronologically descending. |
| **FN-04** | `GET /api/v1/cases` | `search=Northstar` | `200 OK` | Matches cases where customer name contains "Northstar". |
| **FN-05** | `GET /api/v1/cases/00000000-0000-0000-0000-000000000000` | Non-existent case UUID. | `404 Not Found` | Error code `RESOURCE_NOT_FOUND`. |

---

### 2.6 Category 6: Audit Ledger Generation Tests (AU)

| Test ID | Endpoint & Method | Tested Operation | Expected Audit Verification |
| :--- | :--- | :--- | :--- |
| **AU-01** | `POST /api/v1/cases/{id}/actions/retry` | Executing an approved retry action. | Generates `ATTEMPT_DISPATCHED` audit event with sequence number. |
| **AU-02** | `POST /api/v1/cases/{id}/actions/escalate` | Manual operator escalation. | Generates `CASE_ESCALATED` audit event with `operator_id` and reason. |
| **AU-03** | `POST /api/v1/cases/{id}/actions/stop` | Terminating recovery permanently. | Generates `CASE_CLOSED_TERMINAL` audit event with stop reason. |
| **AU-04** | `GET /api/v1/cases/{id}/audit-trail` | Inspecting audit log for sensitive data leaks. | Response contains zero card PANs, zero CVVs, and masked emails. |

---

### 2.7 Category 7: Dashboard Metrics Accuracy Tests (MT)

| Test ID | Endpoint & Method | Assertion Condition | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **MT-01** | `GET /api/v1/dashboard/metrics` | Cases in `VERIFICATION_PENDING` must NOT contribute to `recovered_revenue_minor`. | Verified amount excludes pending cases. |
| **MT-02** | `GET /api/v1/dashboard/metrics` | Sum of recovered amounts matches exact sum of `recovery_evidence.amount_minor`. | Mathematical exactness in minor units. |
| **MT-03** | `GET /api/v1/dashboard/metrics` | Evaluation synthetic batch metrics must NOT contaminate production totals. | Isolated `is_synthetic = TRUE` partition. |
