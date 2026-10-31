# RevenueRescueAI — Business Rules & Governance Invariants

> **Document ID:** DOC-BR-005  
> **Phase:** 0.2 (User Stories, Functional Requirements & Acceptance Criteria)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

In fintech systems, business rules are not merely guidelines—they are non-negotiable operational invariants. A single violation of a rule such as "never charge an already-paid invoice" results in direct financial harm, customer complaints, and potential regulatory sanctions.

This document formally defines the core business rules governing RevenueRescueAI. Each rule has a stable identifier (e.g., `BR-001`), an explicit rationale, an execution trigger, mandatory system behaviors, permissible exceptions (if any), and direct mapping to user stories and test scenarios.

---

## 2. Master Business Rules Index

| Rule ID | Rule Name | Core Governance Invariant | Strictness |
|---|---|---|:---:|
| **BR-001** | Success Protection Invariant | Never dispatch a recovery attempt on an already-settled invoice. | **ABSOLUTE** |
| **BR-002** | Terminal Hard Decline Prohibition | Never retry a card declined for fraud, theft, or closed account. | **ABSOLUTE** |
| **BR-003** | Maximum Retry Budget Ceiling | Never exceed 3 total recovery attempts on any case. | **ABSOLUTE** |
| **BR-004** | Minimum Backoff Interval | Retries must enforce at least 24 hours between attempts. | **MANDATORY** |
| **BR-005** | Maximum Recovery Window Cutoff | Cases older than 14 calendar days must be permanently halted. | **MANDATORY** |
| **BR-006** | Action-Level Idempotency | Every tool dispatch must carry a deterministic unique token. | **ABSOLUTE** |
| **BR-007** | Three-Valued Uncertainty | Timeouts must freeze automated actions in `VERIFICATION_PENDING`. | **ABSOLUTE** |
| **BR-008** | Integer Minor Units Invariant | All financial values must be stored strictly as 64-bit integers. | **ABSOLUTE** |
| **BR-009** | Action Taxonomy Allow-List | AI proposals must match the strict 5-action enum. | **ABSOLUTE** |
| **BR-010** | Policy Gate Supremacy | AI recommendations cannot self-authorize financial execution. | **ABSOLUTE** |
| **BR-011** | Strict 72-Hour Attribution | Success must settle within 72h of action to claim recovery. | **MANDATORY** |
| **BR-012** | Authoritative Settlement Proof | Revenue is recovered only upon receipt of provider capture token. | **ABSOLUTE** |
| **BR-013** | Communication Opt-Out Compliance | Customer opt-out immediately suppresses all communication tools. | **ABSOLUTE** |
| **BR-014** | High-Value Human Escalation | Transactions >= $1,000 mandate human operator review. | **MANDATORY** |
| **BR-015** | Append-Only Audit Immutability | Audit records can never be updated, modified, or deleted. | **ABSOLUTE** |
| **BR-016** | Mandatory Simulation Disclosure | Synthetic evaluation results must never be claimed as live revenue. | **ABSOLUTE** |

---

## 3. Detailed Business Rules Specifications

---

### BR-001: Success Protection Invariant
- **Rule ID:** BR-001
- **Rule Description:** A payment or invoice that has already been confirmed as successful, paid, or settled cannot enter another recovery attempt under any circumstances.
- **Reason / Business Rationale:** Protects customers from double-charging and protects merchants from chargeback disputes, merchant fines, and severe customer churn.
- **Trigger:** Pre-eligibility evaluation, pre-policy check, and pre-tool dispatch.
- **Required System Behavior:** The system queries the authoritative ledger. If `invoice.status == "PAID"`, the workflow halts immediately, cancels all scheduled retries, and transitions case to `RESOLVED_ALREADY_PAID`.
- **Exceptions:** None. Absolute invariant.
- **Related User Stories:** US-ELG-002, US-STP-002
- **Related Test Scenarios:** TS-ELG-002, TS-STP-002

---

