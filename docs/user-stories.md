# RevenueRescueAI — User Story Catalog & Acceptance Criteria

> **Document ID:** DOC-UST-003  
> **Phase:** 0.2 (User Stories, Functional Requirements & Acceptance Criteria)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

This document establishes the comprehensive, testable User Story Catalog for RevenueRescueAI. Each story represents a distinct functional capability required to deliver the approved MVP. 

Every user story strictly adheres to the standard agile template:  
> **"As a [user or actor], I want [capability], so that [business benefit]."**

Furthermore, every user story includes all fifteen required metadata attributes: Unique ID, Epic ID, Title, User Story, Actor, Business Value, MoSCoW Priority, Preconditions, Main Success Scenario, Alternative Scenarios, Failure Scenarios, Dependencies, Gherkin Acceptance Criteria, Related Functional Requirements, and Planned Test Scenarios.

---

## 2. Master User Story Index

| Story ID | Epic ID | Title | Actor | Priority |
|---|---|---|---|:---:|
| **US-ING-001** | EPIC-01 | Ingest Valid Payment Failure Webhook | Event Ingestion Service | **MUST** |
| **US-ING-002** | EPIC-01 | Reject Webhook with Invalid Cryptographic Signature | Event Ingestion Service | **MUST** |
| **US-ING-003** | EPIC-01 | Reject Malformed Inbound Event Payload | Event Ingestion Service | **MUST** |
| **US-ING-004** | EPIC-01 | Absorb Duplicate Inbound Event Idempotently | Event Ingestion Service | **MUST** |
| **US-RSK-001** | EPIC-02 | Detect Revenue Risk and Instantiate Recovery Case | Risk Detection Engine | **MUST** |
| **US-RSK-002** | EPIC-03 | Quantify Revenue at Risk in Integer Minor Units | Risk Detection Engine | **MUST** |
| **US-RSK-003** | EPIC-05 | Standardize and Classify Raw Failure Code | Decision Engine (AI) | **MUST** |
| **US-ELG-001** | EPIC-04 | Pre-screen Case Recovery Eligibility | Policy Enforcement Engine | **MUST** |
| **US-ELG-002** | EPIC-04 | Enforce Success Protection on Already-Settled Invoices | Policy Enforcement Engine | **MUST** |
| **US-ELG-003** | EPIC-04 | Filter Ineligible Cases on Window Expiration or Opt-Out | Policy Enforcement Engine | **MUST** |
| **US-INT-001** | EPIC-06 | Contextually Propose Next Best Recovery Intervention | Decision Engine (AI) | **MUST** |
| **US-INT-002** | EPIC-06 | Provide Explainable Rationale for Action Proposal | Decision Engine (AI) | **MUST** |
| **US-INT-003** | EPIC-06 | Fall Back to Deterministic Rule on Model Failure | Decision Engine (AI) | **MUST** |
| **US-POL-001** | EPIC-07 | Deterministically Authorize Compliant Intervention | Policy Enforcement Engine | **MUST** |
| **US-POL-002** | EPIC-07 | Veto Unauthorized Action or Policy Violation | Policy Enforcement Engine | **MUST** |
| **US-POL-003** | EPIC-07 | Enforce Hard Ban on Retrying Terminal Declines | Policy Enforcement Engine | **MUST** |
| **US-WFK-001** | EPIC-08 | Orchestrate Recovery Workflow State Transitions | Recovery Workflow Engine | **MUST** |
| **US-WFK-002** | EPIC-08 | Dispatch Payment Action via Gateway Simulator | Recovery Workflow Engine | **MUST** |
| **US-STP-001** | EPIC-09 | Enforce Maximum Retry Budget Ceilings | Policy Enforcement Engine | **MUST** |
| **US-STP-002** | EPIC-09 | Halt Workflow Immediately on Confirmed Success | Recovery Workflow Engine | **MUST** |
| **US-STP-003** | EPIC-09 | Escalate High-Value or Anomalous Cases to Human | Recovery Workflow Engine | **MUST** |
| **US-VRF-001** | EPIC-10 | Verify Settlement via Authoritative Gateway Receipt | Recovery Workflow Engine | **MUST** |
| **US-VRF-002** | EPIC-10 | Preserve Uncertainty on Provider Timeout | Recovery Workflow Engine | **MUST** |
| **US-VRF-003** | EPIC-10 | Enforce Attribution Window and Deduplication | Recovery Workflow Engine | **MUST** |
| **US-AUD-001** | EPIC-11 | Record Immutable Append-Only Audit Trail | Recovery Workflow Engine | **MUST** |
| **US-AUD-002** | EPIC-11 | Inspect Sequential Audit History by Correlation ID | Auditor / Reviewer | **MUST** |
| **US-DSH-001** | EPIC-13 | View Real-Time Financial Recovery KPIs | Finance Manager | **MUST** |
| **US-DSH-002** | EPIC-13 | Search, Filter, and Inspect Recovery Case Queue | RevOps Analyst | **MUST** |
| **US-DSH-003** | EPIC-13 | Inspect End-to-End Case Diagnostic Trace Drawer | RevOps Analyst | **MUST** |
| **US-DSH-004** | EPIC-13 | Review and Resolve Escalated Recovery Cases | Recovery Operator | **MUST** |
| **US-EVL-001** | EPIC-14 | Execute Reproducible 500-Scenario Batch Evaluation | RevOps Analyst | **MUST** |
| **US-EVL-002** | EPIC-14 | Benchmark Recovery Lift Against Baselines | Finance Manager | **MUST** |
| **US-EVL-003** | EPIC-14 | Export Auditable Evaluation Report | Auditor / Reviewer | **MUST** |

---

## 3. Detailed User Story Specifications

---

### Epic: EPIC-01 — Event Ingestion & Webhook Boundary

#### US-ING-001: Ingest Valid Payment Failure Webhook
- **Epic ID:** EPIC-01
- **Title:** Ingest Valid Payment Failure Webhook
- **User Story:** As the Event Ingestion Service, I want to receive and authenticate incoming `payment.failed` webhook events from payment providers, so that every revenue-at-risk event enters the recovery pipeline immediately.
- **Actor:** Event Ingestion Service
- **Business Value:** Guarantees zero dropped payment failures at the platform perimeter.
- **Priority:** **MUST**
- **Preconditions:** Webhook listener is running; gateway signing secret is configured.
- **Main Success Scenario:** A payment gateway posts an HTTP payload to `/api/v1/webhooks/gateway`. The service verifies the HMAC signature, parses valid JSON, verifies required fields, and returns HTTP 200 OK within 500ms.
- **Alternative Scenarios:** Payload contains extra unrecognized metadata fields; service preserves them in raw JSON without failing validation.
- **Failure Scenarios:** Database is offline; service returns HTTP 503 so gateway retries later.
- **Dependencies:** Webhook crypto library, Pydantic schema validator.
- **Acceptance Criteria (Gherkin):**
```gherkin
Feature: Webhook Ingestion Boundary

Scenario: Ingest valid payment failure webhook
  GIVEN the webhook ingestion endpoint is active
  AND a payment gateway posts a "payment.failed" webhook with a valid HMAC-SHA256 signature
  AND the body contains payment_id "pay_001", amount 4500, currency "USD", customer_id "cust_101"
  WHEN the Event Ingestion Service processes the request
  THEN the service must return HTTP 200 OK with a confirmation token
  AND an ingestion event must be passed to the Risk Detection Engine
  AND the processing latency must not exceed 500 milliseconds
```
- **Related Functional Requirements:** FR-ING-001, FR-ING-002
- **Related Test Scenarios:** TS-ING-001 (Valid Webhook Ingestion)

