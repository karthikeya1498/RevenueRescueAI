# Event Validation Rules — Phase 2.6

## 1. Overview
Validation in RevenueRescueAI operates under a defense-in-depth model. All events undergo structural schema validation (via Pydantic) followed by deterministic domain validation (via [`EventValidator`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/event_validator.py)).

Any violation results in immediate rejection with an RFC-7807 problem detail response (HTTP 422 Unprocessable Entity or HTTP 400 Bad Request) without writing corrupted records to the database.

---

## 2. Common Validation Rules (All Event Types)

| Rule Identifier | Field | Invariant Condition | Failure Response |
| :--- | :--- | :--- | :--- |
| **VAL-COM-01** | `event_type` | Must be an approved `CanonicalEventType`. | HTTP 400 `UNSUPPORTED_EVENT_TYPE` |
| **VAL-COM-02** | `external_event_id` | Cannot be empty or blank; length $\le 200$. | HTTP 422 `EVENT_VALIDATION_FAILED` |
| **VAL-COM-03** | `provider` | Cannot be empty or blank; length $\le 64$. | HTTP 422 `EVENT_VALIDATION_FAILED` |
| **VAL-COM-04** | `customer_reference` | Cannot be empty or blank; length $\le 128$. | HTTP 422 `EVENT_VALIDATION_FAILED` |
| **VAL-COM-05** | `amount_minor` | Must be a 64-bit integer $\ge 0$. Floating-point numbers and negative values strictly forbidden. | HTTP 422 `EVENT_VALIDATION_FAILED` |
| **VAL-COM-06** | `currency` | Exact 3 uppercase ASCII letters matching ISO-4217 (`^[A-Z]{3}$`). | HTTP 422 `EVENT_VALIDATION_FAILED` |
| **VAL-COM-07** | `occurred_at` | Cannot exceed current UTC time + 15 minutes (clock skew protection). | HTTP 422 `EVENT_VALIDATION_FAILED` |

---

## 3. Event-Type-Specific Rules

### 3.1 `PAYMENT_FAILED`
- **Rule VAL-PF-01:** `payment_reference` is required and must not be empty.
- **Rule VAL-PF-02:** `failure_code` is required and must not be empty.
- **Rule VAL-PF-03:** `amount_minor` must be $\ge 0$ (allows \$0 card validation/authorization failure).

### 3.2 `PAYMENT_SUCCEEDED`
- **Rule VAL-PS-01:** `payment_reference` is required and must not be empty.
- **Rule VAL-PS-02:** `amount_minor` must be $\ge 0$.

### 3.3 `SUBSCRIPTION_PAYMENT_FAILED`
- **Rule VAL-SPF-01:** Must contain at least one of `subscription_reference` or `payment_reference`.
- **Rule VAL-SPF-02:** `failure_code` is required and must not be empty.

### 3.4 `CHECKOUT_ABANDONED`
- **Rule VAL-CA-01:** `checkout_session_id` (or `metadata.checkout_id`) is required.
- **Important Invariant:** The system **does not** assume or require a payment transaction reference for checkout abandonments, as the user abandoned prior to gateway submission.

### 3.5 `INVOICE_OVERDUE`
- **Rule VAL-IO-01:** `invoice_reference` (or `metadata.invoice_id`) is required.
- **Rule VAL-IO-02:** `amount_minor` represents outstanding balance and must be $\ge 0$.