### BR-002: Terminal Hard Decline Prohibition
- **Rule ID:** BR-002
- **Rule Description:** A payment failure classified as a permanent hard decline (`stolen_card`, `lost_card`, `account_closed`, `fraudulent`) must never be retried via payment debit rails.
- **Reason / Business Rationale:** Visa and Mastercard rules levy immediate fines on merchants who re-attempt charges on known stolen or fraudulent cards. Hard declines indicate credentials that can never succeed.
- **Trigger:** Failure classification and Policy Gate evaluation.
- **Required System Behavior:** The Policy Gate evaluates decline severity. If `severity == HARD`, any retry proposal is vetoed with reason `HARD_DECLINE_PROHIBITED`. The case transitions to `HALTED_TERMINAL_DECLINE`.
- **Exceptions:** If the customer submits an entirely new payment credential, a new payment attempt on the new card is permitted under a fresh token.
- **Related User Stories:** US-RSK-003, US-POL-003
- **Related Test Scenarios:** TS-CLS-001, TS-POL-003

---

### BR-003: Maximum Retry Budget Ceiling
- **Rule ID:** BR-003
- **Rule Description:** An automated recovery case cannot exceed its configured retry budget of 3 total attempts.
- **Reason / Business Rationale:** Excessive retries irritate customers, trigger card-testing fraud blocks, and yield rapidly diminishing returns while incurring gateway fees.
- **Trigger:** Policy Gate evaluation prior to action authorization.
- **Required System Behavior:** Case maintains an integer counter `attempt_count`. If `attempt_count >= 3`, the Policy Gate emits `PolicyDecision: REJECTED` with reason `MAX_RETRIES_EXCEEDED` and terminates workflow.
- **Exceptions:** None for automated workflows. A human Recovery Operator may authorize one manual exception attempt after customer contact.
- **Related User Stories:** US-POL-002, US-STP-001
- **Related Test Scenarios:** TS-POL-002, TS-STP-001

---

### BR-004: Minimum Backoff Interval
- **Rule ID:** BR-004
- **Rule Description:** The interval between consecutive payment retry attempts on the same case must be at least 24 hours (1,440 minutes).
- **Reason / Business Rationale:** Rapid-fire retries on balance-declined cards fail repeatedly because bank balances do not replenish within minutes. Spaced retries respect banking clearing cycles.
- **Trigger:** Scheduling logic in Decision Engine and validation in Policy Gate.
- **Required System Behavior:** The Policy Gate asserts $(t_{\text{scheduled}} - t_{\text{last\_attempt}}) \ge 24\text{ hours}$. If interval is less than 24 hours, the proposal is rejected.
- **Exceptions:** Technical transient gateway errors (e.g., gateway 503) may execute a single exponential retry after 15 minutes if no debit occurred.
- **Related User Stories:** US-INT-001, US-POL-001
- **Related Test Scenarios:** TS-INT-001, TS-POL-001

---

### BR-005: Maximum Recovery Window Cutoff
- **Rule ID:** BR-005
- **Rule Description:** A recovery case cannot execute automated collection actions after 14 calendar days (336 hours) have elapsed from the initial failure timestamp.
- **Reason / Business Rationale:** Charging a customer's card weeks or months after an initial failure without fresh authorization violates consumer protection standards and surprises customers.
- **Trigger:** Case eligibility evaluation and pre-dispatch checks.
- **Required System Behavior:** System checks $(t_{\text{current}} - t_{\text{initial\_failure}}) \le 14\text{ days}$. If exceeded, transitions case to `HALTED_EXPIRED` and closes automated workflow.
- **Exceptions:** B2B invoice collection (deferred to post-MVP) may have longer aging brackets (30–60 days).
- **Related User Stories:** US-ELG-003
- **Related Test Scenarios:** TS-ELG-003

---

### BR-006: Action-Level Idempotency
- **Rule ID:** BR-006
- **Rule Description:** Every external recovery action dispatched to a payment provider must include a unique, deterministic idempotency token following `idemp_{case_id}_att_{attempt_number}`.
- **Reason / Business Rationale:** Guarantees that network retries or message queue redeliveries can never execute duplicate charges on the card rails.
- **Trigger:** Outbound tool dispatch by Workflow Engine.
- **Required System Behavior:** The Workflow Engine formats the token, logs it, and passes it in request headers. The payment simulator records the token and caches responses for identical tokens.
- **Exceptions:** None.
- **Related User Stories:** US-WFK-002, FR-IDP-001
- **Related Test Scenarios:** TS-WFK-002

