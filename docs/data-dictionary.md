# RevenueRescueAI — Comprehensive Data Dictionary
## Phase 1.2: Field-Level Definitions, Allowed Values, Data Types, and Examples

**Document Version:** 1.0.0  
**Status:** Approved Data Dictionary  
**Primary Authors:** Senior Database Architect, Data Quality Engineer  

---

## 1. Data Dictionary Conventions

1. **UUIDs:** Stored as native 128-bit RFC-4122 identifiers (rendered as canonical 36-character hexadecimal strings with hyphens).
2. **Minor Units:** Monetary amounts stored as non-negative integers (`amount_minor >= 0`). For example, $8,420.50 USD is `842050`.
3. **Currencies:** ISO-4217 exact 3-character uppercase codes (`USD`, `EUR`, `GBP`).
4. **Timestamps:** ISO-8601 UTC strings stored with timezone (`TIMESTAMPTZ`), e.g., `2026-10-30T12:04:11.450Z`.

---

## 2. Table-by-Table Field Specifications

### 2.1 Table: `customers`

| Column | Data Type | Nullable | Allowed Values / Format | Example Value | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | RFC-4122 UUIDv4 | `e9f8a3c1-4b72-4d9a-9e11-8201bfa82a10` | Unique primary key. |
| `provider` | `VARCHAR(64)` | No | `synthetic`, `stripe`, `adyen` | `synthetic` | Provider domain namespace. |
| `external_customer_id` | `VARCHAR(128)` | No | Non-empty alphanumeric string | `cus_sim_9A12F` | Merchant/gateway customer reference. |
| `email` | `VARCHAR(320)` | Yes | Valid email or masked string | `alex.m***@northstar.io` | Customer contact email. |
| `display_name` | `VARCHAR(200)` | Yes | Free text | `Northstar Labs, Inc.` | Customer or corporate entity name. |
| `status` | `VARCHAR(32)` | No | `active`, `inactive`, `restricted` | `active` | Customer account standing. |
| `metadata` | `JSONB` | No | Valid JSON Object | `{"cooling_off_until": null}` | Safe metadata attributes. |
| `created_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T10:00:00.000Z` | Account record creation time. |
| `updated_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:11.000Z` | Last account modification time. |

---

### 2.2 Table: `transactions`

| Column | Data Type | Nullable | Allowed Values / Format | Example Value | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | RFC-4122 UUIDv4 | `c4b19280-3e21-4f11-9a72-1084bce19401` | Unique primary key. |
| `customer_id` | `UUID` | No | Foreign key $\to$ `customers.id` | `e9f8a3c1-4b72-4d9a-9e11-8201bfa82a10` | Owning customer record. |
| `provider` | `VARCHAR(64)` | No | `synthetic`, `stripe`, `adyen` | `synthetic` | Gateway that processed transaction. |
| `external_transaction_id` | `VARCHAR(128)`| No | Non-empty alphanumeric string | `txn_sim_8F31A` | Provider charge or transaction ID. |
| `amount_minor` | `BIGINT` | No | Integer $\ge 0$ | `842000` | Financial amount in cents ($8,420.00). |
| `currency` | `VARCHAR(3)` | No | ISO-4217 uppercase 3-char | `USD` | Transaction currency. |
| `status` | `VARCHAR(32)` | No | `created`, `authorized`, `succeeded`, `failed`, `pending`, `cancelled`, `refunded`, `unknown` | `failed` | Payment gateway transaction status. |
| `failure_code` | `VARCHAR(100)`| Yes | Standardized decline string | `insufficient_funds` | Raw decline reason code. |
| `failure_message_safe` | `VARCHAR(500)`| Yes | Sanitized text string | `Card has insufficient funds.` | Customer/operator safe decline text. |
| `occurred_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:11.000Z` | Time transaction occurred on network. |
| `metadata` | `JSONB` | No | Valid JSON Object | `{"billing_reason": "renewal"}` | Technical transaction context. |
| `created_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:12.000Z` | Database record creation time. |
| `updated_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:12.000Z` | Last record update time. |

---

### 2.3 Table: `provider_webhook_events`

| Column | Data Type | Nullable | Allowed Values / Format | Example Value | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | RFC-4122 UUIDv4 | `a1122334-4455-6677-8899-aabbccddeeff` | Ingestion receipt ID. |
| `provider` | `VARCHAR(64)` | No | `synthetic`, `stripe` | `synthetic` | Originating gateway name. |
| `external_event_id` | `VARCHAR(200)`| No | Provider event string | `evt_sim_99812` | Provider webhook event identifier. |
| `event_type` | `VARCHAR(160)`| No | Dot-delimited event name | `payment_intent.payment_failed` | Inbound event topic. |
| `payload_hash` | `VARCHAR(128)`| No | 64-char hex SHA-256 digest | `e3b0c44298fc1c149afbf4c8996fb92...` | Cryptographic fingerprint of payload. |
| `signature_verified`| `BOOLEAN` | No | `TRUE`, `FALSE` | `TRUE` | HMAC check outcome. |
| `processed` | `BOOLEAN` | No | `TRUE`, `FALSE` | `TRUE` | Idempotency processing flag. |
| `payload_safe` | `JSONB` | No | Sanitized JSON | `{"amount": 842000, "code": "..."}` | Scrubbed event payload. |
| `created_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:11.200Z` | Webhook ingress arrival time. |
| `updated_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:11.850Z` | Processing completion time. |

