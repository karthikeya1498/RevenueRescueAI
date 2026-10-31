# RevenueRescueAI — Audit and History Data Design
## Phase 1.2: Immutable Audit Ledgers, Event Provenance, and Compliance History

**Document Version:** 1.0.0  
**Status:** Approved Audit Architecture  
**Primary Authors:** Senior Security Engineer, Financial Systems Architect, Compliance Analyst  

---

## 1. The Four Tiers of System Telemetry

In software engineering, confusing developer debug logs with financial audit records leads to compliance violations and data loss. RevenueRescueAI partitions system telemetry into **four distinct, non-overlapping tiers**:

```
+-----------------------------------------------------------------------------------------------+
|                                  TELEMETRY TIER TAXONOMY                                      |
+-------------------+---------------------------+-----------------------+-----------------------+
| Telemetry Tier    | Primary Technology        | Retention Period      | Primary Audience      |
+-------------------+---------------------------+-----------------------+-----------------------+
| 1. App Logs       | Stdout JSON (Uvicorn)     | 14–30 Days            | Developers / SREs     |
| 2. Workflow State | `case_state_transitions`  | 7 Years (Database)    | FSM / UI Timelines    |
| 3. Financial Book | `transactions`, `evidence`| 7 Years (Database)    | Accounting / Regulators|
| 4. Audit Ledger   | `audit_events` Table      | 7 Years (Database)    | Risk & Legal Auditors |
+-------------------+---------------------------+-----------------------+-----------------------+
```

### 1.1 Detailed Distinctions:
1. **Application Logs (Ephemeral):** Streamed to `stdout` via `RequestObservabilityMiddleware`. Contains HTTP method, path, status code, latency in milliseconds, and debug messages. Used for real-time debugging and APM monitoring. Dropped or rotated out after 30 days.
2. **Workflow State Transitions (`case_state_transitions`):** Normalized relational records tracking the formal case finite state machine (`from_state` $\to$ `to_state`). Queried by the frontend to render the visual "Agent Journey" timeline.
3. **Financial Transaction Records (`transactions`, `recovery_attempts`, `recovery_evidence`):** The double-entry-style operational ledger recording every monetary movement, gateway charge ID, and settled attribution proof in integer minor units.
4. **Audit Event Ledger (`audit_events`):** The permanent, chronologically sequenced business audit trail recording *who* decided *what*, *why*, *when*, and under *which policy rules*.

---

## 2. Comprehensive Event Capture Matrix

The following table defines the mandatory audit events recorded across the recovery lifecycle:

| Lifecycle Phase | Event Type (`event_type`) | Triggering Actor | Mandatory Payload Attributes (`payload_safe`) |
| :--- | :--- | :--- | :--- |
| **Ingestion** | `WEBHOOK_INGESTED` | `system` | `{"provider": "synthetic", "event_id": "evt_001", "event_type": "payment_failed"}` |
| **Deduplication**| `DUPLICATE_EVENT_DROPPED`| `system` | `{"external_event_id": "evt_001", "original_received_at": "..."}` |
| **Detection** | `CASE_DETECTED` | `system` | `{"trigger_transaction_id": "txn_001", "amount_minor": 842000, "currency": "USD"}` |
| **Eligibility** | `ELIGIBILITY_EVALUATED` | `agent_policy` | `{"verdict": "ELIGIBLE", "customer_status": "active", "dispute_count": 0}` |
| **AI Decision** | `AI_DECISION_PROPOSED` | `agent_policy` | `{"action": "retry_now", "confidence": 0.94, "reason": "soft_decline", "model": "baseline-v1"}` |
| **Policy Gate** | `POLICY_VALIDATED` | `agent_policy` | `{"invariants_checked": ["INV-001", "INV-002", "INV-006"], "verdict": "ALLOWED"}` |
| **Policy Veto** | `POLICY_OVERRIDE_VETO` | `agent_policy` | `{"proposed_action": "retry_now", "veto_reason": "retry_budget_exceeded_2", "override": "ESCALATE"}` |
| **Execution** | `ATTEMPT_DISPATCHED` | `system` | `{"attempt_seq": 1, "idempotency_key": "rec_att_01", "tool": "provider_retry_charge"}` |
| **Timeout/504** | `PROVIDER_TIMEOUT_UNCERTAIN`| `system` | `{"attempt_seq": 1, "http_status": 504, "disposition": "VERIFICATION_PENDING"}` |
| **Verification**| `RECOVERY_VERIFIED` | `system` | `{"amount_minor": 842000, "evidence_id": "evi_01", "window_hours_elapsed": 0.05}` |
| **Escalation** | `CASE_ESCALATED` | `agent_policy` | `{"escalation_reason": "retry_limit_reached", "queue": "human_operator_review"}` |
| **Operator Act**| `OPERATOR_ACTION_EXECUTED`| `human_operator` | `{"operator_id": "usr_alex_m", "action": "manual_override_retry", "justification": "..."}` |
| **Case Closed** | `CASE_CLOSED_TERMINAL` | `system` | `{"final_state": "RECOVERED", "total_attempts": 1, "recovered_amount_minor": 842000}` |

---

## 3. Monotonic Sequence Numbering & Tamper-Resistance

### 3.1 Strict Sequence Monotonicity
Every audit record for a given `case_id` is assigned an incremental integer `sequence_number` (`1, 2, 3, 4, ...`):
```sql
CONSTRAINT uq_audit_case_sequence UNIQUE (case_id, sequence_number)
```
**Why Sequence Numbers Matter:**
- Timestamps can suffer from clock skew, NTP sync jumps, or identical millisecond collisions under high concurrency.
- Sequence numbers guarantee that the business history of a case is **100% deterministic and strictly ordered**.
- If any process attempts to insert a record out of order or re-use a sequence number, the unique constraint rejects the transaction.

### 3.2 Append-Only Relational Protection (Zero UPDATE / DELETE)
To guarantee ledger integrity:
1. **Application Code Enforcement:** The repository and service layer contain zero SQL `UPDATE` or `DELETE` statements targeting `audit_events`.
2. **Database Role Privileges:** In production PostgreSQL, the application database user is granted `INSERT` and `SELECT` privileges only on `audit_events`. `UPDATE` and `DELETE` grants are explicitly withheld.

### 3.3 Clarification on Cryptographic vs. Relational Immutability
> **Architectural Honesty Note:**  
> An append-only relational table is **not a cryptographically immutable blockchain or Merkle tree**. A database administrator (superuser) with root access could theoretically alter rows directly via raw SQL.  
> However, for financial application compliance (SOC 2 Type II, ISO 27001), **database role privilege separation combined with external write-once log replication (WORM / CloudWatch Logs)** satisfies all regulatory requirements without the massive complexity and gas fees of distributed ledgers.

---

## 4. Sensitive-Data Minimization in Audit Records

Financial audit logs must comply with PCI-DSS and privacy regulations (GDPR / CCPA):
1. **Never Log Cardholder PANs or CVVs:** Credit card Primary Account Numbers and card security codes must never appear in `payload_safe`.
2. **Masked Contact Information:** Customer emails are masked (`a***@northstar.io`) before insertion into audit payloads.
3. **Zero Authentication Secrets:** API keys, webhook signing secrets, and bearer tokens are strictly scrubbed by the observability layer before serialization.