---

#### US-ING-002: Reject Webhook with Invalid Cryptographic Signature
- **Epic ID:** EPIC-01
- **Title:** Reject Webhook with Invalid Cryptographic Signature
- **User Story:** As the Event Ingestion Service, I want to verify the cryptographic HMAC signature of every inbound webhook, so that forged or unauthenticated requests are rejected before parsing.
- **Actor:** Event Ingestion Service
- **Business Value:** Prevents malicious actors from spoofing payment failure events or injecting fabricated debt records.
- **Priority:** **MUST**
- **Preconditions:** Webhook secret is configured in environment.
- **Main Success Scenario:** An unauthenticated client sends a POST request with an invalid or missing `x-signature` header. The service computes the expected HMAC-SHA256 hash, detects the mismatch, rejects the request with HTTP 401 Unauthorized, and aborts processing.
- **Alternative Scenarios:** None.
- **Failure Scenarios:** Timing attack vulnerability; prevented by using constant-time comparison (`hmac.compare_digest`).
- **Dependencies:** Cryptography library.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Reject forged or tampered webhook
  GIVEN the webhook ingestion endpoint is active with configured secret "whsec_test_99"
  WHEN an external client sends a POST request with an invalid signature header "sha256=invalid_hash"
  THEN the system must reject the request immediately with HTTP 401 Unauthorized
  AND must not create a recovery case
  AND must log a security warning containing source IP and payload hash
```
- **Related Functional Requirements:** FR-ING-002
- **Related Test Scenarios:** TS-ING-002 (Invalid Signature Rejection)

---

#### US-ING-003: Reject Malformed Inbound Event Payload
- **Epic ID:** EPIC-01
- **Title:** Reject Malformed Inbound Event Payload
- **User Story:** As the Event Ingestion Service, I want to strictly validate the data schema of incoming payloads, so that corrupted or incomplete event records never pollute the database.
- **Actor:** Event Ingestion Service
- **Business Value:** Guarantees data integrity and prevents null-pointer runtime crashes.
- **Priority:** **MUST**
- **Preconditions:** Signature is valid.
- **Main Success Scenario:** An inbound payload is missing the required `amount` field. The Pydantic validator flags the missing attribute, rejects the request with HTTP 400 Bad Request, and outputs a structured error explanation.
- **Alternative Scenarios:** Payload contains non-numeric string for amount; rejected with HTTP 400.
- **Failure Scenarios:** None.
- **Dependencies:** Pydantic schema validation.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Reject payload with missing required fields
  GIVEN a webhook request arrives with a valid cryptographic signature
  WHEN the JSON body is missing required field "currency" or "amount"
  THEN the system must reject the request with HTTP 400 Bad Request
  AND must return a JSON body detailing the exact schema validation error
  AND must not create a recovery case in database
```
- **Related Functional Requirements:** FR-ING-003
- **Related Test Scenarios:** TS-ING-003 (Schema Validation Rejection)

---

#### US-ING-004: Absorb Duplicate Inbound Event Idempotently
- **Epic ID:** EPIC-01
- **Title:** Absorb Duplicate Inbound Event Idempotently
- **User Story:** As the Event Ingestion Service, I want to detect replayed or duplicate webhook event IDs, so that network retries by payment providers do not trigger duplicate recovery cases.
- **Actor:** Event Ingestion Service
- **Business Value:** Eliminates duplicate processing and protects against race conditions.
- **Priority:** **MUST**
- **Preconditions:** An event with ID `evt_998` has already been ingested.
- **Main Success Scenario:** Gateway delivers `evt_998` a second time due to network ACK delay. Ingestion service queries idempotency index, detects existing `evt_998`, returns HTTP 200 OK immediately, and discards the duplicate without secondary workflow execution.
- **Alternative Scenarios:** Identical payload arrives with different event ID but identical `payment_id`; correlated to existing case in detection layer.
- **Failure Scenarios:** Race condition with concurrent workers; prevented by database unique index constraint.
- **Dependencies:** Database unique index on `event_id`.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Handle duplicate webhook delivery
  GIVEN event "evt_998" has already been successfully ingested and stored
  WHEN the payment gateway re-sends identical event "evt_998"
  THEN the system must recognize "evt_998" as a duplicate
  AND must return HTTP 200 OK with status "duplicate_acknowledged"
  AND must not create a second recovery case
  AND must not execute any recovery actions
```
- **Related Functional Requirements:** FR-ING-004, FR-IDP-001
- **Related Test Scenarios:** TS-ING-004 (Idempotent Webhook Deduplication)

---

### Epic: EPIC-02 & EPIC-03 — Failure Detection & Risk Quantification

#### US-RSK-001: Detect Revenue Risk and Instantiate Recovery Case
- **Epic ID:** EPIC-02
- **Title:** Detect Revenue Risk and Instantiate Recovery Case
- **User Story:** As the Risk Detection Engine, I want to identify payments associated with potential revenue loss and bind them to a stateful `RecoveryCase`, so that the recovery lifecycle begins immediately.
- **Actor:** Risk Detection Engine
- **Business Value:** Transforms passive failure logs into active, tracked recovery workflows.
- **Priority:** **MUST**
- **Preconditions:** Valid failure event token received from ingestion.
- **Main Success Scenario:** Risk Detection Engine resolves customer and invoice references from event payload, instantiates a `RecoveryCase` in state `DETECTED`, assigns a unique `case_id`, and appends an audit event `CASE_DETECTED`.
- **Alternative Scenarios:** Case already open for this invoice; updates existing case telemetry instead of creating duplicate.
- **Failure Scenarios:** Customer ID does not exist in customer repository; creates placeholder customer profile with risk flag.
- **Dependencies:** Case persistence repository, Customer repository.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Instantiate new recovery case from failure event
  GIVEN a validated failure event for payment "pay_441" on invoice "inv_882"
  WHEN the Risk Detection Engine processes the event
  Then a new RecoveryCase must be created in the database
  AND the case state must be "DETECTED"
  AND the case must be linked to payment "pay_441" and invoice "inv_882"
  AND an audit event "CASE_DETECTED" must be permanently recorded
```
- **Related Functional Requirements:** FR-DET-001, FR-DET-002
- **Related Test Scenarios:** TS-DET-001 (Recovery Case Instantiation)

---

#### US-RSK-002: Quantify Revenue at Risk in Integer Minor Units
- **Epic ID:** EPIC-03
- **Title:** Quantify Revenue at Risk in Integer Minor Units
- **User Story:** As the Risk Detection Engine, I want to store all monetary values as integer minor units, so that rounding errors and floating-point inaccuracies never corrupt financial calculations.
- **Actor:** Risk Detection Engine
- **Business Value:** Guarantees 100% mathematical precision on financial balance sheets.
- **Priority:** **MUST**
- **Preconditions:** Event contains nominal amount and valid currency code.
- **Main Success Scenario:** Inbound payload specifies `$129.50 USD`. System validates that 1 USD = 100 cents, computes `12950` minor units as a 64-bit integer, and stores `amount_minor_units: 12950` and `currency: "USD"`.
- **Alternative Scenarios:** Zero-decimal currencies (e.g., JPY); multiplier is 1 (stored as raw integer).
- **Failure Scenarios:** Amount is negative (e.g., `-500`); rejected as invalid financial input.
- **Dependencies:** Currency multiplier lookup table.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Store at-risk revenue in integer minor units
  GIVEN an inbound payment failure event with amount 45.00 and currency "USD"
  WHEN the Risk Detection Engine calculates the revenue at risk
  THEN the stored amount must be exactly 4500 integer minor units
  AND the database column type must be a 64-bit integer
  AND floating-point representations must be strictly prohibited
