# RevenueRescueAI — Domain Glossary & Technical Vocabulary

> **Document ID:** DOC-GL-005  
> **Phase:** 0.1 (Problem Analysis & Use-Case Selection)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

In financial software, ambiguous terminology causes severe bugs. For example, if one developer defines "payment" as an initial authorization attempt and another defines it as a settled bank deposit, double-counting and reconciliation errors will inevitably occur.

This document defines the essential business and technical vocabulary for RevenueRescueAI in simple, straightforward English. It explicitly classifies which domain entities belong to the initial MVP and which are deferred to future phases, ensuring the entire team operates from a shared, unambiguous conceptual model.

---

## 2. Core Domain Concepts & Plain-English Definitions

---

### 1. Payment
- **Plain-English Definition:** A discrete financial transaction representing the transfer of funds from a buyer to a merchant for a specific product, service, or billing period.
- **Purpose in Project:** Represents the primary financial record being monitored, attempted, or recovered.
- **In MVP?** **Yes.** Mandatory core entity.

### 2. Subscription
- **Plain-English Definition:** An ongoing commercial agreement where a customer is charged automatically on a recurring schedule (e.g., $29/month) for continued access to a service.
- **Purpose in Project:** Provides the business context for recurring payment failures, customer billing cycles, and involuntary churn risk.
- **In MVP?** **Yes (Conceptual / Simulated Context).** Simulated as the recurring parent of failed invoices.

### 3. Invoice
- **Plain-English Definition:** An itemized commercial bill issued to a customer stating the amount owed and the payment due date.
- **Purpose in Project:** Serves as the primary billing entity that links a customer to an amount due and tracks payment status (`draft`, `open`, `paid`, `uncollectible`).
- **In MVP?** **Yes.** Foundational tracking unit.

### 4. Customer / Account
- **Plain-English Definition:** The individual or business entity responsible for paying.
- **Purpose in Project:** Contains customer metadata (identifier, tenure, payment preferences, communication opt-out status, risk score).
- **In MVP?** **Yes.** Basic customer record required for policy rules.

### 5. Recovery Case
- **Plain-English Definition:** An active operational ticket created by the system when a payment failure or revenue-at-risk event is detected.
- **Purpose in Project:** Encapsulates the entire lifecycle of recovering a specific at-risk amount, tracking current state, attempt counts, diagnostics, policy decisions, and final disposition.
- **In MVP?** **Yes.** The primary stateful unit of work for the recovery engine.

### 6. Recovery Event
- **Plain-English Definition:** An asynchronous telemetry signal (typically an incoming webhook) emitted by an external system (payment gateway, bank, or billing platform) that changes the risk state of a transaction.
- **Purpose in Project:** Triggers the recovery lifecycle (e.g., `payment.failed`, `payment.succeeded`, `dispute.created`).
- **In MVP?** **Yes.** Event-driven ingestion foundation.

### 7. Risk Reason / Failure Reason
- **Plain-English Definition:** The categorized root cause explaining why a payment failed or why revenue is in jeopardy.
- **Purpose in Project:** Informs the AI diagnostic engine so it can select an appropriate recovery strategy (e.g., distinguishing temporary balance shortfalls from stolen cards).
- **In MVP?** **Yes.** Standardized taxonomy required.

### 8. Intervention
- **Plain-English Definition:** A strategic course of action selected to rescue revenue at risk (e.g., "automated card retry with delayed scheduling" or "send self-service update link").
- **Purpose in Project:** Represents the strategy proposed by the AI and evaluated by the policy gate.
- **In MVP?** **Yes.** High-level strategy descriptor.

### 9. Recovery Action
- **Plain-English Definition:** The concrete, technical operation executed by the system to fulfill an approved intervention (e.g., firing an HTTP API request to re-charge a card via a payment gateway adapter).
- **Purpose in Project:** The actual tool invocation with bounded parameters.
- **In MVP?** **Yes.** Controlled tool execution unit.

### 10. Workflow State
- **Plain-English Definition:** The current, explicit operational status of a recovery case within its state machine (e.g., `DETECTED`, `ELIGIBLE`, `AWAITING_DECISION`, `POLICY_APPROVED`, `ACTION_DISPATCHED`, `VERIFICATION_PENDING`, `RECOVERED`, `HALTED`).
- **Purpose in Project:** Prevents invalid state transitions and enforces deterministic progression.
- **In MVP?** **Yes.** State machine core.

### 11. Retry Policy
- **Plain-English Definition:** A deterministic set of mathematical rules governing when, how often, and at what intervals a failed payment is permitted to be re-attempted.
- **Purpose in Project:** Prevents excessive retries, ensures compliance with card network regulations, and protects customer goodwill.
- **In MVP?** **Yes.** Mandatory safety rule.

### 12. Escalation
- **Plain-English Definition:** The deliberate act of removing a case from automated processing and routing it to a human operator queue due to high risk, ambiguity, or policy violations.
- **Purpose in Project:** Provides a safety valve for edge cases, high-value transactions, or anomalies that an AI should not handle autonomously.
- **In MVP?** **Yes.** Mandatory safety requirement.

