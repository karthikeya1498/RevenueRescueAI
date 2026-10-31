# RevenueRescueAI — Functional Requirements Specification

> **Document ID:** DOC-FR-004  
> **Phase:** 0.2 (User Stories, Functional Requirements & Acceptance Criteria)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

This document establishes the detailed Functional Requirements Specification (FRS) for RevenueRescueAI. While user stories capture capabilities from the perspective of user personas, functional requirements define the precise, deterministic system behaviors, inputs, outputs, preconditions, algorithms, and error responses required by software engineers and QA testers to build and verify the system.

Every functional requirement is uniquely identified (e.g., `FR-ING-001`), prioritized via MoSCoW, mapped to its parent user story and business rules, and provided with explicit verification criteria.

---

## 2. Functional Requirements Index

| Requirement ID | Module / Domain | Requirement Name | Priority |
|---|---|---|:---:|
| **FR-ING-001** | Ingestion | HTTP Webhook Listener Endpoint | **MUST** |
| **FR-ING-002** | Ingestion | HMAC-SHA256 Cryptographic Signature Verification | **MUST** |
| **FR-ING-003** | Ingestion | Webhook Payload Schema Validation | **MUST** |
| **FR-ING-004** | Ingestion | Inbound Idempotency & Replay Protection | **MUST** |
| **FR-DET-001** | Detection | Payment Failure Event Correlation | **MUST** |
| **FR-DET-002** | Detection | Recovery Case Instantiation & State Initialization | **MUST** |
| **FR-QNT-001** | Quantification | 64-Bit Integer Minor-Unit Currency Representation | **MUST** |
| **FR-QNT-002** | Quantification | ISO-4217 Currency Validation & Rejection | **MUST** |
| **FR-ELG-001** | Eligibility | Multi-Factor Recovery Eligibility Pre-screening | **MUST** |
| **FR-ELG-002** | Eligibility | Pre-Execution Success Protection Invariant | **MUST** |
| **FR-ELG-003** | Eligibility | Recovery Window Expiration (14-Day Cutoff) | **MUST** |
| **FR-CLS-001** | Classification | Standardized Failure Taxonomy Normalization | **MUST** |
| **FR-CLS-002** | Classification | Binary Decline Severity Tagging (Soft vs. Hard) | **MUST** |
| **FR-INT-001** | Intelligence | Allow-Listed Intervention Proposal Generation | **MUST** |
| **FR-INT-002** | Intelligence | Liquidity & Time-of-Day Retry Scheduling Heuristic | **MUST** |
| **FR-INT-003** | Intelligence | Explainable Rationale & Confidence Score Generation | **MUST** |
| **FR-INT-004** | Intelligence | Deterministic Rule Fallback on Model Failure | **MUST** |
| **FR-POL-001** | Policy Gate | Deterministic Code Policy Gate Evaluation | **MUST** |
| **FR-POL-002** | Policy Gate | Absolute Veto Enforcement on Policy Rejection | **MUST** |
| **FR-POL-003** | Policy Gate | Terminal Decline Prohibition (Hard Decline Gate) | **MUST** |
| **FR-WFK-001** | Workflow | Finite State Machine Transitions & Validation | **MUST** |
| **FR-WFK-002** | Workflow | Bounded Tool Execution Boundary via Simulator | **MUST** |
| **FR-IDP-001** | Idempotency | Action-Level Idempotency Token Generation | **MUST** |
| **FR-STP-001** | Stopping Rules | Hard Retry Budget Ceiling Enforcement (<= 3 Attempts)| **MUST** |
| **FR-STP-002** | Stopping Rules | Immediate Workflow Halting on Confirmed Recovery | **MUST** |
| **FR-STP-003** | Escalation | High-Value Exposure Escalation Threshold (>= $1,000)| **MUST** |
| **FR-VRF-001** | Verification | Authoritative Gateway Settlement Verification | **MUST** |
| **FR-VRF-002** | Verification | Three-Valued Uncertainty Handling on Timeout | **MUST** |
| **FR-VRF-003** | Verification | 72-Hour Attribution Window Enforcement | **MUST** |
| **FR-AUD-001** | Audit | Append-Only Structured Audit Event Persistence | **MUST** |
| **FR-AUD-002** | Audit | Correlation ID Trace Retrieval API | **MUST** |
| **FR-DSH-001** | UI / API | Real-Time Financial Metric Aggregation Endpoint | **MUST** |
| **FR-DSH-002** | UI / API | Recovery Case Queue Listing with Pagination & Filters | **MUST** |
| **FR-DSH-003** | UI / API | Case Diagnostic Trace & Audit Timeline Endpoint | **MUST** |
| **FR-EVL-001** | Evaluation | Deterministic 500-Scenario Batch Evaluation Harness | **MUST** |
| **FR-EVL-002** | Evaluation | Counterfactual Baseline Comparison Execution | **MUST** |
| **FR-EVL-003** | Evaluation | Serialized Evaluation Report Artifact Generation | **MUST** |

---

## 3. Detailed Functional Requirements Specifications

---

### Ingestion & Perimeter Boundary

