# RevenueRescueAI — End-to-End Business Workflows
## Phase 1.4: Complete Lifecycle Walkthrough, Component Handshakes, and State Transitions

**Document Version:** 1.0.0  
**Status:** Approved Workflow Specification  
**Primary Authors:** Senior Software Architect, Systems Designer  

---

## 1. Executive Summary & Workflow Standard

The core mission of RevenueRescueAI is to execute a **bounded, safe, and verifiable recovery lifecycle**. 

This document details the complete 16-step end-to-end journey of an at-risk payment transaction, demonstrating how data moves across component boundaries, how decisions are authorized, and how states transition from initial detection to verified recovery.

---

## 2. Step-by-Step Complete Lifecycle Walkthrough

```
[ INGESTION & RISK ]
Step 1: Payment Failure Event Occurs
Step 2: Backend API Receives Event
Step 3: Event Payload Validated
Step 4: Duplicate Detection & Idempotency Check
Step 5: Revenue Risk Assessment Evaluated
Step 6: Recovery Case Initialized in Database

[ INTELLIGENCE & POLICY GOVERNANCE ]
Step 7: Case Context & Diagnosis Aggregated
Step 8: AI Recommendation Engine Generates Intent
Step 9: Deterministic Policy Gate Evaluates Invariants
Step 10: System Determines Permitted Execution Path

[ BOUNDED EXECUTION & VERIFICATION ]
Step 11: Approved Action Dispatched with Idempotency Key
Step 12: Payment Provider Simulator Processes Action
Step 13: Outcome Verification Service Proves Attribution (<72h)
Step 14: Case State Atomically Transitioned to RECOVERED
Step 15: Permanent Sequenced Audit Event Recorded
Step 16: Dashboard Authoritative Financial Metrics Updated
```

---

### Step 1: Payment Failure Event Occurs
- **Starting Component:** Payment Gateway / Payment Simulator.
- **Receiving Component:** Public Ingress Network (Reverse Proxy / TLS Terminator).
- **Data Exchanged:** HTTPS Webhook POST payload containing provider event ID, transaction ID, customer reference, `amount: 842000`, `currency: "usd"`, and decline code `insufficient_funds`.
- **Business Decision:** Originating gateway attempts renewal charge and fails due to temporary customer liquidity shortfall.
- **Database Changes:** None.
- **Possible Failure:** Network connection drop before reaching ingress.
- **Expected Next State:** Ingress delivery.

---

### Step 2: Backend API Receives Event
- **Starting Component:** Ingress Reverse Proxy.
- **Receiving Component:** FastAPI Application Gateway (`POST /api/v1/webhooks/provider`).
- **Data Exchanged:** Raw HTTP request bytes, `X-Signature-SHA256` header, and `X-Event-ID` header.
- **Business Decision:** Verify caller authenticity. Check HMAC signature using the shared secret and ensure timestamp is within 300 seconds (replay attack defense).
- **Database Changes:** None.
- **Possible Failure:** Invalid signature or expired timestamp $\to$ Rejects with `401 Unauthorized`.
- **Expected Next State:** Schema Validation.

---

### Step 3: Event Payload Validated
- **Starting Component:** FastAPI Gateway.
- **Receiving Component:** `PaymentEventValidator`.
- **Data Exchanged:** Parsed JSON payload dictionary.
- **Business Decision:** Enforce structural integrity via Pydantic v2 schemas: verify `amount_minor >= 0`, currency matches ISO-4217 (`USD`), and mandatory fields exist.
- **Database Changes:** None.
- **Possible Failure:** Negative amount or malformed JSON $\to$ Rejects with `422 Unprocessable Entity`.
- **Expected Next State:** Deduplication Check.

---

### Step 4: Duplicate Detection & Idempotency Check
- **Starting Component:** `PaymentEventValidator`.
- **Receiving Component:** `DuplicateEventDetector` (Idempotency Engine).
- **Data Exchanged:** `provider = 'synthetic'`, `external_event_id = 'evt_sim_99812'`, and SHA-256 payload digest.
- **Business Decision:** Query `provider_webhook_events` to check if this exact event was already ingested.
- **Database Changes:** If new $\to$ `INSERT INTO provider_webhook_events (processed=FALSE)`.
- **Possible Failure:** Duplicate event detected $\to$ Returns cached `200 OK` with `"duplicate": true` and safely drops downstream processing.
- **Expected Next State:** Risk Assessment.

---

### Step 5: Revenue Risk Assessment Evaluated
- **Starting Component:** Ingestion Subsystem.
- **Receiving Component:** `RiskAssessmentEngine`.
- **Data Exchanged:** Validated `PaymentEvent` and customer transaction profile.
- **Business Decision:** Classify event: failed payment on active account = `HIGH_RISK` at-risk revenue ($8,420.00). Check if customer is restricted (cooling-off period).
- **Database Changes:** None.
- **Possible Failure:** Customer restricted $\to$ Case moves directly to `ESCALATED` or `TERMINATED`.
- **Expected Next State:** Case Creation.