---

### BR-007: Three-Valued Uncertainty Handling
- **Rule ID:** BR-007
- **Rule Description:** When an external payment action times out or returns an ambiguous response, the system must treat the outcome as `UNCERTAIN` and freeze automated retries until verified.
- **Reason / Business Rationale:** Assuming failure upon timeout leads directly to double-charging if the bank actually approved the first charge.
- **Trigger:** HTTP 504 Gateway Timeout, connection reset, or ambiguous gateway response.
- **Required System Behavior:** The Outcome Verifier flags status `UNCERTAIN`, sets state to `VERIFICATION_PENDING`, blocks new payment actions, and schedules asynchronous reconciliation polls.
- **Exceptions:** None.
- **Related User Stories:** US-VRF-002
- **Related Test Scenarios:** TS-VRF-002

---

### BR-008: Integer Minor Units Invariant
- **Rule ID:** BR-008
- **Rule Description:** All monetary amounts in database schemas, memory state, and metric calculations must be represented strictly as 64-bit signed integers in currency minor units (cents/paise).
- **Reason / Business Rationale:** Floating-point numbers introduce binary rounding artifacts (e.g., $0.1 + 0.2 = 0.30000000000000004$) that violate financial audit standards.
- **Trigger:** Webhook ingestion, quantification, metric computation.
- **Required System Behavior:** Floating-point database columns and API fields for currency values are strictly rejected. All arithmetic uses integer operations.
- **Exceptions:** User interface formatting converts integers to decimal strings strictly at the presentation layer (e.g., `4500` -> `"$45.00"`).
- **Related User Stories:** US-RSK-002, US-VRF-001
- **Related Test Scenarios:** TS-QNT-001

---

### BR-009: Action Taxonomy Allow-List
- **Rule ID:** BR-009
- **Rule Description:** The Decision Engine (AI) is strictly restricted to proposing actions from the predefined enum: `RETRY_PAYMENT`, `SCHEDULE_RETRY`, `SEND_PAYMENT_UPDATE_LINK`, `ESCALATE_TO_HUMAN`, or `HALT_RECOVERY`.
- **Reason / Business Rationale:** Prevents autonomous agents from hallucinating unauthorized capabilities (e.g., issuing refunds or modifying invoices).
- **Trigger:** AI proposal generation and schema validation.
- **Required System Behavior:** Pydantic parser validates proposed action string against enum. If invalid, proposal is discarded and deterministic fallback is applied.
- **Exceptions:** None.
- **Related User Stories:** US-INT-001, FR-INT-001
- **Related Test Scenarios:** TS-INT-001

---

### BR-010: Policy Gate Supremacy
- **Rule ID:** BR-010
- **Rule Description:** An AI model recommendation cannot independently authorize a financial transaction; deterministic code policy holds absolute veto authority over all actions.
- **Reason / Business Rationale:** AI models are non-deterministic and untrusted decision proposers; financial and legal compliance must be enforced by deterministic code.
- **Trigger:** Pre-execution workflow pipeline.
- **Required System Behavior:** The Workflow Engine rejects any tool dispatch request that lacks an accompanying `PolicyDecision(status="APPROVED")` generated by code.
- **Exceptions:** None. Fundamental core architectural principle.
- **Related User Stories:** US-POL-001, US-POL-002
- **Related Test Scenarios:** TS-POL-001, TS-POL-002

---