### 13. Payment Outcome
- **Plain-English Definition:** The definitive result of a payment or recovery attempt as reported by the authoritative payment gateway (e.g., `succeeded`, `failed`, or `uncertain`).
- **Purpose in Project:** Serves as the objective ground truth that drives case progression.
- **In MVP?** **Yes.** Ground truth verification.

### 14. Audit Event
- **Plain-English Definition:** An immutable, timestamped record documenting an action taken, a state transition, a policy decision, or an external response.
- **Purpose in Project:** Guarantees total observability, financial reconciliation, and compliance auditability.
- **In MVP?** **Yes.** Mandatory append-only ledger.

### 15. Evaluation Scenario
- **Plain-English Definition:** A synthetic, deterministic test case with a known ground-truth outcome used to evaluate recovery system performance, policy safety, and algorithm accuracy.
- **Purpose in Project:** Allows reproducible benchmarking of recovery strategies without risking live money or violating data privacy.
- **In MVP?** **Yes.** Foundation of the evaluation engine.

### 16. Recovery Result
- **Plain-English Definition:** The final financial and operational summary of a completed recovery case, recording whether revenue was recovered, how much was collected, how many attempts were made, and which policy governed the outcome.
- **Purpose in Project:** Serves as the source of truth for business reporting and metric calculation.
- **In MVP?** **Yes.** Reporting baseline.

---

## 3. Specialized Financial & Technical Terms

| Term | Plain-English Definition & Significance | Real-World Application |
|---|---|---|
| **Minor Units** | The smallest non-divisible fractional denomination of a currency represented as an integer (e.g., cents for USD/EUR, paise for INR). A $45.00 charge is stored strictly as `4500`. | **Never use floating-point numbers (`float`) for money** due to binary rounding errors (e.g., `0.1 + 0.2 = 0.30000000000000004`). |
| **Idempotency Key** | A unique string generated by the client and passed to an API endpoint ensuring that even if the identical request is received multiple times (due to retries or network replays), the operation is executed exactly once. | Prevents charging a customer's card twice when an initial network connection times out. |
| **Attribution Window** | A strictly defined time interval (e.g., 72 hours) following a recovery action during which a successful payment can be legitimately credited to that action. | Prevents taking credit for a payment that occurred 30 days later through an unrelated organic channel. |
| **Stale Pending** | A payment transaction that was initiated but has remained in a non-terminal "processing" state longer than the allowed timeout without an authoritative confirmation. | Flags frozen funds or dropped connections requiring automated status polling. |
| **Soft Decline** | A payment failure caused by a temporary, potentially recoverable condition (e.g., temporary bank server outage, slight balance deficit, temporary rate limit). | Eligible for intelligent, scheduled retry. |
| **Hard Decline** | A payment failure caused by a permanent, non-recoverable condition (e.g., stolen card, fraudulent card, closed bank account). | **Strictly ineligible for payment retries**; requires customer payment method replacement or service termination. |

---

## 4. MVP vs. Post-MVP Concept Boundary

To avoid scope creep and protect the beginner developer from unnecessary complexity, domain concepts are categorized by implementation phase:

### Mandatory for MVP
- `RecoveryCase`, `RecoveryEvent`, `Customer`, `Invoice`, `Payment`
- `FailureClassification` (Soft vs. Hard decline taxonomy)
- `RetryPolicy` (Attempt counts, backoff windows)
- `PolicyDecision` (Pass/Fail rules)
- `AuditEvent` (Append-only state history)
- `EvaluationScenario` (Batch regression fixtures)
- `MinorUnits` (Integer money representations)

### Unnecessary / Deferred Post-MVP
- **Multi-tier Invoice Disputes:** Legal dispute arbitration and credit-note adjustments.
- **Mandate Token Rotation:** Automated crypto-token renewal for banking mandates.
- **Multi-Currency FX Hedging:** Dynamic currency exchange conversion and hedging calculations.
- **Complex Dunning Cadences:** 14-stage multi-channel email/SMS marketing funnels.
- **Telephony Audio Streams:** Real-time VoIP session tokens and audio codecs.
- **Multi-Tenant Org Hierarchies:** Enterprise parent-subsidiary billing rollups.

---

## 5. Ambiguous Terms Requiring Later Decisions

The following terms have multiple industry interpretations and must be monitored during subsequent architectural phases:

1. **"Recovered":** Does "recovered" mean an authoritative gateway capture receipt was issued, or does it require funds to be settled and deposited in the merchant's commercial bank account (which can take 2 business days)?  
   *Provisional MVP Decision:* An authoritative provider capture receipt is accepted as confirmed recovery for the local simulation.
2. **"Net Recovery":** Should net recovery subtract estimated gateway processing fees (e.g., 2.9% + $0.30) and the cost of the recovery engine, or simply the gross captured amount?  
   *Provisional MVP Decision:* Gross recovery is the primary metric; a secondary simulated fee model will be defined in metrics specifications.
3. **"Involuntary Churn":** Does involuntary churn include customers who deliberately let their card expire to avoid paying without clicking "Cancel"?  
   *Provisional MVP Decision:* Any technical failure on an active, non-canceled subscription is treated as involuntary risk.
