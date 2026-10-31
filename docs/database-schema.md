# RevenueRescueAI — Database Schema Specification

## 1. Executive Summary

This document specifies the exact, implemented relational database schema for **RevenueRescueAI**. 

The schema consists of **9 normalized tables** designed around Domain-Driven Design (DDD) aggregate boundaries, ensuring:
- **Financial Precision:** All monetary amounts are stored as 64-bit integer minor units (`amount_minor`). Floating-point types are completely prohibited.
- **Durable Idempotency:** Payment events and recovery attempts enforce unique natural business keys (`idempotency_key`, `provider_event_id`) at the database level.
- **Append-Only Auditing:** Audit records and state transitions are strictly monotonic and protected against deletion or modification.
- **Relational Integrity:** Foreign keys enforce strict referential boundaries with `RESTRICT` and `CASCADE` rules where appropriate.

---

## 2. Comprehensive Table Catalog

```
                                 DATABASE TABLES OVERVIEW
                                            │
       ┌─────────────────┬──────────────────┼─────────────────┬────────────────┐
       ▼                 ▼                  ▼                 ▼                ▼
  [customers]     [transactions]     [recovery_cases]  [recovery_attempts] [agent_decisions]
       │                 │                  │                 │                │
       └─────────────────┴──────────────────┼─────────────────┴────────────────┘
                                            │
       ┌─────────────────┬──────────────────┴─────────────────┬────────────────┐
       ▼                 ▼                                    ▼                ▼
 [audit_events] [case_state_transitions]          [provider_webhook_events] [recovery_evidence]
```

---

### Table 1: `customers`
- **Purpose:** Stores the merchant's customer profile and account status.
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `provider` | `VARCHAR(64)` | No | `'synthetic'` | Originating payment gateway (e.g. `stripe`, `razorpay`). |
| `external_customer_id` | `VARCHAR(128)` | No | — | Merchant or gateway's customer identifier. |
| `email` | `VARCHAR(320)` | Yes | `NULL` | Customer email address for recovery outreach. |
| `display_name` | `VARCHAR(200)` | Yes | `NULL` | Customer name or company name. |
| `status` | `VARCHAR(32)` | No | `'active'` | Account status (`active`, `inactive`, `restricted`). |
| `metadata` | `JSON` | No | `'{}'` | Non-sensitive provider metadata. |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Record creation timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Record last update timestamp. |

- **Unique Constraint:** `uq_customer_provider_external (provider, external_customer_id)`

---

### Table 2: `transactions`
- **Purpose:** Stores payment transactions (both initial failures and subsequent successful captures).
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `customer_id` | `UUID` | No | — | Foreign key to `customers.id` (`ON DELETE RESTRICT`). |
| `provider` | `VARCHAR(64)` | No | `'synthetic'` | Originating gateway adapter. |
| `external_transaction_id` | `VARCHAR(128)` | No | — | Gateway charge/transaction ID (`ch_...`). |
| `amount_minor` | `INTEGER` | No | — | Nominal transaction amount in cents/minor units. |
| `currency` | `VARCHAR(3)` | No | — | 3-letter ISO-4217 uppercase currency code. |
| `status` | `VARCHAR(32)` | No | — | Gateway transaction status (`created`, `succeeded`, `failed`, etc.). |
| `failure_code` | `VARCHAR(100)` | Yes | `NULL` | Normalized decline code (`insufficient_funds`, `expired_card`). |
| `failure_message_safe` | `VARCHAR(500)` | Yes | `NULL` | Sanitized decline explanation. |
| `occurred_at` | `TIMESTAMPTZ` | No | — | Timestamp when transaction occurred at gateway. |
| `metadata` | `JSON` | No | `'{}'` | Contextual telemetry (card brand, issuer country). |

- **Unique Constraint:** `uq_transaction_provider_external (provider, external_transaction_id)`
- **Check Constraints:** 
  - `ck_transaction_amount_nonnegative (amount_minor >= 0)`
  - `ck_transaction_currency (length(currency) = 3 AND currency = upper(currency))`
- **Index:** `ix_transaction_status_occurred (status, occurred_at)`

---