```
- **Related Functional Requirements:** FR-QNT-001, FR-QNT-002
- **Related Test Scenarios:** TS-QNT-001 (Minor Unit Integer Storage)

---

#### US-RSK-003: Standardize and Classify Raw Failure Code
- **Epic ID:** EPIC-05
- **Title:** Standardize and Classify Raw Failure Code
- **User Story:** As the Decision Engine (AI), I want to map diverse, raw gateway decline codes into a standardized failure taxonomy, so that the system understands the underlying root cause.
- **Actor:** Decision Engine (AI)
- **Business Value:** Distinguishes temporary recoverable issues from permanent terminal failures.
- **Priority:** **MUST**
- **Preconditions:** Case is instantiated with raw gateway error code.
- **Main Success Scenario:** Case contains raw code `insufficient_funds` (code 51). Classifier maps it to standardized class `SOFT_DECLINE_TEMPORARY_BALANCE` with severity `SOFT`.
- **Alternative Scenarios:** Raw code is `stolen_card` (code 43); mapped to `HARD_DECLINE_STOLEN_CARD` with severity `HARD`.
- **Failure Scenarios:** Unrecognized raw code; mapped to `UNKNOWN_DECLINE_UNCLASSIFIED` with conservative review flag.
- **Dependencies:** Failure taxonomy mapping table.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Classify temporary balance shortfall
  GIVEN a recovery case with raw provider code "insufficient_funds"
  WHEN the Failure Diagnostic Classifier analyzes the code
  THEN the failure class must be set to "SOFT_DECLINE_TEMPORARY_BALANCE"
  AND the decline severity must be set to "SOFT"
  AND the classification rationale must note "Temporary balance deficit eligible for scheduled retry"
```
- **Related Functional Requirements:** FR-CLS-001, FR-CLS-002
- **Related Test Scenarios:** TS-CLS-001 (Failure Taxonomy Classification)

---

### Epic: EPIC-04 — Recovery Eligibility & Pre-screening

#### US-ELG-001: Pre-screen Case Recovery Eligibility
- **Epic ID:** EPIC-04
- **Title:** Pre-screen Case Recovery Eligibility
- **User Story:** As the Policy Enforcement Engine, I want to evaluate detected cases against business prerequisites, so that inoperable or unrecoverable cases do not waste retry budgets.
- **Actor:** Policy Enforcement Engine
- **Business Value:** Focuses resources exclusively on actionable revenue recovery.
- **Priority:** **MUST**
- **Preconditions:** Case in state `DETECTED`.
- **Main Success Scenario:** Case passes all checks: active customer, invoice age 2 days (< 14 days), no disputes, zero prior successful payments. Case state transitions to `ELIGIBLE`.
- **Alternative Scenarios:** Customer account is suspended; case state transitions to `INELIGIBLE_ACCOUNT_SUSPENDED`.
- **Failure Scenarios:** Customer metadata lookup times out; case remains in `VALIDATING` pending retry.
- **Dependencies:** Customer account repository, Policy rule definitions.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Case passes eligibility pre-screening
  GIVEN a case in state "DETECTED" for an active customer account
  AND the invoice age is 2 calendar days
  AND there are zero disputes or opt-out flags
  WHEN the Policy Enforcement Engine evaluates eligibility
  THEN the case state must transition to "ELIGIBLE"
  AND an audit record "CASE_MARKED_ELIGIBLE" must be logged
```
- **Related Functional Requirements:** FR-ELG-001
- **Related Test Scenarios:** TS-ELG-001 (Eligibility Pre-screening)

---

#### US-ELG-002: Enforce Success Protection on Already-Settled Invoices
- **Epic ID:** EPIC-04
- **Title:** Enforce Success Protection on Already-Settled Invoices
- **User Story:** As the Policy Enforcement Engine, I want to check whether an invoice has already been settled before approving recovery, so that a customer is never double-charged for an invoice they already paid.
- **Actor:** Policy Enforcement Engine
- **Business Value:** Core financial invariant: eliminates duplicate customer debits and chargeback fines.
- **Priority:** **MUST**
- **Preconditions:** Case in state `DETECTED` or `AWAITING_DECISION`.
- **Main Success Scenario:** A customer paid their invoice via web portal 10 minutes ago. Ingestion receives a lagging failure webhook. Policy gate checks invoice ledger, detects status is `PAID`, marks case as `INELIGIBLE_ALREADY_PAID`, and blocks automated actions.
- **Alternative Scenarios:** Case is mid-workflow and external payment clears; workflow halts immediately.
- **Failure Scenarios:** None.
- **Dependencies:** Authoritative invoice ledger.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Block recovery on invoice already marked paid
  GIVEN a recovery case is evaluated for invoice "inv_991"
  AND the authoritative invoice ledger confirms status is "PAID"
  WHEN the Policy Enforcement Engine performs the Success Protection check
  THEN the case must be marked "RESOLVED_ALREADY_PAID"
  AND all scheduled recovery actions must be canceled
  AND zero payment requests must be dispatched to the gateway
```
- **Related Functional Requirements:** FR-ELG-002, FR-POL-003
- **Related Test Scenarios:** TS-ELG-002 (Success Protection Invariant)

---

#### US-ELG-003: Filter Ineligible Cases on Window Expiration or Opt-Out
- **Epic ID:** EPIC-04
- **Title:** Filter Ineligible Cases on Window Expiration or Opt-Out
- **User Story:** As the Policy Enforcement Engine, I want to immediately halt recovery if a case exceeds the 14-day recovery window or if the customer has opted out, so that the business complies with dunning regulations.
- **Actor:** Policy Enforcement Engine
- **Business Value:** Guarantees legal compliance with communication and debt collection rules.
- **Priority:** **MUST**
- **Preconditions:** Case evaluated for eligibility.
- **Main Success Scenario:** Case failure timestamp was 15 days ago. Policy gate identifies `case_age > 14 days`, transitions case to `HALTED_EXPIRED`, and halts automated retries.
- **Alternative Scenarios:** Customer profile has `communication_opted_out: true`; case marks communications suppressed.
- **Failure Scenarios:** None.
- **Dependencies:** Virtual Clock / Date calculation.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Invalidate case exceeding maximum recovery window
  GIVEN an invoice failed 15 calendar days prior to current timestamp
  WHEN the Policy Enforcement Engine evaluates recovery eligibility
  THEN the case must transition to "HALTED_EXPIRED"
  AND automated payment attempts must be permanently disabled
  AND an audit event "RECOVERY_WINDOW_EXPIRED" must be persisted