#### FR-ING-001: HTTP Webhook Listener Endpoint
- **Description:** The system shall expose an HTTP endpoint `POST /api/v1/webhooks/gateway` capable of receiving asynchronous JSON payloads from payment provider simulators.
- **Business Justification:** Real-time event ingestion is required to detect payment failures the instant they occur.
- **Priority:** **MUST**
- **Input:** HTTP POST request with headers (including `x-signature`, `content-type: application/json`) and JSON body.
- **Expected Output:** HTTP 200 OK with JSON confirmation `{ "status": "acknowledged", "event_id": "evt_..." }` or appropriate 4xx/5xx error.
- **Preconditions:** Service is listening on configured network port.
- **Main Behavior:** Receives payload, captures raw bytes, extracts signature header, passes raw stream to cryptographic verifier, and returns response within 500ms.
- **Error Behavior:** If payload is not valid JSON, returns HTTP 400 Bad Request.
- **Related User Stories:** US-ING-001
- **Business Rules:** BR-004, BR-006
- **Acceptance Criteria:** US-ING-001 Scenario
- **Verification Method:** Automated HTTP integration test firing synthetic webhooks.

---

#### FR-ING-002: HMAC-SHA256 Cryptographic Signature Verification
- **Description:** The system shall verify the cryptographic signature of every incoming webhook using HMAC-SHA256 and the shared secret configured in application settings.
- **Business Justification:** Prevents injection of fabricated financial events and unauthorized debt creation.
- **Priority:** **MUST**
- **Input:** Inbound raw body bytes and `x-signature` header value.
- **Expected Output:** Boolean `True` if signature matches; throws `AuthenticationError` if signature is missing or mismatched.
- **Preconditions:** Webhook secret key is loaded in memory.
- **Main Behavior:** Computes HMAC-SHA256 digest of raw body bytes using configured secret; compares computed digest against header using constant-time comparison `hmac.compare_digest`.
- **Error Behavior:** Emits security log with IP address and returns HTTP 401 Unauthorized immediately.
- **Related User Stories:** US-ING-002
- **Business Rules:** BR-006
- **Acceptance Criteria:** US-ING-002 Scenario
- **Verification Method:** Unit test passing tampered, expired, and valid signatures.

---

#### FR-ING-003: Webhook Payload Schema Validation
- **Description:** The system shall validate inbound event payloads against a strict Pydantic model enforcing required fields: `id` (str), `event_type` (str), `amount` (int), `currency` (str, 3-char ISO), `customer_id` (str), and `timestamp` (ISO-8601 str).
- **Business Justification:** Eliminates malformed inputs and prevents runtime null-pointer exceptions.
- **Priority:** **MUST**
- **Input:** Deserialized JSON dictionary.
- **Expected Output:** Validated `PaymentEvent` object.
- **Preconditions:** Cryptographic signature verified.
- **Main Behavior:** Evaluates types, constraints, and presence of mandatory attributes.
- **Error Behavior:** Returns HTTP 400 Bad Request with structured array of validation errors detailing missing or ill-typed fields.
- **Related User Stories:** US-ING-003
- **Business Rules:** BR-008
- **Acceptance Criteria:** US-ING-003 Scenario
- **Verification Method:** Automated schema fuzzing tests with omitted and malformed fields.

---

#### FR-ING-004: Inbound Idempotency & Replay Protection
- **Description:** The system shall check whether an incoming `event_id` has already been recorded in the database idempotency ledger prior to initiating processing.
- **Business Justification:** Prevents payment gateways from triggering duplicate workflows upon network retry.
- **Priority:** **MUST**
- **Input:** String `event_id` from validated payload.
- **Expected Output:** Boolean indicator of whether event is unique or duplicate.
- **Preconditions:** Database connection active.
- **Main Behavior:** Queries unique index on `processed_events.event_id`. If record exists, logs duplicate detection and returns HTTP 200 OK `{ "status": "duplicate_acknowledged" }` without secondary case creation.
- **Error Behavior:** Database constraint violation on concurrent insertion handled gracefully by catching duplicate key exception.
- **Related User Stories:** US-ING-004
- **Business Rules:** BR-004, BR-006
- **Acceptance Criteria:** US-ING-004 Scenario
- **Verification Method:** Integration test replaying identical event payloads in sequence and in parallel.

---

### Detection & Risk Quantification

#### FR-DET-001: Payment Failure Event Correlation
- **Description:** The system shall inspect incoming events of type `payment.failed`, `invoice.payment_failed`, and `payment.stale_pending` and correlate them with existing customer and invoice records.
- **Business Justification:** Ensures financial events are bound to customer debt records.
- **Priority:** **MUST**
- **Input:** Validated `PaymentEvent`.
- **Expected Output:** Correlated references: `customer_id`, `invoice_id`, `payment_reference`.
- **Preconditions:** Event is unique and authenticated.
- **Main Behavior:** Queries customer repository and invoice table; binds entities to new or active case.
- **Error Behavior:** If invoice or customer does not exist, instantiates a synthetic external reference profile to allow tracking.
- **Related User Stories:** US-RSK-001
- **Business Rules:** BR-011
- **Acceptance Criteria:** US-RSK-001 Scenario
- **Verification Method:** Unit test verifying entity binding.

---

