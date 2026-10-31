# RevenueRescueAI — Complete Entity Catalogue
## Phase 1.2: Entity Definitions, Business Attributes, and MVP Scoping

**Document Version:** 1.0.0  
**Status:** Approved Entity Catalogue  
**Primary Authors:** Principal Database Architect, Senior Backend Engineer, Financial Systems Analyst  

---

## 1. Executive Summary & Catalogue Scope

The Entity Catalogue defines the complete set of entities required to implement the failed-payment revenue recovery lifecycle for RevenueRescueAI. 

Every entity is designed according to three fundamental rules:
1. **Single Business Purpose:** An entity exists to represent a distinct business reality, not a temporary programming convenience.
2. **Data Minimization:** No unnecessary PII, raw credit card PANs, or provider secrets are ever stored.
3. **Explicit Boundary Ownership:** Every entity belongs to a specific bounded context and aggregate root.

---

## 2. Accepted MVP Entities

### 2.1 Entity A: `Customer`
- **Business Purpose:** Represents the merchant's account holder / cardholder against whom recovery actions are evaluated.
- **Owning Context:** Payment Management Context.
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Internal globally unique identifier.
  - `provider` (String 64, Not Null, Default: `'synthetic'`): Payment provider domain namespace.
  - `external_customer_id` (String 128, Not Null): Merchant's or gateway's customer reference (e.g., `cus_sim_9A12`).
  - `email` (String 320, Nullable): Masked contact email for notification purposes.
  - `display_name` (String 200, Nullable): Fictional customer or corporate entity name.
  - `status` (Enum `CustomerStatus`, Not Null, Default: `ACTIVE`): Account standing (`ACTIVE`, `INACTIVE`, `RESTRICTED`).
  - `metadata` (JSON, Not Null, Default: `{}`): Non-indexed operational tags and cooling-off timestamps.
  - `created_at`, `updated_at` (TIMESTAMPTZ, Not Null): UTC audit timestamps.
- **Constraints:**
  - `UniqueConstraint("provider", "external_customer_id", name="uq_customer_provider_external")`
- **Invariants Enforced:** Inactive or restricted customers are ineligible for automated payment retries (Invariant INV-003).

---

### 2.2 Entity B: `Transaction` (Payment Record)
- **Business Purpose:** Represents an individual monetary transaction attempt reported by a payment provider.
- **Owning Context:** Payment Management Context.
- **Difference from Recovery Case:** A `Transaction` is a point-in-time financial event (e.g., "Charge of $84.20 failed at 12:04:11"). A `RecoveryCase` is the multi-day lifecycle workflow opened to resolve that failure.
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Internal transaction identifier.
  - `customer_id` (UUIDv4, Foreign Key $\to$ `customers.id`, Not Null): Owning customer.
  - `provider` (String 64, Not Null, Default: `'synthetic'`): Originating gateway.
  - `external_transaction_id` (String 128, Not Null): Provider's reference ID (e.g., `txn_sim_8F31`).
  - `amount_minor` (BIGINT, Not Null): Monetary value in integer minor units (cents).
  - `currency` (String 3, Not Null): ISO-4217 uppercase currency code (`USD`).
  - `status` (Enum `TransactionStatus`, Not Null): Current status (`CREATED`, `AUTHORIZED`, `SUCCEEDED`, `FAILED`, `PENDING`, `CANCELLED`, `REFUNDED`, `UNKNOWN`).
  - `failure_code` (String 100, Nullable): Raw provider decline string (e.g., `insufficient_funds`).
  - `failure_message_safe` (String 500, Nullable): Scrubbed, non-sensitive failure summary.
  - `occurred_at` (TIMESTAMPTZ, Not Null): Exact timestamp when event happened on provider network.
  - `metadata` (JSON, Not Null): Safe technical metadata.
- **Constraints:**
  - `CheckConstraint("amount_minor >= 0", name="ck_transaction_amount_nonnegative")`
  - `CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_transaction_currency")`
  - `UniqueConstraint("provider", "external_transaction_id", name="uq_transaction_provider_external")`
  - `Index("ix_transaction_status_occurred", "status", "occurred_at")`

---