---

### Step 6: Recovery Case Initialized in Database
- **Starting Component:** `RiskAssessmentEngine`.
- **Receiving Component:** `RecoveryWorkflowEngine` (Relational Database).
- **Data Exchanged:** Validated payment parameters, customer reference, and trigger transaction reference.
- **Business Decision:** Open a new, distinct recovery case. Generate deterministic `case_key = "case_sim_8F31A_01"`.
- **Database Changes (Atomic Transaction):**
  - `INSERT INTO transactions` (`status = 'failed'`, `amount_minor = 842000`, `failure_code = 'insufficient_funds'`).
  - `INSERT INTO recovery_cases` (`state = 'DETECTED'`, `priority = 100`, `version = 1`).
  - `INSERT INTO case_state_transitions` (`from = NULL`, `to = 'DETECTED'`, `sequence_number = 1`).
  - `INSERT INTO audit_events` (`event_type = 'CASE_DETECTED'`, `sequence_number = 1`).
- **Possible Failure:** Duplicate case key $\to$ Unique constraint `uq_recovery_case_key` catches collision and aborts duplicate creation.
- **Expected Next State:** Failure Diagnosis & Analysis.

---

### Step 7: Case Context & Diagnosis Aggregated
- **Starting Component:** `RecoveryWorkflowEngine`.
- **Receiving Component:** `FailureDiagnosisEngine`.
- **Data Exchanged:** Raw decline code `insufficient_funds`, prior attempt count (0), customer tenure.
- **Business Decision:** Map raw decline into canonical failure category: `SOFT_DECLINE`, retryable = `TRUE`.
- **Database Changes:** `UPDATE recovery_cases SET state = 'ANALYZING'`; `INSERT INTO case_state_transitions (seq=2)`.
- **Possible Failure:** Unknown error code $\to$ Classified as `UNCERTAIN` and marked non-retryable without human review.
- **Expected Next State:** AI Recommendation Generation.

---

### Step 8: AI Recommendation Engine Generates Intent
- **Starting Component:** `FailureDiagnosisEngine`.
- **Receiving Component:** `AIRecommendationEngine` (Agent Brain).
- **Data Exchanged:** Anonymized diagnosis context (code: `soft_decline`, attempts: 0, customer score: 0.85).
- **Business Decision:** Formulate candidate recommendation: `RETRY_NOW` (confidence: 0.94, rationale: "Soft decline liquidity shortfall on high-value account; immediate retry eligible").
- **Database Changes:** `INSERT INTO agent_decisions` (`action_type = 'retry_now'`, `confidence = 0.940`, `validation_status = 'NOT_VALIDATED'`).
- **Possible Failure:** Model timeout (>3.0s) or invalid JSON $\to$ Falls back to `deterministic-logistic-v1`.
- **Expected Next State:** Policy Gate Check.

---

### Step 9: Deterministic Policy Gate Evaluates Invariants
- **Starting Component:** `AIRecommendationEngine`.
- **Receiving Component:** `DeterministicPolicyGate` (Safety Guardian).
- **Data Exchanged:** Proposed `AgentDecision`, case attempt count (0), customer cooling-off status.
- **Business Decision:** Evaluate hard safety invariants:
  - *INV-001 (Policy Supremacy):* Evaluates action against rules.
  - *INV-002 (Retry Budget):* Prior attempts (0) < Max retries (2) $\to$ **PASS**.
  - *INV-003 (Customer Restrictions):* Customer active and not cooling off $\to$ **PASS**.
  - *INV-004 (Terminal State Lock):* Case is active $\to$ **PASS**.
- **Database Changes:** `UPDATE agent_decisions SET validation_status = 'VALIDATED'`.
- **Possible Failure:** Invariant fails (e.g. attempt count = 2) $\to$ Policy overrides action and forces transition to `ESCALATED`.
- **Expected Next State:** Action Authorization.

---

### Step 10: System Determines Permitted Execution Path
- **Starting Component:** `DeterministicPolicyGate`.
- **Receiving Component:** `RecoveryWorkflowEngine`.
- **Data Exchanged:** Policy verdict: `ALLOWED`, approved action: `RETRY_NOW`.
- **Business Decision:** Transition case from `ANALYZING` to `ACTION_SELECTED`.
- **Database Changes (Atomic Transaction):**
  - `UPDATE recovery_cases SET state = 'ACTION_SELECTED'`, `version = 2`.
  - `INSERT INTO case_state_transitions` (`from = 'ANALYZING'`, `to = 'ACTION_SELECTED'`, `seq = 3`).
- **Possible Failure:** Optimistic locking collision $\to$ Retries transaction.
- **Expected Next State:** Execution Dispatch.

---