#### FR-DET-002: Recovery Case Instantiation & State Initialization
- **Description:** The system shall create an authoritative `RecoveryCase` record in the database for each unique unrecovered failure event, initializing state to `DETECTED`.
- **Business Justification:** Core stateful entity required for all subsequent workflow orchestration.
- **Priority:** **MUST**
- **Input:** Correlated event entities.
- **Expected Output:** Persisted `RecoveryCase` with unique UUID `case_id`, attempt counter = 0, state = `DETECTED`, and creation timestamp.
- **Preconditions:** Database transaction open.
- **Main Behavior:** Inserts case record and creates initial audit record `CASE_DETECTED` within a single atomic database transaction.
- **Error Behavior:** Rolls back transaction if database write fails.
- **Related User Stories:** US-RSK-001
- **Business Rules:** BR-012, BR-015
- **Acceptance Criteria:** US-RSK-001 Scenario
- **Verification Method:** Database state assertion post-ingestion.

---

#### FR-QNT-001: 64-Bit Integer Minor-Unit Currency Representation
- **Description:** The system shall store and compute all monetary values strictly as 64-bit signed integers representing the currency's smallest minor unit (e.g., cents for USD, paise for INR).
- **Business Justification:** Eliminates floating-point rounding errors and satisfies financial accounting standards.
- **Priority:** **MUST**
- **Input:** Nominal amount from event payload.
- **Expected Output:** 64-bit integer minor units (e.g., `$45.00` -> `4500`).
- **Preconditions:** Currency decimal factor known.
- **Main Behavior:** Multiplies nominal decimal by $10^{\text{decimals}}$ using decimal arithmetic, casts to integer, and stores in `BigInteger` column.
- **Error Behavior:** Rejects floating-point fractions of minor units (e.g., 4500.5 cents) as invalid input.
- **Related User Stories:** US-RSK-002
- **Business Rules:** BR-008
- **Acceptance Criteria:** US-RSK-002 Scenario
- **Verification Method:** Static analysis assertion verifying zero `Float` column types in database models.

---

#### FR-QNT-002: ISO-4217 Currency Validation & Rejection
- **Description:** The system shall validate that transaction currencies match supported three-letter ISO-4217 codes (`USD`, `INR`, `EUR`, `GBP`) and reject negative or zero values.
- **Business Justification:** Prevents multi-currency confusion and invalid zero-dollar transactions.
- **Priority:** **MUST**
- **Input:** Currency string and integer amount.
- **Expected Output:** Validated currency code.
- **Preconditions:** None.
- **Main Behavior:** Checks currency against uppercase ISO enum; checks amount > 0.
- **Error Behavior:** Throws `InvalidCurrencyException` or `InvalidAmountException` and rejects case creation.
- **Related User Stories:** US-RSK-002
- **Business Rules:** BR-008
- **Acceptance Criteria:** US-RSK-002 Scenario
- **Verification Method:** Unit tests passing invalid currency codes and negative amounts.

---

### Eligibility Pre-screening

#### FR-ELG-001: Multi-Factor Recovery Eligibility Pre-screening
- **Description:** The system shall evaluate newly detected cases against eligibility criteria: customer account active, invoice age <= 14 days, zero active disputes, customer not opted out, and invoice unpaid.
- **Business Justification:** Ensures automated recovery efforts are focused strictly on recoverable, legally permitted transactions.
- **Priority:** **MUST**
- **Input:** `RecoveryCase` and customer metadata.
- **Expected Output:** Transition to `ELIGIBLE` or `INELIGIBLE` with reason code.
- **Preconditions:** Case is in state `DETECTED`.
- **Main Behavior:** Evaluates boolean rules sequentially; if all pass, sets state to `ELIGIBLE`.
- **Error Behavior:** If any check fails, sets state to `INELIGIBLE_{REASON}` and logs audit event.
- **Related User Stories:** US-ELG-001
- **Business Rules:** BR-001, BR-005, BR-013
- **Acceptance Criteria:** US-ELG-001 Scenario
- **Verification Method:** Parametric unit tests exercising all eligibility branches.

---

#### FR-ELG-002: Pre-Execution Success Protection Invariant
- **Description:** The system shall verify that an invoice has not already succeeded or settled prior to approving or executing any recovery action.
- **Business Justification:** Core financial safety rule: strictly prevents duplicate customer debits.
- **Priority:** **MUST**
- **Input:** `invoice_id`.
- **Expected Output:** Settlement boolean flag.
- **Preconditions:** Invoked immediately prior to policy evaluation and prior to tool execution.
- **Main Behavior:** Queries authoritative invoice ledger; if invoice status is `PAID` or `SETTLED`, transitions case to `RESOLVED_ALREADY_PAID` and cancels workflow.
- **Error Behavior:** Any scheduled or pending actions are permanently aborted.
- **Related User Stories:** US-ELG-002
- **Business Rules:** BR-001
- **Acceptance Criteria:** US-ELG-002 Scenario
- **Verification Method:** Test scenario triggering recovery on pre-settled invoice.

---

