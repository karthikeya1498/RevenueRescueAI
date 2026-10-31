# RevenueRescueAI — Observability, Logging, and Tracing Design

## 1. Executive Summary & Observability Goals

In a mission-critical automated revenue recovery system, debugging production issues cannot rely on guesswork, unstructured `print()` statements, or scouring scattered text files.

The **RevenueRescueAI Observability Architecture** is engineered to provide complete, end-to-end transparency:
1. **End-to-End Traceability:** Any developer or auditor can take a single `case_id` or `correlation_id` and view every inbound webhook, AI prompt, policy check, payment attempt, and database state mutation in strict chronological order.
2. **Zero Sensitive Data Leakage:** Cryptographic secrets, cardholder data (PAN/CVV), and raw customer passwords are strictly scrubbed before any log entry is serialized to disk or stdout.
3. **Real-Time Operational Visibility:** Immediate alerts when AI timeout rates rise, policy rejections spike, or cases enter the `VERIFICATION_PENDING` (uncertain) state.

---

## 2. Distributed Tracing & Correlation Model

Every interaction entering the system is stamped with a set of contextual identifiers propagated across all layers:

```
[ Inbound HTTP Webhook ]
    │
    ├── X-Request-ID: req_9a8b7c6d5e
    └── X-Correlation-ID: corr_case_live_99214a
            │
            ▼
   [ FastApi Middleware ] ──► Injects correlation_id into Python ContextVar
            │
            ├──► AI Gateway Client (Logs request with correlation_id)
            ├──► Policy Validation Engine (Logs evaluation with correlation_id)
            ├──► Tool Execution Registry (Passes correlation_id in HTTP headers)
            └──► Relational Database (Stores correlation_id in audit_events)
```

### Key Tracing Identifiers:
- `request_id`: Identifies a single HTTP request lifecycle (e.g., `req_01HP8A2Z...`).
- `correlation_id`: Identifies the overarching business recovery episode spanning multiple requests over days (e.g., `corr_case_live_99214a`).
- `case_id`: The canonical business key of the `recovery_cases` aggregate root.
- `attempt_id`: Identifies a specific execution attempt within a case (e.g., `att_01HP8A4K...`).

---

## 3. Structured JSON Application Logging Standard

All application log lines are emitted as single-line JSON objects to standard output (`stdout`), formatted according to the following schema:

```json
{
  "timestamp": "2026-10-30T16:42:01.124Z",
  "level": "INFO",
  "logger": "revenuerescue.orchestrator.execution",
  "message": "Recovery attempt dispatched to simulator",
  "context": {
    "case_id": "case_live_99214a",
    "attempt_number": 1,
    "idempotency_key": "idemp_case_99214a_att_1",
    "tool_name": "SIMULATOR_CHARGE_RETRY",
    "nominal_amount_cents": 4500,
    "currency": "USD"
  },
  "trace": {
    "request_id": "req_881a7b",
    "correlation_id": "corr_case_live_99214a"
  },
  "performance": {
    "duration_ms": 142.6
  }
}
```

### Logging Rules & Prohibitions:
- **PROHIBITED:** Never log `Stripe-Signature` secret, JWT private keys, customer email, customer address, or card numbers.
- **MANDATORY:** Every log statement during workflow processing must include `case_id` and `correlation_id`.
- **LEVELS:**
  - `DEBUG`: Verbose query parameters, raw adapter request headers (sanitized).
  - `INFO`: State machine transitions, policy approvals, verified recovery settlements.
  - `WARN`: Policy rejections, AI timeouts falling back to rules, soft gateway declines.
  - `ERROR`: 504 network timeouts, unexpected exceptions, database transaction rollbacks.

---

## 4. Audit Events vs. Application Logs

A vital architectural distinction is maintained between **Application Logs** and **Audit Events**:

| Dimension | Application Logs | Audit Events (`audit_events` Table) |
| :--- | :--- | :--- |
| **Storage Medium** | Stdout / Log files / Datadog / CloudWatch | PostgreSQL Relational Database Table |
| **Lifecycle** | Transient (Retained 14–30 days) | Permanent & Immutable (Retained 7 years) |
| **Purpose** | Developer debugging & performance monitoring | Legal proof, financial reconciliation, compliance audits |
| **Integrity** | Best-effort delivery; can drop lines during spikes | Synchronous ACID transaction; 100% loss-free guarantee |
| **Query Mechanism** | Grep / ElasticSearch / LogQL | SQL Queries with indexes on `case_id`, `created_at` |

---

## 5. End-to-End Case Tracing Walkthrough

A developer investigating a customer inquiry can trace the entire lifecycle using a single SQL query:

```sql
SELECT 
    sequence_number,
    created_at,
    actor_type,
    event_type,
    old_state,
    new_state,
    payload_hash
FROM audit_events
WHERE case_id = 'case_live_99214a'
ORDER BY sequence_number ASC;
```

### Sample Output Trace:
```
seq | created_at           | actor_type | event_type                  | old_state           | new_state
----+----------------------+------------+-----------------------------+---------------------+--------------------
  1 | 2026-10-28 09:12:00  | SYSTEM     | EVENT_INGESTION_COMPLETED   | (null)              | DETECTED
  2 | 2026-10-28 09:12:01  | SYSTEM     | ENTITY_CORRELATION_PASS     | DETECTED            | VALIDATING
  3 | 2026-10-28 09:12:02  | SYSTEM     | ELIGIBILITY_VERIFIED        | VALIDATING          | DIAGNOSING
  4 | 2026-10-28 09:12:04  | AI_AGENT   | AI_RECOMMENDATION_FORMULATED| DIAGNOSING          | ACTION_PENDING
  5 | 2026-10-28 09:12:04  | POLICY_GATE| POLICY_APPROVAL_GRANTED     | ACTION_PENDING      | POLICY_APPROVED
  6 | 2026-10-28 09:12:05  | ORCHESTRATOR| ATTEMPT_DISPATCHED_ATT_1   | POLICY_APPROVED     | ACTION_EXECUTING
  7 | 2026-10-28 09:12:06  | PROVIDER   | PROVIDER_DECLINED_SOFT      | ACTION_EXECUTING    | RETRY_SCHEDULED
  8 | 2026-10-29 09:12:00  | SCHEDULER  | SCHEDULED_TIMER_ELAPSED     | RETRY_SCHEDULED     | POLICY_APPROVED
  9 | 2026-10-29 09:12:01  | ORCHESTRATOR| ATTEMPT_DISPATCHED_ATT_2   | POLICY_APPROVED     | ACTION_EXECUTING
 10 | 2026-10-29 09:12:03  | VERIFIER   | RECOVERY_SETTLEMENT_VERIFIED| ACTION_EXECUTING    | RECOVERED
```
Every step is accounted for, mathematically ordered, and attributable to a specific system actor.

---

## 6. Core Operational Metrics & Health Signals

The system exposes operational telemetry for proactive health monitoring:

1. **Recovery Execution Latency:**
   - Gateway call duration (Target: `p95 < 800ms`, `p99 < 2000ms`).
   - AI recommendation duration (Target: `p95 < 2500ms`).
2. **AI Reliability & Fallback Rate:**
   - Metric: `ai_fallback_rate_pct = (fallback_invocations / total_diagnoses) * 100`.
   - Alert Threshold: Alert if `> 5%` over a 15-minute window.
3. **Policy Gate Rejection Rate:**
   - Metric: `policy_rejection_count` by violated rule name.
   - Sudden spikes indicate model drift or upstream gateway code changes.
4. **Stale Processing Alert:**
   - Alert: Any case remaining in `ACTION_EXECUTING` for `> 5 minutes`.
5. **Dashboard Data Freshness:**
   - Dashboard polling interval = 10 seconds.
   - Maximum metric query execution time = `< 45ms`.