### Table 3: `recovery_cases`
- **Purpose:** The central Aggregate Root governing an episode of at-risk revenue.
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `customer_id` | `UUID` | No | — | Foreign key to `customers.id` (`ON DELETE RESTRICT`). |
| `trigger_transaction_id` | `UUID` | No | — | Foreign key to failed `transactions.id` (`ON DELETE RESTRICT`). |
| `case_key` | `VARCHAR(200)` | No | — | Canonical deterministic business key (`case_...`). |
| `state` | `VARCHAR(40)` | No | `'detected'` | Current FSM state (`detected`, `action_pending`, `recovered`, etc.). |
| `priority` | `INTEGER` | No | `100` | Processing priority score (1–1000). |
| `opened_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp when recovery episode began. |
| `last_state_changed_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp of most recent state mutation. |
| `closed_at` | `TIMESTAMPTZ` | Yes | `NULL` | Timestamp when case entered terminal state. |
| `version` | `INTEGER` | No | `1` | Optimistic concurrency control lock counter. |
| `metadata` | `JSON` | No | `'{}'` | Contextual operational metadata. |

- **Unique Constraint:** `uq_recovery_case_key (case_key)`
- **Indexes:** 
  - `ix_recovery_case_state_changed (state, last_state_changed_at)`
  - `ix_recovery_case_customer (customer_id)`

---

### Table 4: `recovery_attempts`
- **Purpose:** Tracks individual bounded recovery executions dispatched against payment simulator or gateways.
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `case_id` | `UUID` | No | — | Foreign key to `recovery_cases.id` (`ON DELETE CASCADE`). |
| `sequence_number` | `INTEGER` | No | — | Monotonic attempt index within case (1, 2, ...). |
| `status` | `VARCHAR(32)` | No | — | Attempt status (`planned`, `started`, `succeeded`, `failed`, `uncertain`). |
| `action_type` | `VARCHAR(32)` | No | `'none'` | Allow-listed tool intent (`retry_payment`, `send_reminder`). |
| `started_at` | `TIMESTAMPTZ` | Yes | `NULL` | Timestamp when outbound dispatch initiated. |
| `finished_at` | `TIMESTAMPTZ` | Yes | `NULL` | Timestamp when gateway response arrived. |
| `outcome` | `VARCHAR(100)` | Yes | `NULL` | Concise result string. |
| `provider_reference`| `VARCHAR(200)` | Yes | `NULL` | Gateway transaction or task reference ID. |
| `idempotency_key` | `VARCHAR(250)` | No | — | Deterministic UUIDv5 key ensuring exactly-once execution. |
| `error_class` | `VARCHAR(120)` | Yes | `NULL` | Classification of error if attempt failed. |
| `error_safe_message` | `VARCHAR(500)` | Yes | `NULL` | Sanitized error detail. |
| `metadata` | `JSON` | No | `'{}'` | Technical dispatch telemetry. |

- **Unique Constraints:** 
  - `uq_attempt_case_sequence (case_id, sequence_number)`
  - `uq_attempt_idempotency_key (idempotency_key)`
- **Index:** `ix_attempt_case_sequence (case_id, sequence_number)`

---

### Table 5: `agent_decisions`
- **Purpose:** Records AI recommendation proposals and Deterministic Policy Gate validation verdicts.
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `case_id` | `UUID` | No | — | Foreign key to `recovery_cases.id` (`ON DELETE CASCADE`). |
| `attempt_id` | `UUID` | Yes | `NULL` | Foreign key to `recovery_attempts.id` (`ON DELETE SET NULL`). |
| `decision_version` | `INTEGER` | No | `1` | Monotonic decision revision within case. |
| `action_type` | `VARCHAR(32)` | No | — | Proposed action type. |
| `reason_code` | `VARCHAR(120)` | No | — | Machine-readable rule or reasoning code. |
| `rationale_safe` | `VARCHAR(2000)`| Yes | `NULL` | Human-readable explanation of why action was chosen. |
| `confidence` | `NUMERIC(4,3)` | Yes | `NULL` | Model confidence score (0.000 to 1.000). |
| `raw_response_hash`| `VARCHAR(128)` | Yes | `NULL` | SHA-256 fingerprint of the raw model output. |
| `validation_status`| `VARCHAR(32)` | No | `'not_validated'` | Policy verdict (`valid`, `invalid`, `rejected_by_policy`). |

- **Check Constraint:** `ck_decision_confidence (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))`

---

### Table 6: `audit_events`
- **Purpose:** Append-only compliance and regulatory ledger capturing every operational mutation.
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `case_id` | `UUID` | No | — | Foreign key to `recovery_cases.id` (`ON DELETE CASCADE`). |
| `event_type` | `VARCHAR(120)` | No | — | Standard audit event type string. |
| `from_state` | `VARCHAR(40)` | Yes | `NULL` | Prior case state (if state change occurred). |
| `to_state` | `VARCHAR(40)` | Yes | `NULL` | Target case state (if state change occurred). |
| `actor_type` | `VARCHAR(32)` | No | — | Identity tier (`system`, `operator`, `agent`, `provider`, `test`). |
| `actor_id` | `VARCHAR(200)` | Yes | `NULL` | Specific operator email or system worker ID. |
| `correlation_id` | `VARCHAR(200)` | No | — | Distributed tracing correlation ID. |
| `event_time` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp event occurred. |
| `payload_safe` | `JSON` | No | `'{}'` | Non-sensitive payload data. |
| `sequence_number` | `INTEGER` | No | — | Monotonic sequence number within case. |