#### FR-ELG-003: Recovery Window Expiration (14-Day Cutoff)
- **Description:** The system shall evaluate case age against the maximum recovery window of 14 calendar days (336 hours) from the initial failure timestamp.
- **Business Justification:** Prevents stale, surprise charges on customers weeks or months later.
- **Priority:** **MUST**
- **Input:** Case creation timestamp and current time (via Virtual Clock).
- **Expected Output:** Boolean expiration status.
- **Preconditions:** Case in state `ELIGIBLE` or `RETRY_SCHEDULED`.
- **Main Behavior:** If $(t_{\text{current}} - t_{\text{initial\_failure}}) > 14\text{ days}$, transitions case to `HALTED_EXPIRED`.
- **Error Behavior:** Scheduled retry is canceled and case is closed.
- **Related User Stories:** US-ELG-003
- **Business Rules:** BR-005
- **Acceptance Criteria:** US-ELG-003 Scenario
- **Verification Method:** Time-travel test advancing virtual clock past 14 days.

---

### Failure Classification & Diagnostic Intelligence

#### FR-CLS-001: Standardized Failure Taxonomy Normalization
- **Description:** The system shall map raw payment gateway error codes into a normalized failure taxonomy: `SOFT_DECLINE_TEMPORARY_BALANCE`, `SOFT_DECLINE_TECHNICAL`, `HARD_DECLINE_STOLEN_CARD`, `HARD_DECLINE_ACCOUNT_CLOSED`, `TRANSIENT_TIMEOUT`, or `UNKNOWN_DECLINE`.
- **Business Justification:** Provides consistent diagnostic inputs to the recommendation engine regardless of which gateway emitted the failure.
- **Priority:** **MUST**
- **Input:** Raw decline code and raw decline message.
- **Expected Output:** Normalized failure class enum.
- **Preconditions:** Raw code extracted from webhook.
- **Main Behavior:** Evaluates deterministic mapping rules; attaches failure classification to case.
- **Error Behavior:** Unmapped codes default to `UNKNOWN_DECLINE` with review flag.
- **Related User Stories:** US-RSK-003
- **Business Rules:** BR-002
- **Acceptance Criteria:** US-RSK-003 Scenario
- **Verification Method:** Unit test verifying table mapping across 50 raw gateway codes.

---

#### FR-CLS-002: Binary Decline Severity Tagging (Soft vs. Hard)
- **Description:** The system shall explicitly tag every classified failure with a binary severity flag: `SOFT` (potentially recoverable via retry) or `HARD` (strictly unrecoverable via retry).
- **Business Justification:** Provides hard boolean constraint for policy enforcement.
- **Priority:** **MUST**
- **Input:** Normalized failure class.
- **Expected Output:** `DeclineSeverity: SOFT | HARD`.
- **Preconditions:** Classification complete.
- **Main Behavior:** Stolen card, lost card, fraudulent card, and account closed are tagged `HARD`. Balance, network, and processor errors are tagged `SOFT`.
- **Error Behavior:** None.
- **Related User Stories:** US-RSK-003, US-POL-003
- **Business Rules:** BR-002
- **Acceptance Criteria:** US-RSK-003 Scenario
- **Verification Method:** Assertion tests across all taxonomy members.

---

#### FR-INT-001: Allow-Listed Intervention Proposal Generation
- **Description:** The Decision Engine shall analyze case context and recommend an action strictly restricted to the allow-listed taxonomy: `RETRY_PAYMENT`, `SCHEDULE_RETRY`, `SEND_PAYMENT_UPDATE_LINK`, `ESCALATE_TO_HUMAN`, or `HALT_RECOVERY`.
- **Business Justification:** Constrains AI agent to pre-approved, safe operational envelopes.
- **Priority:** **MUST**
- **Input:** Case context (amount, failure class, attempt count, customer tenure, time-of-day).
- **Expected Output:** Typed `InterventionProposal` object.
- **Preconditions:** Case is `ELIGIBLE`.
- **Main Behavior:** Formulates recommendation prompt or calls statistical estimator; validates output against Action Enum.
- **Error Behavior:** If model proposes unauthorized action name, parser rejects it and invokes fallback rule.
- **Related User Stories:** US-INT-001
- **Business Rules:** BR-009, BR-010
- **Acceptance Criteria:** US-INT-001 Scenario
- **Verification Method:** Unit test asserting output type adheres strictly to enum.

---

#### FR-INT-002: Liquidity & Time-of-Day Retry Scheduling Heuristic
- **Description:** When recommending `SCHEDULE_RETRY` for balance-related soft declines, the Decision Engine shall apply a scheduling delay (e.g., 48 to 72 hours, targeting morning business hours 09:00 AM) to maximize liquidity capture probability.
- **Business Justification:** Avoids immediate re-decline and captures end-of-week or month payroll deposits.
- **Priority:** **MUST**
- **Input:** Case failure class and timestamp.
- **Expected Output:** `scheduled_execution_time` timestamp.
- **Preconditions:** Action is `SCHEDULE_RETRY`.
- **Main Behavior:** Calculates target timestamp ensuring backoff >= 24 hours.
- **Error Behavior:** None.
- **Related User Stories:** US-INT-001
- **Business Rules:** BR-004
- **Acceptance Criteria:** US-INT-001 Scenario
- **Verification Method:** Timing calculation test on Friday evening failure cases.

---