### 2.3 Entity C: `ProviderWebhookEvent` (Payment Event Ingress)
- **Business Purpose:** Provides durable, idempotent capture of raw external webhook deliveries before processing.
- **Owning Context:** Payment Management Context.
- **Payload Sanitization Rule:** Raw JSON payloads are scrubbed of any raw PANs, CVVs, or authorization bearer headers before persistence. Only `payload_safe` is retained.
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Ingestion receipt identifier.
  - `provider` (String 64, Not Null): Originating provider (`synthetic`, `stripe`).
  - `external_event_id` (String 200, Not Null): Provider's unique webhook event ID (e.g., `evt_sim_0042`).
  - `event_type` (String 160, Not Null): Canonical event name (`payment_intent.payment_failed`).
  - `payload_hash` (String 128, Not Null): SHA-256 cryptographic digest of the received payload bytes.
  - `signature_verified` (Boolean, Not Null, Default: `False`): HMAC cryptographic check result.
  - `processed` (Boolean, Not Null, Default: `False`): Idempotency flag indicating downstream handling.
  - `payload_safe` (JSON, Not Null): Sanitized event dictionary.
  - `created_at`, `updated_at` (TIMESTAMPTZ, Not Null): Ingress timestamps.
- **Constraints:**
  - `UniqueConstraint("provider", "external_event_id", name="uq_provider_event")`

---

### 2.4 Entity D: `RecoveryCase` (Central Aggregate Root)
- **Business Purpose:** Coordinates the entire end-to-end recovery episode for an at-risk transaction.
- **Owning Context:** Recovery Case Management Context.
- **Cardinality Rule:** **One failed transaction has exactly ONE recovery case.** A new case cannot be opened for an already-active or terminal case (Invariant INV-004).
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Unique case identifier.
  - `customer_id` (UUIDv4, Foreign Key $\to$ `customers.id`, Not Null): Associated customer.
  - `trigger_transaction_id` (UUIDv4, Foreign Key $\to$ `transactions.id`, Not Null): Triggering payment.
  - `case_key` (String 200, Not Null): Deterministic business key (e.g., `case_sim_8F31_01`).
  - `state` (Enum `RecoveryCaseState`, Not Null, Default: `DETECTED`): FSM lifecycle state (`DETECTED`, `ANALYZING`, `ACTION_SELECTED`, `ACTION_PENDING`, `VERIFICATION_PENDING`, `RECOVERED`, `FAILED`, `ESCALATED`, `TERMINATED`).
  - `priority` (Integer, Not Null, Default: 100): Dynamic urgency rank (1 = highest urgency).
  - `opened_at` (TIMESTAMPTZ, Not Null): Timestamp when case was initialized.
  - `last_state_changed_at` (TIMESTAMPTZ, Not Null): Timestamp of most recent transition.
  - `closed_at` (TIMESTAMPTZ, Nullable): Timestamp when case reached terminal state.
  - `version` (Integer, Not Null, Default: 1): Optimistic locking concurrency counter.
  - `metadata` (JSON, Not Null): Contextual tags and diagnostic summaries.
- **Constraints:**
  - `UniqueConstraint("case_key", name="uq_recovery_case_key")`
  - `Index("ix_recovery_case_state_changed", "state", "last_state_changed_at")`
  - `Index("ix_recovery_case_customer", "customer_id")`

---

### 2.5 Entity E: `RecoveryAttempt` (Financial Execution Record)
- **Business Purpose:** Records an individual bounded action executed against a payment provider.
- **Owning Context:** Recovery Workflow Execution Context.
- **Lifecycle Distinctions:**
  1. *Action Requested:* Decision proposed by AI and authorized by Policy Gate.
  2. *Action Executed:* Request sent to payment provider with unique idempotency key.
  3. *Action Accepted:* Provider acknowledges receipt and returns a transaction reference.
  4. *Payment Confirmed:* Succeeded status received from provider.
  5. *Recovery Attributed:* Legitimate recovery proof verified in `RecoveryEvidence`.
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Attempt identifier.
  - `case_id` (UUIDv4, Foreign Key $\to$ `recovery_cases.id`, Not Null): Owning case.
  - `sequence_number` (Integer, Not Null): Sequential attempt counter for this case (`1` or `2`).
  - `status` (Enum `RecoveryAttemptStatus`, Not Null): (`PLANNED`, `STARTED`, `SUCCEEDED`, `FAILED`, `UNCERTAIN`, `CANCELLED`).
  - `action_type` (Enum `ActionType`, Not Null): (`RETRY_NOW`, `SCHEDULE_RETRY`, `REQUEST_PAYMENT_METHOD_UPDATE`, `ESCALATE_TO_HUMAN`, `STOP_RECOVERY`).
  - `started_at` (TIMESTAMPTZ, Nullable): Timestamp when HTTP call dispatched.
  - `finished_at` (TIMESTAMPTZ, Nullable): Timestamp when provider response received.
  - `outcome` (String 100, Nullable): Provider outcome classification (`succeeded`, `soft_decline`, `timeout`).
  - `provider_reference` (String 200, Nullable): Gateway charge ID (e.g., `ch_sim_9918`).
  - `idempotency_key` (String 250, Not Null): Unique deterministic execution token.
  - `error_class` (String 120, Nullable): Canonical error category on failure.
  - `error_safe_message` (String 500, Nullable): Scrubbed error description.
  - `metadata` (JSON, Not Null): Request and timing diagnostics.