```
- **Related Functional Requirements:** FR-ELG-003, FR-STP-002
- **Related Test Scenarios:** TS-ELG-003 (Recovery Window Expiration)

---

### Epic: EPIC-06 & EPIC-07 — Intervention Recommendation & Policy Gate

#### US-INT-001: Contextually Propose Next Best Recovery Intervention
- **Epic ID:** EPIC-06
- **Title:** Contextually Propose Next Best Recovery Intervention
- **User Story:** As the Decision Engine (AI), I want to analyze case telemetry and recommend an allow-listed recovery intervention, so that the system applies an optimal strategy rather than blind retrying.
- **Actor:** Decision Engine (AI)
- **Business Value:** Increases recovery probability by timing retries around customer liquidity (e.g., payday).
- **Priority:** **MUST**
- **Preconditions:** Case is in state `ELIGIBLE`.
- **Main Success Scenario:** Case is soft decline on Friday evening. Decision Engine inspects historical recovery curves, recommends action `RETRY_PAYMENT` with execution delay of 60 hours (Monday 09:00 AM), and outputs a typed `InterventionProposal`.
- **Alternative Scenarios:** Soft decline is second attempt; recommends `SEND_PAYMENT_UPDATE_LINK`.
- **Failure Scenarios:** Hard decline detected; recommends `HALT_RECOVERY`.
- **Dependencies:** Failure classification, Statistical/Model Inference module.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Propose delayed payment retry for payday liquidity
  GIVEN an eligible case with failure class "SOFT_DECLINE_TEMPORARY_BALANCE"
  AND attempt count is 0
  WHEN the Decision Engine evaluates the case context
  THEN it must generate an InterventionProposal with action "RETRY_PAYMENT"
  AND the proposal must specify a scheduled execution delay
  AND the action name must match the allow-listed Action Taxonomy
```
- **Related Functional Requirements:** FR-INT-001, FR-INT-002
- **Related Test Scenarios:** TS-INT-001 (Intervention Proposal Generation)

---

#### US-INT-002: Provide Explainable Rationale for Action Proposal
- **Epic ID:** EPIC-06
- **Title:** Provide Explainable Rationale for Action Proposal
- **User Story:** As a RevOps Analyst, I want the Decision Engine to attach a human-readable explanation and confidence score to every proposal, so that automated decisions are transparent and auditable.
- **Actor:** Decision Engine (AI) / RevOps Analyst
- **Business Value:** Eliminates the "black box" problem of AI automation; empowers operators to trust system logic.
- **Priority:** **MUST**
- **Preconditions:** Decision engine generates a proposal.
- **Main Success Scenario:** Decision Engine outputs proposal with `confidence: 0.85` and `rationale: "Soft balance decline on Friday; delaying retry 60h captures Monday payroll deposit."` Stored in case record and visible in UI.
- **Alternative Scenarios:** Confidence score is low (< 0.60); proposal flags case for human review.
- **Failure Scenarios:** None.
- **Dependencies:** Diagnostic telemetry.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Attach explainable rationale to recommendation
  GIVEN the Decision Engine generates an intervention proposal
  WHEN the proposal is created
  THEN it must contain a numeric confidence score between 0.0 and 1.0
  AND it must contain a non-empty string explaining the business rationale
  AND the rationale must be visible in the Case Detail Inspector UI
```
- **Related Functional Requirements:** FR-INT-003
- **Related Test Scenarios:** TS-INT-002 (Explainable Rationale Verification)

---

#### US-INT-003: Fall Back to Deterministic Rule on Model Failure
- **Epic ID:** EPIC-06
- **Title:** Fall Back to Deterministic Rule on Model Failure
- **User Story:** As the Decision Engine (AI), I want to fall back to a safe deterministic rule if model inference fails or times out, so that system throughput is never blocked by AI downtime.
- **Actor:** Decision Engine (AI)
- **Business Value:** Guarantees 99.9% system availability even during external LLM outages.
- **Priority:** **MUST**
- **Preconditions:** Model inference endpoint throws HTTP 500, timeout, or invalid JSON.
- **Main Success Scenario:** LLM API times out after 3 seconds. Decision Engine catches the exception, logs a warning, applies the fallback rule (standard 48-hour retry for soft declines), and flags proposal with `source: "DETERMINISTIC_FALLBACK"`.
- **Alternative Scenarios:** Model outputs hallucinated action name; rejected by schema parser and triggers fallback.
- **Failure Scenarios:** None.
- **Dependencies:** Fallback rule engine.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Fall back to deterministic rule when AI service fails
  GIVEN an eligible recovery case requiring an intervention recommendation
  WHEN the AI reasoning service times out or returns malformed JSON
  THEN the Decision Engine must catch the failure without crashing
  AND must generate a valid InterventionProposal using deterministic fallback rules
  AND must record an audit event "MODEL_FALLBACK_APPLIED"
```
- **Related Functional Requirements:** FR-INT-004
- **Related Test Scenarios:** TS-INT-003 (Deterministic Model Fallback)

---

#### US-POL-001: Deterministically Authorize Compliant Intervention
- **Epic ID:** EPIC-07
- **Title:** Deterministically Authorize Compliant Intervention
- **User Story:** As the Policy Enforcement Engine, I want to evaluate proposed interventions against hard business rules, so that only strictly compliant actions can be executed.
- **Actor:** Policy Enforcement Engine
- **Business Value:** Core safety invariant: guarantees zero unauthorized actions occur.
- **Priority:** **MUST**
- **Preconditions:** Proposal received from Decision Engine.
- **Main Success Scenario:** Proposed action is `RETRY_PAYMENT`. Policy checks: action is allow-listed (Pass), attempts (0 < 3) (Pass), backoff >= 24h (Pass), invoice unpaid (Pass). Policy emits `PolicyDecision: APPROVED`, case state transitions to `POLICY_APPROVED`.
- **Alternative Scenarios:** None.
- **Failure Scenarios:** None.
- **Dependencies:** Policy rule repository.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Authorize compliant retry proposal
  GIVEN a proposed action "RETRY_PAYMENT" for an invoice with 0 prior attempts
  AND the invoice is unpaid and within the 14-day recovery window
  WHEN the Policy Enforcement Engine validates the proposal
  THEN it must return a PolicyDecision with status "APPROVED"
  AND the case state must transition to "POLICY_APPROVED"
  AND an audit record "POLICY_EVALUATION_PASSED" must be appended
```
- **Related Functional Requirements:** FR-POL-001
- **Related Test Scenarios:** TS-POL-001 (Policy Approval)

---

#### US-POL-002: Veto Unauthorized Action or Policy Violation
- **Epic ID:** EPIC-07
- **Title:** Veto Unauthorized Action or Policy Violation
- **User Story:** As the Policy Enforcement Engine, I want to veto any proposal that violates retry limits, backoff intervals, or safety invariants, so that rogue AI decisions are completely neutralized.
- **Actor:** Policy Enforcement Engine
- **Business Value:** Protects the business from legal, financial, and reputational harm caused by AI hallucinations.
- **Priority:** **MUST**
- **Preconditions:** Proposal received from Decision Engine.
- **Main Success Scenario:** AI proposes `RETRY_PAYMENT` on a case with 3 prior attempts. Policy checks attempt ceiling, rejects proposal with reason `MAX_RETRIES_EXCEEDED`, transitions case to `HALTED_MAX_RETRIES`, and blocks tool execution.
- **Alternative Scenarios:** AI proposes an unauthorized action name `REFUND_DISCOUNT`; policy immediately rejects with `UNAUTHORIZED_ACTION`.
- **Failure Scenarios:** None.
- **Dependencies:** Policy rule repository.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Veto proposal violating maximum retry limit
  GIVEN a recovery case that has already undergone 3 failed attempts
  WHEN the AI Decision Engine proposes an additional "RETRY_PAYMENT"
  THEN the Policy Enforcement Engine must emit PolicyDecision "REJECTED"
  AND the rejection reason must be "MAX_RETRIES_EXCEEDED"
  AND zero payment requests must be dispatched
  AND the case state must transition to "HALTED_MAX_RETRIES"
```
- **Related Functional Requirements:** FR-POL-002, FR-STP-001
- **Related Test Scenarios:** TS-POL-002 (Policy Rejection Veto)