#### FR-INT-003: Explainable Rationale & Confidence Score Generation
- **Description:** The Decision Engine shall attach a human-readable text explanation (rationale) and a numeric confidence score (0.00 to 1.00) to every generated proposal.
- **Business Justification:** Guarantees transparency and enables operators to audit AI reasoning.
- **Priority:** **MUST**
- **Input:** Context and model inference result.
- **Expected Output:** String `rationale` and float `confidence`.
- **Preconditions:** Proposal created.
- **Main Behavior:** Serializes reasoning into case proposal model.
- **Error Behavior:** Missing rationale triggers validation error.
- **Related User Stories:** US-INT-002
- **Business Rules:** BR-012
- **Acceptance Criteria:** US-INT-002 Scenario
- **Verification Method:** Assertion that `len(rationale) > 0` and `0.0 <= confidence <= 1.0`.

---

#### FR-INT-004: Deterministic Rule Fallback on Model Failure
- **Description:** If the AI reasoning service times out (> 3000ms), returns HTTP 5xx, or outputs invalid JSON, the system shall catch the exception and fall back to a deterministic rule without crashing.
- **Business Justification:** Ensures high platform availability regardless of external AI infrastructure status.
- **Priority:** **MUST**
- **Input:** Case context and caught exception.
- **Expected Output:** Standard deterministic proposal tagged `source: "FALLBACK_RULE"`.
- **Preconditions:** AI model failure caught.
- **Main Behavior:** Applies default rule: soft declines receive 48-hour retry; hard declines halt.
- **Error Behavior:** Logs warning event `MODEL_FALLBACK_APPLIED`.
- **Related User Stories:** US-INT-003
- **Business Rules:** BR-010
- **Acceptance Criteria:** US-INT-003 Scenario
- **Verification Method:** Chaos test injecting artificial model timeout.

---

### Policy Gate & Safety Enforcement

#### FR-POL-001: Deterministic Code Policy Gate Evaluation
- **Description:** The system shall pass every `InterventionProposal` through a deterministic Python policy gate that authoritatively evaluates business rules, retry limits, and safety invariants.
- **Business Justification:** Ensures code, not AI, holds absolute authorization authority.
- **Priority:** **MUST**
- **Input:** `InterventionProposal` and `RecoveryCase`.
- **Expected Output:** `PolicyDecision(status="APPROVED" | "REJECTED", reason="...")`.
- **Preconditions:** Proposal received.
- **Main Behavior:** Evaluates boolean rules sequentially in pure Python. If all pass, returns `APPROVED`.
- **Error Behavior:** If any rule fails, returns `REJECTED` with specific failure reason code.
- **Related User Stories:** US-POL-001, US-POL-002
- **Business Rules:** BR-001, BR-002, BR-003, BR-004, BR-010
- **Acceptance Criteria:** US-POL-001 Scenario
- **Verification Method:** Comprehensive policy test matrix exercising all rule combinations.

---

#### FR-POL-002: Absolute Veto Enforcement on Policy Rejection
- **Description:** When the Policy Gate emits `PolicyDecision: REJECTED`, the Workflow Engine shall immediately abort action dispatch, transition case to `HALTED` or `ESCALATED`, and log the rejection.
- **Business Justification:** Prevents unauthorized actions from ever reaching payment provider tools.
- **Priority:** **MUST**
- **Input:** Rejected `PolicyDecision`.
- **Expected Output:** Action execution blocked; case state updated.
- **Preconditions:** Policy rejected.
- **Main Behavior:** Halts workflow; throws `PolicyVetoException` if tool execution is attempted.
- **Error Behavior:** None.
- **Related User Stories:** US-POL-002
- **Business Rules:** BR-006, BR-010
- **Acceptance Criteria:** US-POL-002 Scenario
- **Verification Method:** Negative integration test verifying zero API calls dispatched on veto.

---

#### FR-POL-003: Terminal Decline Prohibition (Hard Decline Gate)
- **Description:** The Policy Gate shall reject any payment retry proposal where the case decline severity is `HARD`.
- **Business Justification:** Eliminates fines and sanctions from card networks (Visa/Mastercard).
- **Priority:** **MUST**
- **Input:** Case failure severity and proposed action.
- **Expected Output:** `PolicyDecision(status="REJECTED", reason="HARD_DECLINE_PROHIBITED")`.
- **Preconditions:** Proposed action involves payment retry.
- **Main Behavior:** Blocks retry; transitions case to `HALTED_TERMINAL_DECLINE`.
- **Error Behavior:** None.
- **Related User Stories:** US-POL-003
- **Business Rules:** BR-002
- **Acceptance Criteria:** US-POL-003 Scenario
- **Verification Method:** Unit test asserting rejection of retry proposals on stolen card cases.

---

### Workflow Orchestration & Tool Boundary

#### FR-WFK-001: Finite State Machine Transitions & Validation
- **Description:** The system shall enforce legal transitions across the defined recovery state machine: `DETECTED` -> `VALIDATING` -> `ELIGIBILITY_CHECK` -> `DIAGNOSING` -> `ACTION_PENDING` -> `POLICY_APPROVED` -> `ACTION_EXECUTING` -> `WAITING_FOR_VERIFICATION` -> `RECOVERED` | `FAILED` | `RETRY_SCHEDULED` | `VERIFICATION_PENDING` | `ESCALATED` | `CLOSED`.
- **Business Justification:** Guarantees workflow determinism and eliminates illegal state transitions.
- **Priority:** **MUST**
- **Input:** Current state and target state.
- **Expected Output:** State updated atomically in database.
- **Preconditions:** Transition is in legal transition matrix.
- **Main Behavior:** Verifies target state is permitted from current state; updates database column.
- **Error Behavior:** If transition is illegal, throws `InvalidStateTransitionException` and rolls back.
- **Related User Stories:** US-WFK-001
- **Business Rules:** BR-004, BR-015
- **Acceptance Criteria:** US-WFK-001 Scenario
- **Verification Method:** State machine unit tests exercising all legal and illegal transitions.