### Step 11: Approved Action Dispatched with Idempotency Key
- **Starting Component:** `RecoveryWorkflowEngine`.
- **Receiving Component:** `BoundedToolRegistry` (Two-Phase Planned Attempt Pattern).
- **Data Exchanged:** `case_id`, `amount_minor = 842000`, `currency = 'USD'`, `sequence_number = 1`.
- **Business Decision:** Generate deterministic `Idempotency-Key = "rec_att_case001_seq1"`. Record attempt in database before dispatching network call.
- **Database Changes (Phase 1 Commit):**
  - `INSERT INTO recovery_attempts` (`id = att_001`, `sequence_number = 1`, `status = 'STARTED'`, `idempotency_key = 'rec_att_case001_seq1'`).
  - `UPDATE recovery_cases SET state = 'ACTION_PENDING'`, `version = 3`.
  - `INSERT INTO case_state_transitions` (`from = 'ACTION_SELECTED'`, `to = 'ACTION_PENDING'`, `seq = 4`).
- **Possible Failure:** Server crashes immediately after commit $\to$ Recovery worker restarts, queries provider using idempotency key, and resumes cleanly.
- **Expected Next State:** Provider Execution.

---

### Step 12: Payment Provider Simulator Processes Action
- **Starting Component:** `BoundedToolRegistry`.
- **Receiving Component:** `PaymentProviderSimulator`.
- **Data Exchanged:** HTTPS POST `/v1/charges` with `amount = 842000`, `currency = 'USD'`, and `Idempotency-Key`.
- **Business Decision:** Simulator checks seed 42 schedule; cardholder funds verified; charge authorized and captured.
- **Database Changes:** Simulator logs charge creation (`ch_sim_8F31_01`).
- **Possible Failure:** 504 Timeout $\to$ Handled via Uncertain Outcome protocol (case moved to `VERIFICATION_PENDING`).
- **Expected Next State:** Outcome Verification.

---

### Step 13: Outcome Verification Service Proves Attribution (<72h)
- **Starting Component:** Tool Registry / Simulator Callback.
- **Receiving Component:** `OutcomeVerificationService`.
- **Data Exchanged:** Succeeded charge response (`charge_id = 'ch_sim_8F31_01'`, `amount = 842000`, `event_id = 'evt_sim_99815'`).
- **Business Decision:** Validate attribution invariants:
  1. Amount matches failed transaction ($8,420.00 == $8,420.00).
  2. Customer ID matches.
  3. Elapsed time is 4 seconds ($<72$ hours).
- **Database Changes:** `INSERT INTO recovery_evidence` (`provider_event_id = 'evt_sim_99815'`, `amount_minor = 842000`, `attributable = TRUE`).
- **Possible Failure:** Amount mismatch $\to$ Attribution denied; flagged for human investigation.
- **Expected Next State:** Case Closure & Lock.

---

### Step 14: Case State Atomically Transitioned to RECOVERED
- **Starting Component:** `OutcomeVerificationService`.
- **Receiving Component:** `RecoveryWorkflowEngine`.
- **Data Exchanged:** Verified evidence confirmation.
- **Business Decision:** Lock case as terminal `RECOVERED` under Invariant INV-004.
- **Database Changes (Atomic Transaction):**
  - `UPDATE recovery_attempts SET status = 'SUCCEEDED'`, `provider_reference = 'ch_sim_8F31_01'`.
  - `UPDATE recovery_cases SET state = 'RECOVERED'`, `closed_at = NOW()`, `version = 4`.
  - `INSERT INTO case_state_transitions` (`from = 'ACTION_PENDING'`, `to = 'RECOVERED'`, `seq = 5`).
- **Possible Failure:** Database connection drop $\to$ Handled via transaction rollback and retry.
- **Expected Next State:** Audit Logging.

---

### Step 15: Permanent Sequenced Audit Event Recorded
- **Starting Component:** `RecoveryWorkflowEngine`.
- **Receiving Component:** `AuditService`.
- **Data Exchanged:** Audit payload (event: `CASE_RECOVERED`, sequence: 5, amount: 842000).
- **Business Decision:** Commit immutable audit row.
- **Database Changes:** `INSERT INTO audit_events` (`case_id = case_001`, `event_type = 'CASE_RECOVERED'`, `sequence_number = 5`).
- **Possible Failure:** Write constraint violation $\to$ Transaction rolled back.
- **Expected Next State:** Realtime Broadcast & Dashboard Refresh.

---

### Step 16: Dashboard Authoritative Financial Metrics Updated
- **Starting Component:** Backend Observability / WebSocket Hub.
- **Receiving Component:** Operator React Dashboard (`/overview`).
- **Data Exchanged:** WSS frame `recovery.payment_recovered` ($8,420.00).
- **Business Decision:** Frontend receives live event, updates Command Center table row, and invalidates metrics cache.
- **Database Changes:** None. Next `GET /api/v1/dashboard/metrics` reflects +$8,420.00 in `recovered_revenue_minor`.
- **Result:** **Workflow Lifecycle Complete.** Zero financial discrepancies. 100% auditable proof.