---

#### US-POL-003: Enforce Hard Ban on Retrying Terminal Declines
- **Epic ID:** EPIC-07
- **Title:** Enforce Hard Ban on Retrying Terminal Declines
- **User Story:** As the Policy Enforcement Engine, I want to strictly prohibit retries on cards declined for fraud, theft, or closed accounts, so that the merchant never incurs card-scheme fines or fraud penalties.
- **Actor:** Policy Enforcement Engine
- **Business Value:** Mandatory card network compliance (Visa/Mastercard rules).
- **Priority:** **MUST**
- **Preconditions:** Case failure class is `HARD_DECLINE_STOLEN_CARD`.
- **Main Success Scenario:** Case is marked hard decline. Policy gate evaluates case, immediately blocks payment retry actions, marks case `HALTED_TERMINAL_DECLINE`, and requests customer payment method update.
- **Alternative Scenarios:** None.
- **Failure Scenarios:** None.
- **Dependencies:** Failure classification.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Prohibit retrying stolen or fraudulent card
  GIVEN a case with failure class "HARD_DECLINE_STOLEN_CARD"
  WHEN the Policy Enforcement Engine evaluates possible interventions
  THEN any payment retry action must be strictly prohibited
  AND the case must transition to "HALTED_TERMINAL_DECLINE"
  AND an audit event "HARD_DECLINE_RETRY_BLOCKED" must be logged
```
- **Related Functional Requirements:** FR-POL-003, FR-CLS-002
- **Related Test Scenarios:** TS-POL-003 (Hard Decline Ban)

---

### Epic: EPIC-08 & EPIC-09 — Workflow Execution & Stopping Rules

#### US-WFK-001: Orchestrate Recovery Workflow State Transitions
- **Epic ID:** EPIC-08
- **Title:** Orchestrate Recovery Workflow State Transitions
- **User Story:** As the Recovery Workflow Engine, I want to manage the progression of cases across discrete state machine states, so that invalid transitions and race conditions are strictly prevented.
- **Actor:** Recovery Workflow Engine
- **Business Value:** Ensures predictable, crash-resilient lifecycle execution.
- **Priority:** **MUST**
- **Preconditions:** Case is stateful entity in database.
- **Main Success Scenario:** Engine moves case cleanly through: `DETECTED` -> `ELIGIBILITY_CHECK` -> `DIAGNOSING` -> `ACTION_PENDING` -> `POLICY_APPROVED` -> `ACTION_EXECUTING` -> `WAITING_FOR_VERIFICATION` -> `RECOVERED`.
- **Alternative Scenarios:** Illegal transition attempted (e.g., jumping from `DETECTED` directly to `ACTION_EXECUTING`); engine throws `InvalidStateTransitionException` and rolls back.
- **Failure Scenarios:** Concurrency collision; row-level lock ensures single worker progression.
- **Dependencies:** State transition table.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Enforce legal workflow state progression
  GIVEN a recovery case in state "POLICY_APPROVED"
  WHEN the Workflow Engine initiates action execution
  THEN the case state must transition to "ACTION_EXECUTING"
  AND attempting to transition directly to "CLOSED" without verification must throw an error
  AND the state update must be committed atomically in the database
```
- **Related Functional Requirements:** FR-WFK-001
- **Related Test Scenarios:** TS-WFK-001 (State Machine Transitions)

---

#### US-WFK-002: Dispatch Payment Action via Gateway Simulator
- **Epic ID:** EPIC-08
- **Title:** Dispatch Payment Action via Gateway Simulator
- **User Story:** As the Recovery Workflow Engine, I want to execute approved actions exclusively through a controlled payment provider simulator with unique idempotency keys, so that actions are safely tested without real-money exposure.
- **Actor:** Recovery Workflow Engine
- **Business Value:** Eliminates financial liability during testing while verifying real distributed API mechanics.
- **Priority:** **MUST**
- **Preconditions:** Case in state `POLICY_APPROVED`.
- **Main Success Scenario:** Workflow generates idempotency key `idemp_case_101_att_1`, invokes simulated gateway adapter, simulator processes virtual debit, and returns HTTP 200 with transaction response.
- **Alternative Scenarios:** None.
- **Failure Scenarios:** Simulator connection drops; handled as uncertain outcome.
- **Dependencies:** Simulated Payment Provider adapter.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Dispatch payment retry with unique idempotency key
  GIVEN a case in state "POLICY_APPROVED" with case ID "case_551" and attempt 1
  WHEN the Workflow Engine invokes the Simulated Payment Provider
  THEN it must generate idempotency key "idemp_case_551_att_1"
  AND must pass amount 4500 minor units and currency "USD"
  AND must transition case to "ACTION_EXECUTING"
  AND must record the dispatch in the audit ledger
```
- **Related Functional Requirements:** FR-WFK-002, FR-IDP-001
- **Related Test Scenarios:** TS-WFK-002 (Idempotent Action Dispatch)

---

#### US-STP-001: Enforce Maximum Retry Budget Ceilings
- **Epic ID:** EPIC-09
- **Title:** Enforce Maximum Retry Budget Ceilings
- **User Story:** As the Recovery Workflow Engine, I want to increment an immutable attempt counter on each execution and halt when the ceiling is reached, so that no case is ever retried more than 3 times.
- **Actor:** Recovery Workflow Engine
- **Business Value:** Prevents infinite retry loops and payment processor fraud penalties.
- **Priority:** **MUST**
- **Preconditions:** Action executed and returned failure.
- **Main Success Scenario:** Attempt 3 fails. Workflow increments counter to 3, evaluates stopping rule `attempt_count >= 3`, halts workflow, and transitions case to `HALTED_MAX_RETRIES`.
- **Alternative Scenarios:** Case is eligible for human review; routed to `ESCALATED_HUMAN_REVIEW`.
- **Failure Scenarios:** None.
- **Dependencies:** Attempt counter column.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Halt case when retry budget is exhausted
  GIVEN a recovery case has completed attempt 3 with a decline outcome
  WHEN the Workflow Engine evaluates the post-execution state
  THEN the attempt counter must equal 3
  AND the case state must transition to "HALTED_MAX_RETRIES"
  AND no further retries may be scheduled
  AND an audit event "RETRY_BUDGET_EXHAUSTED" must be recorded
```
- **Related Functional Requirements:** FR-STP-001
- **Related Test Scenarios:** TS-STP-001 (Retry Budget Exhaustion)

---