---

#### FR-WFK-002: Bounded Tool Execution Boundary via Simulator
- **Description:** The system shall execute approved recovery actions exclusively through a strongly-typed adapter interface connected to the Simulated Payment Provider.
- **Business Justification:** Isolates external side effects and eliminates live financial exposure.
- **Priority:** **MUST**
- **Input:** Approved tool payload with idempotency key, amount minor units, currency, customer ID.
- **Expected Output:** Provider response object with transaction ID and status.
- **Preconditions:** Case in state `POLICY_APPROVED`.
- **Main Behavior:** Calls simulator method; transitions case to `ACTION_EXECUTING`.
- **Error Behavior:** Socket drops caught and handled via three-valued uncertainty.
- **Related User Stories:** US-WFK-002
- **Business Rules:** BR-006, BR-007
- **Acceptance Criteria:** US-WFK-002 Scenario
- **Verification Method:** Adapter contract tests against simulator.

---

#### FR-IDP-001: Action-Level Idempotency Token Generation
- **Description:** The system shall generate a deterministic, unique idempotency token for every outgoing action following the format `idemp_{case_id}_att_{attempt_number}`.
- **Business Justification:** Ensures external payment gateways never execute duplicate charges for the same retry attempt.
- **Priority:** **MUST**
- **Input:** `case_id` and integer `attempt_number`.
- **Expected Output:** String idempotency token.
- **Preconditions:** Action dispatch initiated.
- **Main Behavior:** Formats string; attaches to outgoing request header and persists in action ledger.
- **Error Behavior:** None.
- **Related User Stories:** US-WFK-002
- **Business Rules:** BR-004, BR-006
- **Acceptance Criteria:** US-WFK-002 Scenario
- **Verification Method:** Assertion that re-executing action passes identical token.

---

### Stopping Rules & Escalation

#### FR-STP-001: Hard Retry Budget Ceiling Enforcement (<= 3 Attempts)
- **Description:** The system shall maintain an integer attempt counter on the case, incrementing on each dispatch, and permanently halt automated retries when attempt counter reaches 3.
- **Business Justification:** Prevents runaway retry loops and card scheme fraud flags.
- **Priority:** **MUST**
- **Input:** Current case attempt count.
- **Expected Output:** Execution permitted if count < 3; halted if count >= 3.
- **Preconditions:** Action evaluation.
- **Main Behavior:** Blocks 4th attempt; transitions case to `HALTED_MAX_RETRIES`.
- **Error Behavior:** None.
- **Related User Stories:** US-STP-001
- **Business Rules:** BR-003
- **Acceptance Criteria:** US-STP-001 Scenario
- **Verification Method:** Multi-attempt simulation asserting hard stop at attempt 3.

---

#### FR-STP-002: Immediate Workflow Halting on Confirmed Recovery
- **Description:** When an authoritative provider receipt confirms payment status `succeeded`, the system shall transition case to `RECOVERED` and permanently cancel any pending or scheduled retries.
- **Business Justification:** Absolute success protection invariant: eliminates double charges.
- **Priority:** **MUST**
- **Input:** Verified settlement receipt.
- **Expected Output:** Case state set to terminal `RECOVERED`.
- **Preconditions:** Receipt verified.
- **Main Behavior:** Cancels scheduler timers; updates confirmed recovery metrics.
- **Error Behavior:** None.
- **Related User Stories:** US-STP-002
- **Business Rules:** BR-001, BR-007
- **Acceptance Criteria:** US-STP-002 Scenario
- **Verification Method:** Integration test verifying zero actions dispatched post-recovery.

---

#### FR-STP-003: High-Value Exposure Escalation Threshold (>= $1,000)
- **Description:** The system shall automatically route any case with nominal amount >= 100,000 minor units ($1,000.00) or low model confidence (< 0.60) to the human operator escalation queue.
- **Business Justification:** Human-in-the-loop protection against large autonomous financial errors.
- **Priority:** **MUST**
- **Input:** Case nominal amount and model confidence score.
- **Expected Output:** Case state transitioned to `ESCALATED_HUMAN_REVIEW`.
- **Preconditions:** Case evaluated.
- **Main Behavior:** Halts automated execution; exposes case in operator queue.
- **Error Behavior:** None.
- **Related User Stories:** US-STP-003, US-DSH-004
- **Business Rules:** BR-014
- **Acceptance Criteria:** US-STP-003 Scenario
- **Verification Method:** Test scenario with $1,500 invoice asserting automatic escalation.

---

### Outcome Verification & Attribution

