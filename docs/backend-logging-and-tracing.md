# RevenueRescueAI — Backend Logging, Observability, and Request Tracing

## 1. Executive Summary

In high-concurrency fintech platforms, unstructured text logs (such as arbitrary `print()` statements or unformatted strings) make automated log analysis, distributed tracing, and production troubleshooting virtually impossible.

The **RevenueRescueAI Logging Architecture** enforces:
1. **Machine-Readable Structured JSON:** Every HTTP request and critical operational event emits a structured JSON object to standard output (`stdout`).
2. **Deterministic Correlation Tracing:** Inbound `X-Request-ID` or `X-Correlation-ID` headers are propagated through all services, middleware, and database audit logs.
3. **Strict Zero-Leakage Redaction:** Cardholder data (PAN/CVV), merchant webhook secrets, and user passwords are automatically stripped before serialization.

---

## 2. Request Observability Middleware Architecture

The request lifecycle is managed by [`RequestObservabilityMiddleware`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/core/observability.py), an ASGI middleware intercepting all HTTP interactions:

```
[ Inbound HTTP Request ] ──► (Header: X-Request-ID: req_01HP8A2Z...)
          │
          ▼
[ RequestObservabilityMiddleware ]
          │
          ├── 1. Capture start time (perf_counter)
          ├── 2. Extract or generate UUID4 request_id
          ├── 3. Execute request pipeline (app logic)
          ├── 4. Inject 'x-request-id' into response headers
          │
          ▼
[ JSON Access Event Emitted to stdout ]
```

### Emitted JSON Access Event Structure:
```json
{
  "event": "http_request",
  "request_id": "phase10-test-001",
  "method": "GET",
  "path": "/health",
  "status_code": 200,
  "duration_ms": 1.45
}
```

---

## 3. Log Levels & Formatting Standards

Logging is initialized via `configure_logging()` in [`app/core/logging.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/core/logging.py).

### Log Level Guidelines:

| Severity Level | Standard Use Case | Example Log Line |
| :--- | :--- | :--- |
| **`DEBUG`** | Low-level developer diagnostic details, query timings, internal loop traces. | `SQL query executed in 1.2ms: SELECT 1` |
| **`INFO`** | Routine operational milestones (case created, attempt started, outcome verified). | `Recovery case case_live_99214a transitioned from ACTION_PENDING to POLICY_APPROVED` |
| **`WARN`** | Expected recoverable anomalies (soft card declines, AI timeouts using fallback). | `AI recommendation model timed out after 3000ms; applying standard 24h retry fallback` |
| **`ERROR`** | Unhandled server exceptions, gateway 504 timeouts, database connectivity failures. | `Database connection probe failed during /health/db check` |

---

## 4. End-to-End Tracing: From Webhook to Audit Event

RevenueRescueAI links disparate operations across multi-day recovery episodes using a 5-tier correlation hierarchy:

```
Tier 1: Request ID (HTTP Transport)
        └── req_01HP8A2Z14
                 │
Tier 2: Case ID (Business Aggregate Root)
        └── case_live_99214a
                 │
Tier 3: Workflow ID (FSM Execution Episode)
        └── wf_vertical_recovery_v1
                 │
Tier 4: Attempt ID (Specific Provider Dispatch)
        └── att_01HP8A4K22 (idempotency_key = idemp_case_99214a_att_1)
                 │
Tier 5: Audit Event ID (Immutable Relational Record)
        └── audit_evt_01HP8A5M88 (sequence_number = 6)
```

### Tracing a Single Case via SQL:
```sql
SELECT 
    sequence_number,
    created_at,
    actor_type,
    event_type,
    old_state,
    new_state
FROM audit_events
WHERE case_id = 'case_live_99214a'
ORDER BY sequence_number ASC;
```

---

## 5. Security & PII Redaction Policy

The logging framework strictly adheres to the **Zero-CHD (Cardholder Data) Invariant**:
- **BANNED IN LOGS:** Primary Account Numbers (16-digit PAN), Card CVV/CVC codes, user plaintext passwords, `Stripe-Signature` secrets, and JWT private keys.
- **PERMITTED IN LOGS:** Masked card brand and last 4 digits (e.g., `Visa **** 4242`), customer UUIDs, transaction amounts in integer cents (`4500`), and gateway decline reason codes (`insufficient_funds`).
