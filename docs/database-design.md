# RevenueRescueAI — Database Schema Design Specification
## Phase 1.2: Logical Relational Schema, Table Specifications, and Integrity Constraints

**Document Version:** 1.0.0  
**Status:** Approved Schema Specification  
**Target Engine:** PostgreSQL 16 Alpine (Production/Staging) / SQLite 3 Dialect (Test Isolation)  
**Primary Authors:** Principal Database Architect, Senior Backend Engineer  

---

## 1. Schema Conventions & Standards

To ensure production-grade consistency across all database tables:
1. **Table Naming:** Lowercase plural nouns separated by underscores (`customers`, `transactions`, `recovery_cases`).
2. **Primary Keys:** Every table uses a non-sequential, randomly generated `id UUID PRIMARY KEY`. UUIDv4 prevents ID enumeration attacks, protects business volume confidentiality, and allows client/service key pre-generation without database roundtrips.
3. **Monetary Representation:** Every financial amount is stored as an exact 64-bit integer (`BIGINT`) representing minor currency units (`amount_minor >= 0`). Ordinary floating-point math is strictly forbidden.
4. **Timestamp Standardization:** Every timestamp is stored in **UTC with timezone** (`TIMESTAMPTZ` in PostgreSQL). Column names explicitly indicate meaning (`occurred_at`, `opened_at`, `closed_at`, `created_at`).
5. **Audit Metadata:** Operational tables inherit `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` and `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
6. **Constraint Naming Convention:**
   - Primary Keys: `pk_<table_name>`
   - Foreign Keys: `fk_<table_name>_<column_name>`
   - Unique Constraints: `uq_<table_name>_<descriptor>`
   - Check Constraints: `ck_<table_name>_<descriptor>`
   - Indexes: `ix_<table_name>_<columns>`

---

## 2. Comprehensive Table Specifications

### 2.1 Table: `customers`
- **Purpose:** Stores merchant customer profiles, contact info, and recovery restriction flags.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Unique internal customer identifier. |
| `provider` | `VARCHAR(64)` | No | `'synthetic'` | Originating provider namespace. |
| `external_customer_id` | `VARCHAR(128)` | No | — | Merchant's unique customer ID. |
| `email` | `VARCHAR(320)` | Yes | `NULL` | Masked email address for customer updates. |
| `display_name` | `VARCHAR(200)` | Yes | `NULL` | Customer or company display name. |
| `status` | `VARCHAR(32)` | No | `'active'` | Enum: `active`, `inactive`, `restricted`. |
| `metadata` | `JSONB / JSON` | No | `'{}'` | Safe customer metadata. |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Account creation timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Last account update timestamp. |

- **Constraints & Indexes:**
  - `CONSTRAINT uq_customer_provider_external UNIQUE (provider, external_customer_id)`
  - `INDEX ix_customers_status (status)`
- **Foreign Key Relationships:**
  - One-to-Many with `transactions` (`fk_transactions_customer_id`, `ON DELETE RESTRICT`)
  - One-to-Many with `recovery_cases` (`fk_recovery_cases_customer_id`, `ON DELETE RESTRICT`)
- **Retention:** Retained permanently while active customer transactions exist.

---

### 2.2 Table: `transactions`
- **Purpose:** Immutable ledger of payment events received from providers or created during recovery.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Internal transaction identifier. |
| `customer_id` | `UUID` | No | — | **FK** $\to$ `customers.id` (`ON DELETE RESTRICT`). |
| `provider` | `VARCHAR(64)` | No | `'synthetic'` | Originating payment provider. |
| `external_transaction_id`| `VARCHAR(128)` | No | — | Provider's unique transaction reference. |
| `amount_minor` | `BIGINT` | No | — | Monetary value in minor units (cents). |
| `currency` | `VARCHAR(3)` | No | — | ISO-4217 uppercase 3-character code. |
| `status` | `VARCHAR(32)` | No | — | Enum: `created`, `succeeded`, `failed`, `pending`... |
| `failure_code` | `VARCHAR(100)` | Yes | `NULL` | Raw provider error code string. |
| `failure_message_safe` | `VARCHAR(500)` | Yes | `NULL` | Sanitized human-readable error summary. |
| `occurred_at` | `TIMESTAMPTZ` | No | — | Exact network timestamp of the event. |
| `metadata` | `JSONB / JSON` | No | `'{}'` | Non-sensitive provider payload attributes. |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Database insertion timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Last record update timestamp. |

- **Constraints & Indexes:**
  - `CONSTRAINT ck_transaction_amount_nonnegative CHECK (amount_minor >= 0)`
  - `CONSTRAINT ck_transaction_currency CHECK (length(currency) = 3 AND currency = upper(currency))`
  - `CONSTRAINT uq_transaction_provider_external UNIQUE (provider, external_transaction_id)`
  - `INDEX ix_transaction_status_occurred (status, occurred_at)`
  - `INDEX ix_transaction_customer (customer_id)`
- **Retention:** 7 years for financial compliance and accounting audit trails.

---

### 2.3 Table: `provider_webhook_events`
- **Purpose:** Durable, idempotent receipt ledger for incoming provider event payloads.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Ingestion event identifier. |
| `provider` | `VARCHAR(64)` | No | — | Provider name (`synthetic`, `stripe`). |
| `external_event_id` | `VARCHAR(200)` | No | — | Provider's webhook event identifier. |
| `event_type` | `VARCHAR(160)` | No | — | Event name (`payment_intent.failed`). |
| `payload_hash` | `VARCHAR(128)` | No | — | SHA-256 digest of payload for tamper detection.|
| `signature_verified` | `BOOLEAN` | No | `FALSE` | HMAC cryptographic verification flag. |
| `processed` | `BOOLEAN` | No | `FALSE` | Processing completion flag. |
| `payload_safe` | `JSONB / JSON` | No | `'{}'` | Sanitized event body (zero secrets/PANs). |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Webhook receipt timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Processing completion timestamp. |

- **Constraints & Indexes:**
  - `CONSTRAINT uq_provider_event UNIQUE (provider, external_event_id)`
  - `INDEX ix_webhook_processed (processed)`
- **Retention:** 90 days operational retention; archived cold thereafter.

---

### 2.4 Table: `recovery_cases`
- **Purpose:** Core lifecycle aggregate coordinating the recovery of one at-risk payment.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Unique recovery case identifier. |
| `customer_id` | `UUID` | No | — | **FK** $\to$ `customers.id` (`ON DELETE RESTRICT`). |
| `trigger_transaction_id` | `UUID` | No | — | **FK** $\to$ `transactions.id` (`ON DELETE RESTRICT`).|
| `case_key` | `VARCHAR(200)` | No | — | Unique deterministic business key. |
| `state` | `VARCHAR(40)` | No | `'detected'` | Enum: `detected`, `action_pending`, `recovered`... |
| `priority` | `INTEGER` | No | `100` | Urgency rank (1 = highest urgency). |
| `opened_at` | `TIMESTAMPTZ` | No | — | Timestamp when case was initialized. |
| `last_state_changed_at` | `TIMESTAMPTZ` | No | — | Timestamp of most recent state change. |
| `closed_at` | `TIMESTAMPTZ` | Yes | `NULL` | Timestamp when case reached terminal state. |
| `version` | `INTEGER` | No | `1` | Optimistic locking concurrency counter. |
| `metadata` | `JSONB / JSON` | No | `'{}'` | Case summary tags and diagnosis. |

- **Constraints & Indexes:**
  - `CONSTRAINT uq_recovery_case_key UNIQUE (case_key)`
  - `INDEX ix_recovery_case_state_changed (state, last_state_changed_at)`
  - `INDEX ix_recovery_case_customer (customer_id)`
  - `INDEX ix_recovery_case_trigger (trigger_transaction_id)`
- **Retention:** 7 years for financial auditability.

---

### 2.5 Table: `recovery_attempts`
- **Purpose:** Records physical recovery actions executed against the payment provider.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Recovery attempt identifier. |
| `case_id` | `UUID` | No | — | **FK** $\to$ `recovery_cases.id` (`ON DELETE CASCADE`).|
| `sequence_number` | `INTEGER` | No | — | Attempt sequence number (`1` or `2`). |
| `status` | `VARCHAR(32)` | No | — | Enum: `planned`, `started`, `succeeded`, `failed`...|
| `action_type` | `VARCHAR(40)` | No | `'none'` | Enum: `retry_now`, `schedule_retry`... |
| `started_at` | `TIMESTAMPTZ` | Yes | `NULL` | HTTP dispatch timestamp. |
| `finished_at` | `TIMESTAMPTZ` | Yes | `NULL` | Provider response receipt timestamp. |
| `outcome` | `VARCHAR(100)` | Yes | `NULL` | Provider outcome string. |
| `provider_reference` | `VARCHAR(200)` | Yes | `NULL` | Gateway charge ID (e.g., `ch_sim_8F31`). |
| `idempotency_key` | `VARCHAR(250)` | No | — | Unique deterministic execution key. |
| `error_class` | `VARCHAR(120)` | Yes | `NULL` | Canonical error class if failed. |
| `error_safe_message` | `VARCHAR(500)` | Yes | `NULL` | Scrubbed error message. |
| `metadata` | `JSONB / JSON` | No | `'{}'` | Execution diagnostic payload. |

- **Constraints & Indexes:**
  - `CONSTRAINT uq_attempt_case_sequence UNIQUE (case_id, sequence_number)`
  - `CONSTRAINT uq_attempt_idempotency_key UNIQUE (idempotency_key)`
  - `CONSTRAINT ck_attempt_sequence_budget CHECK (sequence_number >= 1 AND sequence_number <= 2)`
  - `INDEX ix_attempt_case_sequence (case_id, sequence_number)`
- **Retention:** 7 years.

---

### 2.6 Table: `agent_decisions`
- **Purpose:** Immutable record of AI recommendations and their policy validation status.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Decision record identifier. |
| `case_id` | `UUID` | No | — | **FK** $\to$ `recovery_cases.id` (`ON DELETE CASCADE`).|
| `attempt_id` | `UUID` | Yes | `NULL` | **FK** $\to$ `recovery_attempts.id` (`ON DELETE SET NULL`).|
| `decision_version` | `INTEGER` | No | `1` | Decision contract schema version. |
| `action_type` | `VARCHAR(40)` | No | — | Proposed action enum. |
| `reason_code` | `VARCHAR(120)` | No | — | Diagnostic reason code. |
| `rationale_safe` | `VARCHAR(2000)`| Yes | `NULL` | Human-readable explanation. |
| `confidence` | `NUMERIC(4,3)` | Yes | `NULL` | Confidence score between 0.000 and 1.000. |
| `raw_response_hash` | `VARCHAR(128)` | Yes | `NULL` | SHA-256 hash of raw model response. |
| `validation_status` | `VARCHAR(40)` | No | `'not_validated'`| Enum: `validated`, `overridden_by_policy`... |

- **Constraints & Indexes:**
  - `CONSTRAINT ck_decision_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))`
  - `INDEX ix_decision_case (case_id)`
- **Retention:** 7 years.

---

### 2.7 Table: `case_state_transitions`
- **Purpose:** Normalized, queryable history of state machine transitions.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Transition identifier. |
| `case_id` | `UUID` | No | — | **FK** $\to$ `recovery_cases.id` (`ON DELETE CASCADE`).|
| `from_state` | `VARCHAR(40)` | Yes | `NULL` | Originating state (null for creation). |
| `to_state` | `VARCHAR(40)` | No | — | Destination state. |
| `reason_code` | `VARCHAR(120)` | No | — | Domain explanation string. |
| `actor_type` | `VARCHAR(32)` | No | — | Enum: `system`, `agent_policy`, `human_operator`. |
| `correlation_id` | `VARCHAR(200)` | No | — | Distributed trace identifier. |
| `occurred_at` | `TIMESTAMPTZ` | No | — | Transition occurrence timestamp. |
| `sequence_number` | `INTEGER` | No | — | Monotonic sequence number for case. |
| `metadata` | `JSONB / JSON` | No | `'{}'` | Transition context snapshot. |

- **Constraints & Indexes:**
  - `CONSTRAINT uq_transition_case_sequence UNIQUE (case_id, sequence_number)`
  - `INDEX ix_transition_case_occurred (case_id, occurred_at)`
- **Retention:** 7 years.

---

### 2.8 Table: `audit_events`
- **Purpose:** Permanent, append-only chronological audit trail.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Audit event identifier. |
| `case_id` | `UUID` | No | — | **FK** $\to$ `recovery_cases.id` (`ON DELETE CASCADE`).|
| `event_type` | `VARCHAR(120)` | No | — | Canonical audit event name. |
| `from_state` | `VARCHAR(40)` | Yes | `NULL` | Prior case state. |
| `to_state` | `VARCHAR(40)` | Yes | `NULL` | Resulting case state. |
| `actor_type` | `VARCHAR(32)` | No | — | Actor category. |
| `actor_id` | `VARCHAR(200)` | Yes | `NULL` | Actor identity string. |
| `correlation_id` | `VARCHAR(200)` | No | — | Distributed correlation ID. |
| `event_time` | `TIMESTAMPTZ` | No | — | Audit event occurrence time. |
| `payload_safe` | `JSONB / JSON` | No | `'{}'` | Non-sensitive event metadata. |
| `sequence_number` | `INTEGER` | No | — | Strictly increasing monotonic sequence. |

- **Constraints & Indexes:**
  - `CONSTRAINT uq_audit_case_sequence UNIQUE (case_id, sequence_number)`
  - `INDEX ix_audit_case_sequence (case_id, sequence_number)`
  - `INDEX ix_audit_correlation (correlation_id)`
- **Retention:** 7 years permanent.

---

### 2.9 Table: `recovery_evidence`
- **Purpose:** Relational proof tying a provider success to an intervention within a 72-hour window.
- **Columns:**

| Column Name | Data Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | **PK**. Evidence record identifier. |
| `intervention_id` | `VARCHAR(200)` | No | — | Associated attempt ID. |
| `provider_event_id` | `VARCHAR(200)` | No | — | External success webhook ID. |
| `failed_transaction_id` | `VARCHAR(200)` | No | — | Original failed transaction ID. |
| `successful_transaction_id`| `VARCHAR(200)` | No | — | New successful transaction ID. |
| `amount_minor` | `BIGINT` | No | — | Confirmed recovered minor units. |
| `currency` | `VARCHAR(3)` | No | — | ISO-4217 uppercase currency. |
| `verified_at` | `TIMESTAMPTZ` | No | — | Evidence verification timestamp. |
| `attribution_window_hours`| `INTEGER` | No | `72` | Allowed window threshold. |
| `attribution_reason` | `VARCHAR(200)` | No | — | Attribution justification string. |
| `attributable` | `BOOLEAN` | No | `FALSE` | Legitimate attribution flag. |
| `evidence_json` | `JSONB / JSON` | No | `'{}'` | Matching evidence details. |
| `created_at` | `TIMESTAMPTZ` | No | `NOW()` | Creation timestamp. |
| `updated_at` | `TIMESTAMPTZ` | No | `NOW()` | Update timestamp. |

- **Constraints & Indexes:**
  - `CONSTRAINT uq_recovery_evidence_provider_event UNIQUE (provider_event_id)`
  - `CONSTRAINT ck_recovery_evidence_amount_nonnegative CHECK (amount_minor >= 0)`
  - `CONSTRAINT ck_recovery_evidence_currency CHECK (length(currency) = 3 AND currency = upper(currency))`
  - `INDEX ix_recovery_evidence_failed_transaction (failed_transaction_id)`
- **Retention:** 7 years permanent.