---

### 2.4 Table: `recovery_cases`

| Column | Data Type | Nullable | Allowed Values / Format | Example Value | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | RFC-4122 UUIDv4 | `f7a28190-8812-4c22-b912-334455667788` | Unique case primary key. |
| `customer_id` | `UUID` | No | Foreign key $\to$ `customers.id` | `e9f8a3c1-4b72-4d9a-9e11-8201bfa82a10` | Account holder reference. |
| `trigger_transaction_id` | `UUID` | No | Foreign key $\to$ `transactions.id` | `c4b19280-3e21-4f11-9a72-1084bce19401` | Initial failed payment trigger. |
| `case_key` | `VARCHAR(200)`| No | Unique business string | `case_sim_8F31A_01` | Human/audit reference key. |
| `state` | `VARCHAR(40)` | No | `detected`, `analyzing`, `action_selected`, `action_pending`, `verification_pending`, `recovered`, `failed`, `escalated`, `terminated` | `action_pending` | Current FSM lifecycle state. |
| `priority` | `INTEGER` | No | Positive integer ($1 \dots 1000$) | `100` | Scheduling urgency priority. |
| `opened_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:12.000Z` | Case opening timestamp. |
| `last_state_changed_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:14.000Z` | Last FSM state update time. |
| `closed_at` | `TIMESTAMPTZ` | Yes | UTC Timestamp or `NULL` | `NULL` | Terminal state lock timestamp. |
| `version` | `INTEGER` | No | Positive integer $\ge 1$ | `2` | Optimistic concurrency version. |
| `metadata` | `JSONB` | No | Valid JSON Object | `{"risk_tier": "high", "attempts": 1}`| Case diagnostics and summary tags. |

---

### 2.5 Table: `recovery_attempts`

| Column | Data Type | Nullable | Allowed Values / Format | Example Value | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | RFC-4122 UUIDv4 | `11223344-5566-7788-99aa-bbccddeeff00` | Attempt primary key. |
| `case_id` | `UUID` | No | Foreign key $\to$ `recovery_cases.id` | `f7a28190-8812-4c22-b912-334455667788` | Owning recovery case. |
| `sequence_number`| `INTEGER` | No | Integer `1` or `2` | `1` | Sequential attempt counter. |
| `status` | `VARCHAR(32)` | No | `planned`, `started`, `succeeded`, `failed`, `uncertain`, `cancelled` | `succeeded` | Execution outcome status. |
| `action_type` | `VARCHAR(40)` | No | `retry_now`, `schedule_retry`, `request_payment_method_update`, `escalate_to_human`, `stop_recovery` | `retry_now` | Specific recovery tool invoked. |
| `started_at` | `TIMESTAMPTZ` | Yes | UTC Timestamp | `2026-10-30T12:04:14.100Z` | Time action was initiated. |
| `finished_at` | `TIMESTAMPTZ` | Yes | UTC Timestamp | `2026-10-30T12:04:18.400Z` | Time provider responded. |
| `outcome` | `VARCHAR(100)`| Yes | Provider outcome string | `succeeded` | Provider response category. |
| `provider_reference`| `VARCHAR(200)`| Yes | Gateway charge ID | `ch_sim_8F31_01` | Gateway transaction reference. |
| `idempotency_key`| `VARCHAR(250)`| No | Unique execution string | `rec_att_f7a28190_seq1` | Deduplication token sent to provider. |
| `error_class` | `VARCHAR(120)`| Yes | Error classification string | `NULL` | Canonical error class if failed. |
| `error_safe_message`| `VARCHAR(500)`| Yes | Sanitized text | `NULL` | Safe error message summary. |
| `metadata` | `JSONB` | No | Valid JSON Object | `{"latency_ms": 430}` | Execution diagnostics. |

---

### 2.6 Table: `agent_decisions`