- **Constraints:**
  - `UniqueConstraint("case_id", "sequence_number", name="uq_attempt_case_sequence")`
  - `UniqueConstraint("idempotency_key", name="uq_attempt_idempotency_key")`
  - `CheckConstraint("sequence_number >= 1 AND sequence_number <= 2", name="ck_attempt_sequence_budget")`

---

### 2.6 Entity F: `CaseStateTransition` (Workflow FSM History)
- **Business Purpose:** Provides a normalized, queryable record of every state transition in the case state machine.
- **Owning Context:** Recovery Case Management Context.
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Transition identifier.
  - `case_id` (UUIDv4, Foreign Key $\to$ `recovery_cases.id`, Not Null): Owning case.
  - `from_state` (Enum `RecoveryCaseState`, Nullable): Originating state (null for initial detection).
  - `to_state` (Enum `RecoveryCaseState`, Not Null): Target state.
  - `reason_code` (String 120, Not Null): Domain explanation (e.g., `soft_decline_retry_scheduled`).
  - `actor_type` (Enum `ActorType`, Not Null): (`SYSTEM`, `AGENT_POLICY`, `HUMAN_OPERATOR`).
  - `correlation_id` (String 200, Not Null): Distributed request trace ID.
  - `occurred_at` (TIMESTAMPTZ, Not Null): Transition timestamp.
  - `sequence_number` (Integer, Not Null): Monotonic sequence number for case.
  - `metadata` (JSON, Not Null): Diagnostic state snapshot.
- **Constraints:**
  - `UniqueConstraint("case_id", "sequence_number", name="uq_transition_case_sequence")`
  - `Index("ix_transition_case_occurred", "case_id", "occurred_at")`

---

### 2.7 Entity G: `AuditEvent` (Immutable Audit Ledger)
- **Business Purpose:** Permanent, append-only chronological log of all business, policy, and financial events.
- **Difference from Application Logs:** Application logs (via stdout) are ephemeral, debug-focused, and rotated out after 14 days. `AuditEvent` is a permanent, queryable relational table subject to financial audit.
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Unique audit record ID.
  - `case_id` (UUIDv4, Foreign Key $\to$ `recovery_cases.id`, Not Null): Associated case.
  - `event_type` (String 120, Not Null): Event category (`POLICY_EVALUATION`, `ATTEMPT_DISPATCHED`).
  - `from_state` (Enum `RecoveryCaseState`, Nullable): Pre-event state.
  - `to_state` (Enum `RecoveryCaseState`, Nullable): Post-event state.
  - `actor_type` (Enum `ActorType`, Not Null): Triggering entity.
  - `actor_id` (String 200, Nullable): User ID or system worker ID.
  - `correlation_id` (String 200, Not Null): End-to-end trace correlation ID.
  - `event_time` (TIMESTAMPTZ, Not Null): UTC event timestamp.
  - `payload_safe` (JSON, Not Null): Scrubbed, non-sensitive audit payload.
  - `sequence_number` (Integer, Not Null): Strictly increasing monotonic integer.
- **Constraints:**
  - `UniqueConstraint("case_id", "sequence_number", name="uq_audit_case_sequence")`
  - `Index("ix_audit_case_sequence", "case_id", "sequence_number")`

---