#### FR-VRF-001: Authoritative Gateway Settlement Verification
- **Description:** The system shall declare revenue recovered only upon receiving and validating an authoritative provider receipt matching transaction ID, exact integer minor units, and currency.
- **Business Justification:** Eliminates phantom revenue claims; guarantees financial report truthfulness.
- **Priority:** **MUST**
- **Input:** Provider settlement receipt and case parameters.
- **Expected Output:** Boolean verification result.
- **Preconditions:** Receipt received.
- **Main Behavior:** Validates `status == "succeeded"`, `amount_captured == case.amount_minor_units`, and `currency == case.currency`.
- **Error Behavior:** Mismatched receipt triggers escalation with reason `SETTLEMENT_DISCREPANCY`.
- **Related User Stories:** US-VRF-001
- **Business Rules:** BR-008, BR-012
- **Acceptance Criteria:** US-VRF-001 Scenario
- **Verification Method:** Receipt validation unit test suite.

---

#### FR-VRF-002: Three-Valued Uncertainty Handling on Timeout
- **Description:** If a payment retry network request times out, drops connection, or returns HTTP 504/502, the system shall classify the outcome as `UNCERTAIN` and transition case to `VERIFICATION_PENDING`.
- **Business Justification:** Prevents double-charging customers during temporary gateway network partitions.
- **Priority:** **MUST**
- **Input:** Network timeout exception or HTTP 5xx gateway error.
- **Expected Output:** Case state = `VERIFICATION_PENDING`.
- **Preconditions:** Tool execution in-flight.
- **Main Behavior:** Freezes automated retries; schedules asynchronous reconciliation poll.
- **Error Behavior:** If reconciliation fails after 3 attempts, escalates to human operator.
- **Related User Stories:** US-VRF-002
- **Business Rules:** BR-007
- **Acceptance Criteria:** US-VRF-002 Scenario
- **Verification Method:** Chaos test injecting socket timeout during retry call.

---

#### FR-VRF-003: 72-Hour Attribution Window Enforcement
- **Description:** The system shall attribute a successful payment to a recovery action if and only if the settlement timestamp falls within 72 hours of action dispatch.
- **Business Justification:** Prevents taking credit for organic payments settled months later outside the workflow.
- **Priority:** **MUST**
- **Input:** Settlement timestamp and action dispatch timestamp.
- **Expected Output:** Attribution boolean flag.
- **Preconditions:** Payment succeeded.
- **Main Behavior:** If $(t_{\text{settled}} - t_{\text{action}}) \le 72\text{ hours}$, credits confirmed recovered revenue; otherwise marks as `ORGANIC_UNATTRIBUTED`.
- **Error Behavior:** None.
- **Related User Stories:** US-VRF-003
- **Business Rules:** BR-011
- **Acceptance Criteria:** US-VRF-003 Scenario
- **Verification Method:** Attribution test passing settlement timestamps at 24h (attributed) vs. 96h (unattributed).

---

### Audit & Observability

#### FR-AUD-001: Append-Only Structured Audit Event Persistence
- **Description:** The system shall persist an immutable, structured audit record for every case state transition, policy decision, and tool execution.
- **Business Justification:** Guarantees total compliance observability and forensic financial traceability.
- **Priority:** **MUST**
- **Input:** Event parameters: `case_id`, `correlation_id`, `actor`, `action`, `state_from`, `state_to`, `payload_hash`.
- **Expected Output:** Persisted audit row with auto-generated UUID and UTC timestamp.
- **Preconditions:** Database connection active.
- **Main Behavior:** Inserts row into append-only table; database user permissions restrict `UPDATE` and `DELETE`.
- **Error Behavior:** If audit insert fails, primary transaction rolls back.
- **Related User Stories:** US-AUD-001
- **Business Rules:** BR-015
- **Acceptance Criteria:** US-AUD-001 Scenario
- **Verification Method:** Database security permission test verifying `DELETE` statements fail.

---

#### FR-AUD-002: Correlation ID Trace Retrieval API
- **Description:** The system shall expose a REST endpoint `GET /api/v1/cases/{id}/audit` returning the ordered chronological timeline of audit events for a specified case.
- **Business Justification:** Enables operators and auditors to inspect the complete history of any case.
- **Priority:** **MUST**
- **Input:** `case_id` path parameter.
- **Expected Output:** HTTP 200 with chronological array of audit event objects.
- **Preconditions:** Case exists.
- **Main Behavior:** Queries audit table ordered by timestamp ascending; returns JSON list.
- **Error Behavior:** Returns HTTP 404 if case does not exist.
- **Related User Stories:** US-AUD-002
- **Business Rules:** BR-015
- **Acceptance Criteria:** US-AUD-002 Scenario
- **Verification Method:** API test retrieving audit trail for completed case.

---

### Dashboard & Analytics

#### FR-DSH-001: Real-Time Financial Metric Aggregation Endpoint
- **Description:** The system shall expose `GET /api/v1/metrics/overview` computing aggregate KPIs: Gross Revenue at Risk, Confirmed Recovered Revenue, Case Recovery Rate (%), Revenue Recovery Rate (%), Active Cases, and Blocked Violations.
- **Business Justification:** Drives executive and operational dashboards with authoritative financial metrics.
- **Priority:** **MUST**
- **Input:** None (or optional date range query parameters).
- **Expected Output:** HTTP 200 with JSON summary of metrics computed strictly from database records.
- **Preconditions:** Database accessible.
- **Main Behavior:** Executes aggregation queries using integer math; formats recovery rates as percentages.
- **Error Behavior:** None.
- **Related User Stories:** US-DSH-001
- **Business Rules:** BR-008, BR-012
- **Acceptance Criteria:** US-DSH-001 Scenario
- **Verification Method:** Integration test comparing API output against direct SQL aggregate counts.