### BR-011: Strict 72-Hour Attribution Window
- **Rule ID:** BR-011
- **Rule Description:** A successful payment can be credited as recovered revenue if and only if it settles within 72 hours of an authorized recovery action dispatch.
- **Reason / Business Rationale:** Prevents false recovery claims and eliminates claiming credit for organic customer payments made weeks or months later.
- **Trigger:** Outcome verification of successful payment events.
- **Required System Behavior:** Verifier evaluates $(t_{\text{settled}} - t_{\text{action}}) \le 72\text{ hours}$. If exceeded, payment is classified `ORGANIC_UNATTRIBUTED` and excluded from recovery metrics.
- **Exceptions:** None in MVP.
- **Related User Stories:** US-VRF-003
- **Related Test Scenarios:** TS-VRF-003

---

### BR-012: Authoritative Settlement Proof
- **Rule ID:** BR-012
- **Rule Description:** Revenue is declared recovered if and only if an authoritative provider receipt confirms successful capture matching transaction ID, amount, and currency.
- **Reason / Business Rationale:** Sent reminders and dispatched retries are not money; only verified bank deposits constitute revenue recovery.
- **Trigger:** Metric aggregation and case state finalization.
- **Required System Behavior:** Case state transitions to `RECOVERED` only when provider receipt with status `succeeded` is validated. Dispatched retries remain strictly as `attempts`.
- **Exceptions:** None.
- **Related User Stories:** US-VRF-001, US-DSH-001
- **Related Test Scenarios:** TS-VRF-001, TS-DSH-001

---

### BR-013: Communication Opt-Out Compliance
- **Rule ID:** BR-013
- **Rule Description:** If a customer has opted out of commercial communications (`communication_opted_out == True`), all automated customer notifications must be immediately suppressed.
- **Reason / Business Rationale:** Statutory compliance with TCPA, CAN-SPAM, and GDPR.
- **Trigger:** Eligibility check and notification tool evaluation.
- **Required System Behavior:** System blocks email/SMS actions for opted-out customers; permits only silent card retries if authorized under original merchant agreement.
- **Exceptions:** Mandatory transactional receipts confirming a successful charge are permitted.
- **Related User Stories:** US-ELG-003
- **Related Test Scenarios:** TS-ELG-003

---

### BR-014: High-Value Human Escalation
- **Rule ID:** BR-014
- **Rule Description:** Any recovery case where nominal revenue at risk >= 100,000 minor units ($1,000.00) must be routed to human operator review rather than automated execution.
- **Reason / Business Rationale:** Protects high-value merchant accounts from automated errors and provides personalized white-glove handling.
- **Trigger:** Policy Gate evaluation.
- **Required System Behavior:** Policy gate flags amount >= 100,000, blocks automatic dispatch, transitions case to `ESCALATED_HUMAN_REVIEW`, and adds case to operator queue.
- **Exceptions:** Threshold can be adjusted in configuration by Finance Manager.
- **Related User Stories:** US-STP-003, US-DSH-004
- **Related Test Scenarios:** TS-STP-003

---

### BR-015: Append-Only Audit Immutability
- **Rule ID:** BR-015
- **Rule Description:** Audit records once written to the database can never be updated, altered, or deleted by any user or system component.
- **Reason / Business Rationale:** Satisfies compliance standards, supports forensic investigation, and prevents tampering with financial history.
- **Trigger:** Any database operation targeting audit tables.
- **Required System Behavior:** Database permissions enforce `INSERT` and `SELECT` only. Attempting `UPDATE` or `DELETE` throws a database permission error.
- **Exceptions:** None.
- **Related User Stories:** US-AUD-001, US-AUD-002
- **Related Test Scenarios:** TS-AUD-001

---

### BR-016: Mandatory Simulation Disclosure
- **Rule ID:** BR-016
- **Rule Description:** All batch evaluation reports, dashboard cards, and exported artifacts must explicitly disclose that metrics are synthetic simulation fixtures, not live production financial results.
- **Reason / Business Rationale:** Maintains engineering integrity and prevents misleading investors, auditors, or project evaluators.
- **Trigger:** Metric rendering, report generation, artifact serialization.
- **Required System Behavior:** UI headers and report JSON files include explicit disclosure: `"NOTICE: Synthetic regression benchmark. Not a live production financial claim."`
- **Exceptions:** None.
- **Related User Stories:** US-EVL-001, US-EVL-003
- **Related Test Scenarios:** TS-EVL-003