### 2.8 Entity H: `AgentDecision` (AI Intent Record)
- **Business Purpose:** Captures the recommendation produced by the AI Advisor and records whether the Deterministic Policy Gate approved, vetoed, or escalated it.
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Decision record ID.
  - `case_id` (UUIDv4, Foreign Key $\to$ `recovery_cases.id`, Not Null): Associated case.
  - `attempt_id` (UUIDv4, Foreign Key $\to$ `recovery_attempts.id`, Nullable): Linked attempt (if executed).
  - `decision_version` (Integer, Not Null, Default: 1): Schema version of decision contract.
  - `action_type` (Enum `ActionType`, Not Null): Proposed action.
  - `reason_code` (String 120, Not Null): Diagnostic code.
  - `rationale_safe` (String 2000, Nullable): Human-readable reasoning string.
  - `confidence` (Decimal(4, 3), Nullable): Confidence score between `0.000` and `1.000`.
  - `raw_response_hash` (String 128, Nullable): SHA-256 digest of LLM output for auditability.
  - `validation_status` (Enum `DecisionValidationStatus`, Not Null): (`NOT_VALIDATED`, `VALIDATED`, `OVERRIDDEN_BY_POLICY`, `REJECTED_INVALID_SCHEMA`).
- **Constraints:**
  - `CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_decision_confidence")`

---

### 2.9 Entity I: `RecoveryEvidence` (Verified Attribution Proof)
- **Business Purpose:** Legally and mathematically proves that a recovered payment was legitimately recovered by an intervention.
- **Attributes:**
  - `id` (UUIDv4, Primary Key): Evidence record ID.
  - `intervention_id` (String 200, Not Null): ID of the specific recovery attempt or action.
  - `provider_event_id` (String 200, Not Null): External ID of the successful payment event.
  - `failed_transaction_id` (String 200, Not Null): Original failed transaction ID.
  - `successful_transaction_id` (String 200, Not Null): New successful transaction ID.
  - `amount_minor` (BIGINT, Not Null): Exact recovered minor units.
  - `currency` (String 3, Not Null): ISO-4217 currency.
  - `verified_at` (TIMESTAMPTZ, Not Null): Timestamp of verification.
  - `attribution_window_hours` (Integer, Not Null, Default: 72): Time window ceiling.
  - `attribution_reason` (String 200, Not Null): Audit justification.
  - `attributable` (Boolean, Not Null, Default: `False`): Final attribution verdict.
  - `evidence_json` (JSON, Not Null): Matching evidence payload.
- **Constraints:**
  - `UniqueConstraint("provider_event_id", name="uq_recovery_evidence_provider_event")`
  - `CheckConstraint("amount_minor >= 0", name="ck_recovery_evidence_amount_nonnegative")`
  - `CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_recovery_evidence_currency")`

---

### 2.10 Entities J, K, L: Evaluation Subsystem (`EvaluationRun`, `EvaluationScenario`, `EvaluationResult`)
- **Business Purpose:** Manages offline batch benchmarks (500 scenarios, Seed 42).
- **Partitioning Rule:** Evaluation records are explicitly flagged `is_synthetic = True` and are never queried during production revenue reporting.

---

## 3. Evaluation of Deferred Entities (Scope Boundary Discipline)

| Candidate Entity | Decision | Detailed Rationale for Deferral |
| :--- | :--- | :--- |
| **`Subscription`** | **DEFERRED** | The MVP focuses on failed-payment recovery. Subscription lifecycle management (renewals, plan upgrades, downgrades) belongs to the merchant's billing system. Storing customer status and trigger transactions is sufficient. |
| **`Invoice`** | **DEFERRED** | An invoice is a billing artifact that groups line items. The payment gateway operates on `Transaction` objects. Adding `Invoice` introduces unnecessary data modeling complexity for the MVP. |
| **`Notification`** | **DEFERRED** | In the MVP, customer communication (e.g., card update requests) is emulated via dry-run tools and recorded in `agent_decisions` and `audit_events`. A dedicated outbound messaging queue is deferred to Phase 4. |
| **`RecoveryPolicy` (Table)** | **DEFERRED** | Invariants INV-001 through INV-016 are hardcoded deterministic Python rules in `app.policy.safety`. Storing policies in dynamic database tables introduces security risks (operators accidentally deleting safety constraints). |
| **`RetrySchedule` (Table)**| **DEFERRED** | Exponential backoff retry times are calculated dynamically and persisted directly in `recovery_attempts.scheduled_at`. A separate schedule table would be redundant. |
