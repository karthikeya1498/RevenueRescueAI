# RevenueRescueAI — Audit Logging & Idempotency Storage Specification

## 1. Executive Summary & Core Invariant

In high-concurrency automated financial platforms, application-level checks alone are insufficient to prevent duplicate billing and audit corruption. If two concurrent webhook requests or retry workers execute simultaneously, only **hard database constraints** can guarantee exactly-once execution.

RevenueRescueAI enforces two non-negotiable storage invariants:
1. **Durable Idempotency Boundary:** Every mutating operation (incoming webhook, external card charge) has a unique database constraint. Concurrent duplicate attempts fail immediately with a SQL unique violation.
2. **Append-Only Tamper-Resistant Auditing:** Audit rows and state transitions are monotonically sequenced per case. Database permissions revoke `UPDATE` and `DELETE`, guaranteeing permanent legal and financial auditability.

---

## 2. Idempotency & Duplicate Prevention Storage Architecture

```
[ Incoming Action / Event ]
           │
           ├── Webhook Ingestion ────────► provider_webhook_events (provider, external_event_id) UNIQUE
           │
           ├── Trigger Transaction ──────► transactions (provider, external_transaction_id) UNIQUE
           │
           └── Payment Retry Dispatch ───► recovery_attempts (idempotency_key) UNIQUE
```

---

### 2.1 Webhook Ingress Idempotency (`provider_webhook_events`)
When an external gateway (Stripe, Razorpay) sends a webhook, gateways routinely retry transmission if their HTTP client experiences transient network jitter.
- **Unique Constraint:**
  ```sql
  CONSTRAINT uq_provider_event UNIQUE (provider, external_event_id)
  ```
- **Payload Fingerprinting:** The SHA-256 hash of raw payload bytes is stored in `payload_hash`.
- **Handling Protocol (`WebhookEventRepository`):**
  - If `(provider, external_event_id)` is seen with the **same** `payload_hash`: Return `HTTP 200` with status `duplicate_event_suppressed`. No duplicate case is created.
  - If `(provider, external_event_id)` is seen with a **different** `payload_hash`: Flagged as an attack or malformed replay (`event_id_reused_with_different_payload`). Processing is blocked.

### 2.2 Payment Attempt Idempotency (`recovery_attempts`)
To guarantee that a customer's credit card is never charged twice for the same recovery attempt, every dispatch generates a **deterministic UUIDv5 key**:
```python
idempotency_key = uuid5(NAMESPACE_URL, f"revrescue:{case_id}:{attempt_number}")
```
- **Unique Constraint:**
  ```sql
  CONSTRAINT uq_attempt_idempotency_key UNIQUE (idempotency_key)
  ```
- **Concurrency Protection:** Even if two background workers race to execute attempt #1 for the same recovery case, the second worker hits `uq_attempt_idempotency_key` and is aborted by the database engine.

---

## 3. Append-Only Audit Trail Architecture

The system maintains two distinct append-only ledgers:

### 3.1 Business Audit Ledger (`audit_events`)
- Captures high-level business decisions (e.g. `CASE_DETECTED`, `POLICY_VETOED`, `RECOVERY_VERIFIED`).
- **Monotonic Sequence Enforcement:**
  ```sql
  CONSTRAINT uq_audit_case_sequence UNIQUE (case_id, sequence_number)
  ```
- Guaranteed sequential ordering (`sequence_number = 1, 2, 3...`) with zero duplicates or gaps per case.
- **Correlation ID Tracking:** Every row stores `correlation_id` to enable cross-system log correlation.

### 3.2 State Machine Transition Ledger (`case_state_transitions`)
- Captures exact Finite State Machine movements (`from_state` -> `to_state`).
- **Monotonic Sequence Enforcement:**
  ```sql
  CONSTRAINT uq_transition_case_sequence UNIQUE (case_id, sequence_number)
  ```
- Records `reason_code` and `actor_type` (`system`, `operator`, `agent`, `provider`, `test`).

---

## 4. Database Permission & Deletion Safeguards

To prevent accidental or malicious destruction of audit records:
1. **Production Role Grants:** In staging and production, the application database user is granted `INSERT` and `SELECT` only on `audit_events` and `case_state_transitions`.
   ```sql
   REVOKE UPDATE, DELETE ON audit_events FROM revenuerescue_app;
   REVOKE UPDATE, DELETE ON case_state_transitions FROM revenuerescue_app;
   ```
2. **Zero Cascade Destruction:** Root customer and transaction records cannot be deleted while child records exist (`ondelete="RESTRICT"`).

---

## 5. PII & Cardholder Data (CHD) Minimization

Audit payloads (`payload_safe`) adhere strictly to GDPR, CCPA, and PCI-DSS:
- **STRICTLY PROHIBITED:** Primary Account Numbers (PAN), CVVs, card expiration dates, user passwords, and customer phone numbers.
- **PERMITTED:** Masked card brand (`Visa **** 4242`), integer minor amounts (`amount_minor = 4500`), currency (`USD`), and decline codes (`insufficient_funds`).