| Column | Data Type | Nullable | Allowed Values / Format | Example Value | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | RFC-4122 UUIDv4 | `88776655-4433-2211-00ff-eeddccbbaa99` | Decision record ID. |
| `case_id` | `UUID` | No | Foreign key $\to$ `recovery_cases.id` | `f7a28190-8812-4c22-b912-334455667788` | Associated case. |
| `attempt_id` | `UUID` | Yes | Foreign key $\to$ `recovery_attempts.id` | `11223344-5566-7788-99aa-bbccddeeff00` | Attempt executed from decision. |
| `decision_version`| `INTEGER` | No | Positive integer | `1` | Schema version of decision contract. |
| `action_type` | `VARCHAR(40)` | No | Permitted action enum values | `retry_now` | Proposed action recommendation. |
| `reason_code` | `VARCHAR(120)`| No | Lowercase underscore string | `soft_decline_retry_eligible` | Machine-readable diagnosis code. |
| `rationale_safe`| `VARCHAR(2000)`| Yes | Clean natural language | `Soft decline on active account; retry allowed.` | Human-readable explanation. |
| `confidence` | `NUMERIC(4,3)`| Yes | Decimal between `0.000` and `1.000` | `0.940` | Model confidence estimate. |
| `raw_response_hash`| `VARCHAR(128)`| Yes | 64-char hex SHA-256 | `d41d8cd98f00b204e9800998ecf8427e...` | SHA-256 hash of raw model output. |
| `validation_status`| `VARCHAR(40)` | No | `not_validated`, `validated`, `overridden_by_policy`, `rejected_invalid_schema` | `validated` | Policy gate authorization result. |

---

### 2.7 Table: `audit_events`

| Column | Data Type | Nullable | Allowed Values / Format | Example Value | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | RFC-4122 UUIDv4 | `99887766-5544-3322-1100-ffeeddccbbaa` | Unique audit event ID. |
| `case_id` | `UUID` | No | Foreign key $\to$ `recovery_cases.id` | `f7a28190-8812-4c22-b912-334455667788` | Associated case. |
| `event_type` | `VARCHAR(120)`| No | Canonical event name string | `POLICY_EVALUATION` | Audit event classification. |
| `from_state` | `VARCHAR(40)` | Yes | `RecoveryCaseState` or `NULL` | `action_pending` | State before event. |
| `to_state` | `VARCHAR(40)` | Yes | `RecoveryCaseState` or `NULL` | `recovered` | State after event. |
| `actor_type` | `VARCHAR(32)` | No | `system`, `agent_policy`, `human_operator` | `agent_policy` | Actor that initiated event. |
| `actor_id` | `VARCHAR(200)`| Yes | Actor identity string | `policy_gate_v1` | Specific user ID or service name. |
| `correlation_id`| `VARCHAR(200)`| No | Correlation trace UUID | `corr_8f31_4492` | Distributed request trace ID. |
| `event_time` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:18.500Z` | Accurate event timestamp. |
| `payload_safe` | `JSONB` | No | Sanitized JSON | `{"action": "retry_now", "result": "ok"}` | Non-sensitive event metadata. |
| `sequence_number`| `INTEGER` | No | Monotonic integer $\ge 1$ | `5` | Strictly increasing sequence index. |

---

### 2.8 Table: `recovery_evidence`

| Column | Data Type | Nullable | Allowed Values / Format | Example Value | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | RFC-4122 UUIDv4 | `33445566-7788-99aa-bbcc-ddeeff001122` | Evidence record ID. |
| `intervention_id`| `VARCHAR(200)`| No | Unique attempt or action ID | `11223344-5566-7788-99aa-bbccddeeff00` | Triggering recovery attempt ID. |
| `provider_event_id`| `VARCHAR(200)`| No | Provider success webhook ID | `evt_sim_99815` | Succeeded payment event ID. |
| `failed_transaction_id`| `VARCHAR(200)`| No | Initial failed transaction ID | `txn_sim_8F31A` | Original failed transaction reference.|
| `successful_transaction_id`| `VARCHAR(200)`| No | New successful transaction ID| `txn_sim_8F31B` | Recovering transaction reference. |
| `amount_minor` | `BIGINT` | No | Integer $\ge 0$ | `842000` | Exact recovered amount ($8,420.00). |
| `currency` | `VARCHAR(3)` | No | ISO-4217 uppercase 3-char | `USD` | Recovered currency. |
| `verified_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:18.600Z` | Verification completion time. |
| `attribution_window_hours`| `INTEGER` | No | Positive integer | `72` | Configured window ceiling (hours). |
| `attribution_reason`| `VARCHAR(200)`| No | Justification text | `exact_match_successful_charge` | Proof justification string. |
| `attributable` | `BOOLEAN` | No | `TRUE`, `FALSE` | `TRUE` | Verified attribution verdict. |
| `evidence_json`| `JSONB` | No | Valid JSON Object | `{"charge_id": "ch_sim_8F31_01"}` | Raw verification handshake details. |
| `created_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:18.650Z` | Record insertion time. |
| `updated_at` | `TIMESTAMPTZ` | No | UTC Timestamp | `2026-10-30T12:04:18.650Z` | Last record update time. |