#### US-STP-002: Halt Workflow Immediately on Confirmed Success
- **Epic ID:** EPIC-09
- **Title:** Halt Workflow Immediately on Confirmed Success
- **User Story:** As the Recovery Workflow Engine, I want to immediately terminate the recovery workflow once payment success is confirmed, so that no further attempts can ever be dispatched.
- **Actor:** Recovery Workflow Engine
- **Business Value:** Core financial invariant: protects customers from secondary debits.
- **Priority:** **MUST**
- **Preconditions:** Provider receipt verified with status `succeeded`.
- **Main Success Scenario:** Gateway returns verified success on attempt 1. Workflow transitions case to `RECOVERED`, cancels any scheduled timers, and marks case as terminal.
- **Alternative Scenarios:** None.
- **Failure Scenarios:** None.
- **Dependencies:** Outcome verification engine.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Terminate workflow upon verified payment success
  GIVEN an active recovery case in state "WAITING_FOR_VERIFICATION"
  WHEN authoritative provider receipt confirms status "succeeded"
  THEN the case state must transition to terminal state "RECOVERED"
  AND all pending retries or reminders must be permanently canceled
  AND confirmed recovered revenue must be updated
```
- **Related Functional Requirements:** FR-STP-002, FR-VRF-001
- **Related Test Scenarios:** TS-STP-002 (Terminal Success Stopping)

---

#### US-STP-003: Escalate High-Value or Anomalous Cases to Human
- **Epic ID:** EPIC-09
- **Title:** Escalate High-Value or Anomalous Cases to Human
- **User Story:** As the Recovery Workflow Engine, I want to route cases exceeding $1,000 or exhibiting low model confidence to a human review queue, so that operators retain control over high-stakes transactions.
- **Actor:** Recovery Workflow Engine / Recovery Operator
- **Business Value:** Human-in-the-loop safety valve for high financial exposure.
- **Priority:** **MUST**
- **Preconditions:** Case amount >= 100,000 minor units ($1,000.00).
- **Main Success Scenario:** A $2,500 invoice fails. Policy gate detects amount exceeds threshold, blocks autonomous retry, transitions case to `ESCALATED_HUMAN_REVIEW`, and adds case to operator queue.
- **Alternative Scenarios:** Operator approves case in UI; workflow dispatches action. Operator rejects; case halts.
- **Failure Scenarios:** Operator queue unread; alerts generated after 24h.
- **Dependencies:** Operator escalation inbox.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Escalate high-value transaction to operator queue
  GIVEN a recovery case with nominal amount 250000 minor units ($2,500.00)
  WHEN the Policy Enforcement Engine checks escalation thresholds
  THEN automated tool execution must be halted
  AND the case state must transition to "ESCALATED_HUMAN_REVIEW"
  AND the case must appear in the Operator Escalation Inbox
```
- **Related Functional Requirements:** FR-STP-003
- **Related Test Scenarios:** TS-STP-003 (High-Value Human Escalation)

---

### Epic: EPIC-10 — Outcome Verification & Attribution

#### US-VRF-001: Verify Settlement via Authoritative Gateway Receipt
- **Epic ID:** EPIC-10
- **Title:** Verify Settlement via Authoritative Gateway Receipt
- **User Story:** As the Recovery Workflow Engine, I want to verify payment settlement using authoritative provider receipts matching transaction ID, amount, and currency, so that financial claims are 100% factual.
- **Actor:** Recovery Workflow Engine / Auditor
- **Business Value:** Eliminates phantom revenue claims; guarantees auditable financial integrity.
- **Priority:** **MUST**
- **Preconditions:** Action dispatched to simulator.
- **Main Success Scenario:** Simulator returns receipt: `transaction_id: "txn_881"`, `status: "succeeded"`, `amount: 4500`, `currency: "USD"`. Verifier validates fields match case, transitions case to `RECOVERED`, and credits $45.00 to confirmed recovered revenue.
- **Alternative Scenarios:** Receipt reports `status: "failed"`; case schedules permitted retry or halts.
- **Failure Scenarios:** Receipt amount does not match case amount; verifier flags discrepancy and escalates.
- **Dependencies:** Simulated Payment Provider receipt parser.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Verify payment capture with matching provider receipt
  GIVEN a case in state "WAITING_FOR_VERIFICATION" with amount 4500 USD
  WHEN the Simulated Payment Provider returns status "succeeded" with amount 4500 USD and transaction ID "txn_881"
  THEN the Outcome Verifier must validate the receipt parameters
  AND the case state must transition to "RECOVERED"
  AND Confirmed Recovered Revenue must increment by 4500 minor units
  AND an audit event "SETTLEMENT_VERIFIED" must be permanently recorded
```
- **Related Functional Requirements:** FR-VRF-001
- **Related Test Scenarios:** TS-VRF-001 (Authoritative Receipt Verification)

---

#### US-VRF-002: Preserve Uncertainty on Provider Timeout
- **Epic ID:** EPIC-10
- **Title:** Preserve Uncertainty on Provider Timeout
- **User Story:** As the Recovery Workflow Engine, I want to flag network timeouts and ambiguous gateway responses as `UNCERTAIN`, so that the system never assumes failure and never double-charges a customer.
- **Actor:** Recovery Workflow Engine
- **Business Value:** Eliminates duplicate billing caused by network socket drops.
- **Priority:** **MUST**
- **Preconditions:** Action dispatched to simulator.
- **Main Success Scenario:** Gateway connection drops after 15s (HTTP 504). Verifier marks outcome `UNCERTAIN`, transitions case to `VERIFICATION_PENDING`, freezes automated retries, and schedules status reconciliation.
- **Alternative Scenarios:** Reconciliation poll confirms charge succeeded; transitions to `RECOVERED`. Poll confirms failure; permits retry.
- **Failure Scenarios:** Ambiguity persists after 3 polls; escalates to human operator.
- **Dependencies:** Reconciliation poller.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Handle gateway timeout as uncertain outcome
  GIVEN a payment retry was dispatched to the gateway
  WHEN the network connection times out with HTTP 504 without a definitive response
  THEN the Outcome Verifier must classify the result as "UNCERTAIN"
  AND the case state must transition to "VERIFICATION_PENDING"
  AND immediate secondary retries must be strictly blocked
  AND a background reconciliation check must be scheduled
```
- **Related Functional Requirements:** FR-VRF-002
- **Related Test Scenarios:** TS-VRF-002 (Uncertain Timeout Preservation)

---

#### US-VRF-003: Enforce Attribution Window and Deduplication
- **Epic ID:** EPIC-10
- **Title:** Enforce Attribution Window and Deduplication
- **User Story:** As the Recovery Workflow Engine, I want to credit successful payments only if they occur within 72 hours of an authorized recovery action, so that unrelated organic payments are not falsely claimed.
- **Actor:** Recovery Workflow Engine / Auditor
- **Business Value:** Guarantees metric integrity and prevents over-attribution.
- **Priority:** **MUST**
- **Preconditions:** Successful payment event received.
- **Main Success Scenario:** Payment settles 12 hours after action dispatch. Timestamp is within 72h window, idempotency token matches. Verifier attributes recovery to the action.
- **Alternative Scenarios:** Payment settles 10 days after action without idempotency match; classified as `ORGANIC_PAYMENT_UNATTRIBUTED` and excluded from recovery metrics.
- **Failure Scenarios:** None.
- **Dependencies:** Timestamp validator.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Reject attribution for payment outside 72-hour window
  GIVEN a recovery action was dispatched at 2026-11-01 10:00:00 UTC
  WHEN a successful payment arrives for the invoice at 2026-11-06 10:00:00 UTC (120 hours later)
  THEN the Outcome Verifier must classify it as "ORGANIC_SETTLEMENT"
  AND must not attribute the revenue to the automated recovery engine
  AND must record an audit event "ATTRIBUTION_WINDOW_EXPIRED"