- **Unique Constraint:** `uq_audit_case_sequence (case_id, sequence_number)`
- **Index:** `ix_audit_case_sequence (case_id, sequence_number)`

---

### Table 7: `case_state_transitions`
- **Purpose:** Formal audit trail of every finite state machine transition.
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `case_id` | `UUID` | No | — | Foreign key to `recovery_cases.id` (`ON DELETE CASCADE`). |
| `from_state` | `VARCHAR(40)` | Yes | `NULL` | Originating state. |
| `to_state` | `VARCHAR(40)` | No | — | Destination state. |
| `reason_code` | `VARCHAR(120)` | No | — | Justification for state transition. |
| `actor_type` | `VARCHAR(32)` | No | — | Actor initiating transition. |
| `correlation_id` | `VARCHAR(200)` | No | — | Distributed trace correlation ID. |
| `occurred_at` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp transition took effect. |
| `sequence_number` | `INTEGER` | No | — | Monotonic transition order within case. |
| `metadata` | `JSON` | No | `'{}'` | Transition context. |

- **Unique Constraint:** `uq_transition_case_sequence (case_id, sequence_number)`
- **Index:** `ix_transition_case_occurred (case_id, occurred_at)`

---

### Table 8: `provider_webhook_events`
- **Purpose:** Ingests and deduplicates raw payment gateway webhook notifications.
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `provider` | `VARCHAR(64)` | No | — | Payment gateway (e.g. `stripe`, `razorpay`). |
| `external_event_id` | `VARCHAR(200)` | No | — | Gateway event identifier (`evt_...`). |
| `event_type` | `VARCHAR(160)` | No | — | Event name (`payment_intent.payment_failed`). |
| `payload_hash` | `VARCHAR(128)` | No | — | SHA-256 fingerprint of the raw payload bytes. |
| `signature_verified`| `BOOLEAN` | No | `false` | Whether HMAC signature was verified. |
| `processed` | `BOOLEAN` | No | `false` | Whether business workflow has ingested this event. |
| `payload_safe` | `JSON` | No | `'{}'` | Sanitized event payload (PII stripped). |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Arrival timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Processing timestamp. |

- **Unique Constraint:** `uq_provider_event (provider, external_event_id)`

---

### Table 9: `recovery_evidence`
- **Purpose:** Cryptographically verified proof linking an external gateway success to an intervention.
- **Primary Key:** `id` (`UUID`)

| Column Name | Data Type | Nullable | Default | Description & Constraints |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | No | `uuid4()` | Primary key. |
| `intervention_id` | `VARCHAR(200)` | No | — | Identifier of the recovery attempt or action. |
| `provider_event_id` | `VARCHAR(200)` | No | — | Authoritative provider success event ID. |
| `failed_transaction_id` | `VARCHAR(200)` | No | — | Original failed transaction ID being recovered. |
| `successful_transaction_id` | `VARCHAR(200)` | No | — | New successful transaction ID settling the balance. |
| `amount_minor` | `INTEGER` | No | — | Verified recovered amount in minor units (cents). |
| `currency` | `VARCHAR(3)` | No | — | 3-letter uppercase ISO currency code. |
| `verified_at` | `TIMESTAMPTZ` | No | — | Timestamp verification engine confirmed ledger proof. |
| `attribution_window_hours` | `INTEGER` | No | `72` | Allowed elapsed hours (max 72h). |
| `attribution_reason` | `VARCHAR(200)` | No | — | Mathematical proof description. |
| `attributable` | `BOOLEAN` | No | `false` | Final attribution verdict. |
| `evidence_json` | `JSON` | No | `'{}'` | Raw gateway receipt cryptographic hashes. |

- **Unique Constraint:** `uq_recovery_evidence_provider_event (provider_event_id)`
- **Check Constraints:** 
  - `ck_recovery_evidence_amount_nonnegative (amount_minor >= 0)`
  - `ck_recovery_evidence_currency (length(currency) = 3 AND currency = upper(currency))`
- **Index:** `ix_recovery_evidence_failed_transaction (failed_transaction_id)`