---

#### FR-DSH-002: Recovery Case Queue Listing with Pagination & Filters
- **Description:** The system shall expose `GET /api/v1/cases` supporting pagination (`limit`, `offset`), sorting, and filtering by `state`, `failure_class`, and `customer_id`.
- **Business Justification:** Allows operators to triage and navigate thousands of active recovery cases.
- **Priority:** **MUST**
- **Input:** Query parameters: `state`, `failure_class`, `search`, `limit`, `offset`.
- **Expected Output:** HTTP 200 with paginated array of case summary objects and `total_count`.
- **Preconditions:** Database accessible.
- **Main Behavior:** Executes parameterized SQL query with index optimization.
- **Error Behavior:** Invalid query parameters return HTTP 422 Unprocessable Entity.
- **Related User Stories:** US-DSH-002
- **Business Rules:** None.
- **Acceptance Criteria:** US-DSH-002 Scenario
- **Verification Method:** API tests verifying pagination bounds and filter combinations.

---

#### FR-DSH-003: Case Diagnostic Trace & Audit Timeline Endpoint
- **Description:** The system shall expose `GET /api/v1/cases/{id}` returning complete diagnostic telemetry: raw decline code, AI failure class, confidence score, rationale, evaluated policy rules, provider receipt, and audit history.
- **Business Justification:** Powers the frontend diagnostic drawer to provide explainable AI reasoning to operators.
- **Priority:** **MUST**
- **Input:** `case_id` path parameter.
- **Expected Output:** HTTP 200 with complete nested case detail schema.
- **Preconditions:** Case exists.
- **Main Behavior:** Assembles case entity, proposal record, policy decisions, and audit timeline into unified response.
- **Error Behavior:** Returns HTTP 404 if case ID is not found.
- **Related User Stories:** US-DSH-003
- **Business Rules:** BR-012, BR-015
- **Acceptance Criteria:** US-DSH-003 Scenario
- **Verification Method:** API contract assertion test against frontend schema.

---

### Evaluation Engine

#### FR-EVL-001: Deterministic 500-Scenario Batch Evaluation Harness
- **Description:** The system shall provide an evaluation CLI and service that executes a batch simulation of 500 deterministic synthetic scenarios using a fixed seed (default: 42) and Virtual Clock.
- **Business Justification:** Replaces subjective claims with reproducible, scientific regression benchmarking.
- **Priority:** **MUST**
- **Input:** Seed integer (e.g., 42) and scenario count (e.g., 500).
- **Expected Output:** Evaluation report object with exact case recovery counts, recovered amounts, and safety rates.
- **Preconditions:** Scenario generator fixtures initialized.
- **Main Behavior:** Iterates through scenarios, feeds events through full pipeline, advances virtual clock, and tabulates final outcomes.
- **Error Behavior:** Any safety violation aborts run with critical regression failure.
- **Related User Stories:** US-EVL-001
- **Business Rules:** BR-016
- **Acceptance Criteria:** US-EVL-001 Scenario
- **Verification Method:** Repeatability test running batch twice with seed 42 asserting identical SHA-256 output hashes.

---

#### FR-EVL-002: Counterfactual Baseline Comparison Execution
- **Description:** The Evaluation Engine shall execute four standardized counterfactual baselines (Do-Nothing, Always-Retry, Simple Rule-Based, and Oracle Upper Bound) on the identical scenario cohort and calculate comparative lift.
- **Business Justification:** Mathematically proves whether intelligent recovery outperforms naive retrying.
- **Priority:** **MUST**
- **Input:** 500 scenario cohort.
- **Expected Output:** Baseline comparison table containing recovery rate and net revenue for each baseline.
- **Preconditions:** Evaluation run complete.
- **Main Behavior:** Computes counterfactual outcomes under each baseline strategy; calculates relative percentage lift.
- **Error Behavior:** None.
- **Related User Stories:** US-EVL-002
- **Business Rules:** BR-016
- **Acceptance Criteria:** US-EVL-002 Scenario
- **Verification Method:** Mathematical verification test asserting baseline ordering: Do-Nothing <= Rule-Based <= Oracle.

---

#### FR-EVL-003: Serialized Evaluation Report Artifact Generation
- **Description:** The Evaluation Engine shall serialize evaluation results into a versioned JSON artifact at `artifacts/evaluation_report_500.json` containing run metadata, formulas, baselines, and synthetic disclaimers.
- **Business Justification:** Enables transparent auditing and external review of project performance claims.
- **Priority:** **MUST**
- **Input:** Evaluation report data structure.
- **Expected Output:** Formatted JSON file written to `artifacts/`.
- **Preconditions:** Write access to `artifacts/` directory.
- **Main Behavior:** Formats JSON with 2-space indentation; includes commit hash, timestamp, seed, and disclaimer notice.
- **Error Behavior:** None.
- **Related User Stories:** US-EVL-003
- **Business Rules:** BR-016
- **Acceptance Criteria:** US-EVL-003 Scenario
- **Verification Method:** JSON schema validation test on generated artifact.