```
- **Related Functional Requirements:** FR-VRF-003, FR-ATR-001
- **Related Test Scenarios:** TS-VRF-003 (Attribution Window Enforcement)

---

### Epic: EPIC-11 — Immutable Audit History

#### US-AUD-001: Record Immutable Append-Only Audit Trail
- **Epic ID:** EPIC-11
- **Title:** Record Immutable Append-Only Audit Trail
- **User Story:** As the Recovery Workflow Engine, I want to append an immutable audit record for every decision, policy check, and tool execution, so that every action is fully traceable and tamper-evident.
- **Actor:** Recovery Workflow Engine / Auditor
- **Business Value:** Guarantees legal, financial, and operational auditability.
- **Priority:** **MUST**
- **Preconditions:** State transition or policy evaluation occurs.
- **Main Success Scenario:** Case transitions from `AWAITING_DECISION` to `POLICY_APPROVED`. Audit engine writes record with `timestamp`, `case_id`, `correlation_id`, `actor: "POLICY_GATE"`, `action: "APPROVE_RETRY"`, and payload SHA-256 hash.
- **Alternative Scenarios:** None.
- **Failure Scenarios:** Database write fails; workflow rolls back transaction to preserve consistency.
- **Dependencies:** Relational audit table with append-only permissions.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Append immutable audit record on state transition
  GIVEN a recovery case undergoes a policy evaluation
  WHEN the Policy Enforcement Engine approves the action
  THEN an audit record must be appended to the immutable audit table
  AND the record must contain timestamp, case_id, correlation_id, actor, and payload hash
  AND database UPDATE or DELETE operations on the audit table must be strictly prohibited
```
- **Related Functional Requirements:** FR-AUD-001
- **Related Test Scenarios:** TS-AUD-001 (Append-Only Audit Logging)

---

#### US-AUD-002: Inspect Sequential Audit History by Correlation ID
- **Epic ID:** EPIC-11
- **Title:** Inspect Sequential Audit History by Correlation ID
- **User Story:** As an Auditor or RevOps Analyst, I want to query the complete chronological timeline of events for a case by its correlation ID, so that I can reconstruct exactly how a recovery outcome was achieved.
- **Actor:** Auditor / Reviewer / RevOps Analyst
- **Business Value:** Enables instant root-cause analysis and compliance verification.
- **Priority:** **MUST**
- **Preconditions:** Case has completed or in-flight audit records.
- **Main Success Scenario:** Auditor calls `GET /api/v1/cases/{id}/audit`. API returns ordered chronological list of all audit records from `CASE_DETECTED` to `SETTLEMENT_VERIFIED`.
- **Alternative Scenarios:** Case has zero audit records; returns empty list with HTTP 200.
- **Failure Scenarios:** Case ID not found; returns HTTP 404.
- **Dependencies:** Audit query API.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Retrieve full sequential audit history for a case
  GIVEN a completed recovery case with case ID "case_882"
  WHEN an auditor requests the audit trail for "case_882"
  THEN the API must return a sequential list of audit events ordered by timestamp
  AND each event must display actor, state transition, policy status, and timestamp
  AND no records may be omitted or altered
```
- **Related Functional Requirements:** FR-AUD-002
- **Related Test Scenarios:** TS-AUD-002 (Audit History Retrieval)

---

### Epic: EPIC-13 — Dashboard Command Center & Case Management

#### US-DSH-001: View Real-Time Financial Recovery KPIs
- **Epic ID:** EPIC-13
- **Title:** View Real-Time Financial Recovery KPIs
- **User Story:** As a Finance Manager, I want to view high-altitude KPI cards displaying Confirmed Recovered Revenue, Revenue at Risk, and Recovery Rate, so that I have instant visibility into financial recovery performance.
- **Actor:** Finance Manager
- **Business Value:** Provides executive leadership with accurate, real-time financial tracking.
- **Priority:** **MUST**
- **Preconditions:** Backend analytics endpoint is operational.
- **Main Success Scenario:** User loads dashboard. Frontend calls `GET /api/v1/metrics/overview`. UI renders five KPI cards with tabular numerals: Confirmed Recovered ($), Revenue at Risk ($), Recovery Rate (%), Active Cases, and Blocked Violations (100% defended).
- **Alternative Scenarios:** No cases exist yet; KPI cards render zero state (`$0.00`, `0.0%`).
- **Failure Scenarios:** API returns 500; KPI cards display graceful error state with retry button.
- **Dependencies:** Analytics aggregation endpoint, Dark neon UI components.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Render executive recovery KPI cards
  GIVEN verified recovery cases exist in the database
  WHEN the Finance Manager navigates to the Command Center dashboard
  THEN the dashboard must display Confirmed Recovered Revenue in currency format
  AND must display Revenue at Risk in currency format
  AND must display Case Recovery Rate and Revenue Recovery Rate percentages
  AND all monetary values must use tabular monospace numerals
```
- **Related Functional Requirements:** FR-DSH-001, FR-DSH-002
- **Related Test Scenarios:** TS-DSH-001 (KPI Card Rendering)

---

#### US-DSH-002: Search, Filter, and Inspect Recovery Case Queue
- **Epic ID:** EPIC-13
- **Title:** Search, Filter, and Inspect Recovery Case Queue
- **User Story:** As a RevOps Analyst, I want to search and filter the active recovery case queue by state, failure code, and customer ID, so that I can rapidly locate and manage specific transactions.
- **Actor:** RevOps Analyst
- **Business Value:** Optimizes operational productivity and case triaging.
- **Priority:** **MUST**
- **Preconditions:** Cases exist in database.
- **Main Success Scenario:** Analyst types "insufficient_funds" in failure filter and selects state `VERIFICATION_PENDING`. Table immediately filters to display matching cases with status badges and risk amounts.
- **Alternative Scenarios:** Search query yields no results; table renders clear empty state.
- **Failure Scenarios:** None.
- **Dependencies:** Case list REST endpoint (`GET /api/v1/cases`).
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Filter recovery queue by workflow state
  GIVEN multiple cases exist across states "DETECTED", "RECOVERED", and "ESCALATED"
  WHEN the RevOps Analyst filters the queue by state "ESCALATED"
  THEN the table must render only cases in state "ESCALATED"
  AND each row must display Case ID, Customer, Amount, Failure Class, and State Badge
  AND the count of filtered results must match the table records
```
- **Related Functional Requirements:** FR-DSH-003
- **Related Test Scenarios:** TS-DSH-002 (Queue Search and Filtering)

---

#### US-DSH-003: Inspect End-to-End Case Diagnostic Trace Drawer
- **Epic ID:** EPIC-13
- **Title:** Inspect End-to-End Case Diagnostic Trace Drawer
- **User Story:** As a RevOps Analyst, I want to click any case row to open an explainable diagnostic trace drawer, so that I can inspect the raw failure telemetry, AI reasoning, policy rules evaluated, and settlement receipt.
- **Actor:** RevOps Analyst
- **Business Value:** Provides complete operational transparency into automated AI decisions.
- **Priority:** **MUST**
- **Preconditions:** Case exists in table.
- **Main Success Scenario:** Analyst clicks row for `case_104`. Right-side slide-over drawer opens displaying: (1) Header with amount and state, (2) Raw Gateway Code, (3) AI Diagnostic Class & Rationale, (4) Policy Evaluation Rules (Pass/Fail), and (5) Gateway Receipt Token.
- **Alternative Scenarios:** Drawer is closed via `Escape` key or backdrop click.
- **Failure Scenarios:** Trace details fail to load; drawer displays error notification.
- **Dependencies:** Case detail endpoint (`GET /api/v1/cases/{id}`).
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Open case diagnostic trace drawer
  GIVEN the user is viewing the Recovery Case Queue
  WHEN the user clicks on Case ID "case_104"
  THEN an inspectable detail drawer must slide open
  AND must display raw failure telemetry, AI reasoning rationale, policy check results, and settlement receipt
  AND must visually render the sequential timeline of audit transitions
```
- **Related Functional Requirements:** FR-DSH-004
- **Related Test Scenarios:** TS-DSH-003 (Diagnostic Trace Drawer)

---

#### US-DSH-004: Review and Resolve Escalated Recovery Cases
- **Epic ID:** EPIC-13
- **Title:** Review and Resolve Escalated Recovery Cases
- **User Story:** As a Recovery Operator, I want to review cases in the escalation queue and approve or reject recovery actions, so that high-risk edge cases are safely resolved with human oversight.
- **Actor:** Recovery Operator
- **Business Value:** Closes the human-in-the-loop safety loop.
- **Priority:** **MUST**
- **Preconditions:** Case in state `ESCALATED_HUMAN_REVIEW`.
- **Main Success Scenario:** Operator opens escalated case, reviews context, clicks "Approve Retry". System records operator ID in audit trail, transitions case to `POLICY_APPROVED`, and dispatches retry via simulator.
- **Alternative Scenarios:** Operator clicks "Halt Case"; case transitions to `HALTED_OPERATOR_REJECTED`.
- **Failure Scenarios:** None.
- **Dependencies:** Escalation resolution API (`POST /api/v1/cases/{id}/escalation-action`).
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Operator approves escalated recovery action
  GIVEN a case in state "ESCALATED_HUMAN_REVIEW"
  WHEN the Recovery Operator reviews the case and clicks "Approve Retry"
  THEN the system must record operator ID in the audit trail
  AND the case state must transition to "POLICY_APPROVED"
  AND the recovery action must be dispatched via the simulator
```
- **Related Functional Requirements:** FR-DSH-005, FR-STP-003
- **Related Test Scenarios:** TS-DSH-004 (Human Escalation Resolution)

---

### Epic: EPIC-14 — Batch Evaluation Lab & Baseline Comparison

#### US-EVL-001: Execute Reproducible 500-Scenario Batch Evaluation
- **Epic ID:** EPIC-14
- **Title:** Execute Reproducible 500-Scenario Batch Evaluation
- **User Story:** As a RevOps Analyst, I want to run a 500-scenario batch simulation under fixed seed 42, so that system recovery performance is benchmarked scientifically and reproducibly.
- **Actor:** RevOps Analyst
- **Business Value:** Replaces guesswork with rigorous, reproducible regression benchmarking.
- **Priority:** **MUST**
- **Preconditions:** Evaluation harness and scenario fixtures available.
- **Main Success Scenario:** Analyst runs evaluation CLI/API with `--seed 42 --count 500`. Engine runs all 500 scenarios through the virtual clock and outputs report with exact recovery rates, zero safety violations, and matching checksums.
- **Alternative Scenarios:** Analyst runs with different seed (e.g., seed 101); generates new randomized cohort.
- **Failure Scenarios:** Invariant violation detected during run; evaluation halts immediately with regression alert.
- **Dependencies:** Evaluation simulation engine, Virtual Clock.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Run reproducible 500-scenario evaluation batch
  GIVEN the Evaluation Engine is initialized with seed 42 and scenario count 500
  WHEN the batch simulation is executed
  THEN exactly 500 deterministic scenarios must be processed
  AND the output report must be generated with matching metrics across repeated runs
  AND safety violation rate must be exactly 0.00%
  AND all results must be explicitly labeled synthetic regression fixtures
```
- **Related Functional Requirements:** FR-EVL-001
- **Related Test Scenarios:** TS-EVL-001 (Reproducible Batch Simulation)

---

#### US-EVL-002: Benchmark Recovery Lift Against Baselines
- **Epic ID:** EPIC-14
- **Title:** Benchmark Recovery Lift Against Baselines
- **User Story:** As a Finance Manager, I want to compare RevenueRescueAI's recovery performance against standard counterfactual baselines, so that I can mathematically prove the value of intelligent recovery over dumb retrying.
- **Actor:** Finance Manager
- **Business Value:** Quantifies the net return on investment (ROI) of intelligent recovery logic.
- **Priority:** **MUST**
- **Preconditions:** Batch evaluation has completed.
- **Main Success Scenario:** Report renders side-by-side comparison table: (1) Do-Nothing Baseline (0% recovery), (2) Always-Retry Baseline (32% recovery, high fees), (3) Simple Rule-Based (38% recovery), (4) RevenueRescueAI (45.3% recovery), (5) Oracle Bound. Shows relative lift and net financial gain.
- **Alternative Scenarios:** None.
- **Failure Scenarios:** None.
- **Dependencies:** Counterfactual baseline models.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Compare recovery engine against counterfactual baselines
  GIVEN a completed evaluation run on 500 scenarios
  WHEN the comparative baseline analysis is generated
  THEN the report must display recovery metrics for Do-Nothing, Always-Retry, Rule-Based, and RevenueRescueAI
  AND must calculate relative percentage lift over each baseline
  AND must display net recovered revenue after simulated gateway fees
```
- **Related Functional Requirements:** FR-EVL-002
- **Related Test Scenarios:** TS-EVL-002 (Baseline Comparison Verification)

---

#### US-EVL-003: Export Auditable Evaluation Report
- **Epic ID:** EPIC-14
- **Title:** Export Auditable Evaluation Report
- **User Story:** As an Auditor, I want to export the complete serialized JSON evaluation report and scenario manifest, so that third parties can independently verify the evaluation findings.
- **Actor:** Auditor / Reviewer
- **Business Value:** Enables independent verification and academic/commercial compliance audit.
- **Priority:** **MUST**
- **Preconditions:** Evaluation report generated.
- **Main Success Scenario:** Auditor exports `artifacts/evaluation_report_500.json`. File contains run timestamp, git commit hash, seed (42), scenario count (500), metric summary, baseline table, and individual scenario results.
- **Alternative Scenarios:** Export as CSV summary.
- **Failure Scenarios:** None.
- **Dependencies:** File serialization service.
- **Acceptance Criteria (Gherkin):**
```gherkin
Scenario: Export serialized evaluation report artifact
  GIVEN an evaluation simulation run has completed
  WHEN the export report action is triggered
  THEN a valid JSON file must be saved to "artifacts/evaluation_report_500.json"
  AND the JSON must include seed, scenario count, metric formulas, baseline metrics, and scenario breakdown
  AND the file must contain explicit disclaimers that data is synthetic
```
- **Related Functional Requirements:** FR-EVL-003
- **Related Test Scenarios:** TS-EVL-003 (Evaluation Artifact Serialization)
