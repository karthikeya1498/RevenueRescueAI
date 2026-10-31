# RevenueRescueAI — Safety, Security, Risk Register & Quality Objectives

> **Document ID:** DOC-RSK-008  
> **Phase:** 0.1 (Problem Analysis & Use-Case Selection)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

Financial recovery software operates directly adjacent to customer money, regulatory compliance, and personal data. A defect in a standard web application might result in a broken UI button; a defect in a financial recovery engine can result in double-charging customer bank accounts, violating consumer credit laws, or corrupting company balance sheets.

This document establishes the provisional Risk Register for RevenueRescueAI, analyzing fifteen specific operational and safety hazards. For each hazard, it defines preventative controls, detection mechanisms, and verification scenarios. Furthermore, it defines measurable Non-Functional Quality Objectives and catalogs jurisdiction-dependent compliance questions.

---

## 2. Comprehensive Risk Register (Fifteen Critical Hazards)

The following matrix assesses fifteen critical failure hazards across Likelihood (Low, Medium, High) and Severity (Minor, Moderate, Critical, Catastrophic).

---

### Hazard HAZ-001: Duplicate Recovery Actions
- **Description:** A network glitch, message queue redelivery, or concurrent worker execution dispatches two identical retry calls for the same failed payment.
- **Potential Impact:** Customer's card is charged twice for a single invoice, causing overdraft fees, chargeback disputes, and loss of customer trust.
- **Likelihood Assessment:** **High.** In distributed systems, at-least-once message delivery guarantees inevitably produce duplicate delivery events.
- **Severity Assessment:** **Critical.** Double-charging directly damages customer financial standing.
- **Preventive Control:** Unique, deterministic Idempotency Keys (`idemp_{case_id}_{attempt_num}`) enforced at both the database level and provider adapter layer.
- **Detection / Recovery Mechanism:** Database unique constraint violation catches duplicates; provider adapter rejects replayed tokens with cached response.
- **Verification Test Scenario:** Dispatch two identical concurrent retry requests with identical payload and idempotency key; assert that exactly one charge is executed and one is absorbed cleanly.
- **Required Before MVP?** **YES (Mandatory Blocking Invariant).**

---

### Hazard HAZ-002: Retrying a Payment that Already Succeeded
- **Description:** A customer independently pays an overdue invoice via a web portal, but the recovery engine dispatches a scheduled automated retry without checking settlement status.
- **Potential Impact:** Duplicate debit; customer charged twice for an invoice they already paid.
- **Likelihood Assessment:** **Medium.** Common in asynchronous billing systems where webhooks may lag.
- **Severity Assessment:** **Critical.** Causes immediate merchant chargeback liability.
- **Preventive Control:** Success Protection Invariant: The deterministic policy gate must query the authoritative ledger status immediately prior to dispatching any payment action; if status is `PAID` or `SETTLED`, execution is blocked.
- **Detection / Recovery Mechanism:** Pre-flight state check; provider returns `invoice_already_paid`.
- **Verification Test Scenario:** Set invoice status to `PAID`, trigger recovery action dispatch; assert that policy gate halts action with reason `PAYMENT_ALREADY_SUCCEEDED`.
- **Required Before MVP?** **YES (Mandatory Blocking Invariant).**

---

### Hazard HAZ-003: Treating an Unknown Payment Outcome as a Definite Failure
- **Description:** A retry call to the payment gateway times out after 30 seconds due to network socket drop; the system marks it as "failed" and immediately triggers another retry.
- **Potential Impact:** The initial charge may have actually succeeded at the bank; immediately retrying charges the customer a second time.
- **Likelihood Assessment:** **High.** Network timeouts are routine in payment gateway communications.
- **Severity Assessment:** **Critical.** Direct cause of phantom charges and duplicate billing.
- **Preventive Control:** Three-Valued Logic: Outcome verifier must treat timeouts as `UNCERTAIN` / `VERIFICATION_PENDING`. Immediate re-execution on uncertain states is strictly prohibited.
- **Detection / Recovery Mechanism:** Asynchronous reconciliation worker queries provider ledger using idempotency key after a mandatory cooldown window.
- **Verification Test Scenario:** Simulate gateway returning HTTP 504 Gateway Timeout; assert that case transitions to `VERIFICATION_PENDING` and secondary retries are blocked.
- **Required Before MVP?** **YES (Mandatory Blocking Invariant).**

---

### Hazard HAZ-004: Exceeding Retry Limits (Infinite Retry Storm)
- **Description:** An automated recovery loop continues retrying a declined payment indefinitely without a stopping condition.
- **Potential Impact:** Triggers anti-fraud alarms at Visa/Mastercard, merchant card-processing account suspension, and bank penalty fees.
- **Likelihood Assessment:** **Medium.** Frequent bug in naive recursive or event-driven agent loops.
- **Severity Assessment:** **Critical.** Can result in merchant termination by payment processors.
- **Preventive Control:** Hard Retry Budget: Integer attempt counter stored on the `RecoveryCase` entity; deterministic policy gate rejects any action where `attempt_count >= MAX_RETRIES` (default: 3).
- **Detection / Recovery Mechanism:** Policy gate emits `REJECTED_MAX_RETRIES_EXCEEDED` and terminates case to `HALTED_MAX_RETRIES`.
- **Verification Test Scenario:** Submit a case with `attempt_count = 3` for retry; assert that policy gate blocks action and transitions case to terminal state.
- **Required Before MVP?** **YES (Mandatory Blocking Invariant).**

---

### Hazard HAZ-005: Acting Outside the Allowed Recovery Window
- **Description:** The system attempts to recover an overdue invoice months after the initial failure event.
- **Potential Impact:** Surprise charge on customer account months later; violation of card scheme rules and dunning regulations.
- **Likelihood Assessment:** **Low.** Occurs when stale backlog queues are processed without age filters.
- **Severity Assessment:** **Moderate.** High dispute and churn probability.
- **Preventive Control:** Temporal Recovery Window: Policy rejects actions on cases where `current_timestamp > initial_failure_timestamp + MAX_RECOVERY_DAYS` (default: 14 days).
- **Detection / Recovery Mechanism:** Eligibility check verifies case age; flags case as `EXPIRED`.
- **Verification Test Scenario:** Pass a synthetic case with failure date 30 days in the past; assert that eligibility check marks it `INELIGIBLE_EXPIRED`.
- **Required Before MVP?** **YES (Mandatory Blocking Invariant).**

---

### Hazard HAZ-006: Sending Communications Without Appropriate Permission
- **Description:** System sends automated recovery emails or SMS to individuals who have not consented to commercial communications.
- **Potential Impact:** Fines under GDPR, CAN-SPAM, or TCPA; merchant domain blacklisted by spam filters.
- **Likelihood Assessment:** **Medium.** Common when marketing lists and transactional systems are improperly mixed.
- **Severity Assessment:** **Moderate.** Legal fines and brand damage.
- **Preventive Control:** Strict Channel Authorization: Tool boundary verifies customer notification preferences and transactional messaging exemptions.
- **Detection / Recovery Mechanism:** Communication dispatcher checks `customer.consent_status` prior to sending.
- **Verification Test Scenario:** Attempt to dispatch communication to a customer with missing consent; assert action is blocked.
- **Required Before MVP?** **Deferred (Real messaging is out of scope for MVP).**

---

### Hazard HAZ-007: Continuing After an Opt-Out
- **Description:** A customer replies "STOP" or clicks "Unsubscribe," but the automated recovery engine continues sending reminders.
- **Potential Impact:** Direct statutory violation of TCPA/CAN-SPAM; regulatory complaints.
- **Likelihood Assessment:** **Medium.** Occurs when opt-out webhooks fail to synchronize with active workflows.
- **Severity Assessment:** **Critical.** High risk of regulatory enforcement actions.
- **Preventive Control:** Instant Suppression Flag: Case model contains `communication_opted_out` boolean; policy gate enforces immediate zero-contact rule upon flag activation.
- **Detection / Recovery Mechanism:** Ingestion endpoint for opt-out events immediately updates customer profile and cancels scheduled notifications.
- **Verification Test Scenario:** Set customer `opt_out = True`; assert that communication tools throw a suppressed policy exception.
- **Required Before MVP?** **YES (Modeled as policy invariant in MVP).**

---

### Hazard HAZ-008: Applying an Incorrect Currency or Amount
- **Description:** Currency code mismatch (e.g., charging $100.00 as 100 JPY or 100 EUR) or floating-point rounding errors (charging $45.00 as $4,500.00).
- **Potential Impact:** Severe financial loss, customer overbilling, balance sheet errors.
- **Likelihood Assessment:** **Low.** Occurs when string parsing or multi-currency conversions are unvalidated.
- **Severity Assessment:** **Catastrophic.** Instant catastrophic financial and reputational harm.
- **Preventive Control:** Minor Units & ISO-4217 Currency Invariants: All amounts stored as integers; currency code enforced across case, action, and receipt.
- **Detection / Recovery Mechanism:** Schema validation rejects mismatched currency or non-integer amounts.
- **Verification Test Scenario:** Attempt to execute a retry with currency `EUR` against a case registered in `USD`; assert policy rejection.
- **Required Before MVP?** **YES (Mandatory Blocking Invariant).**

---

### Hazard HAZ-009: Incorrect Revenue Attribution
- **Description:** The system claims credit for a successful payment that was completed organically by the customer outside the recovery flow or after the recovery window closed.
- **Potential Impact:** Falsified executive metrics, misleading ROI reporting, deceptive performance claims.
- **Likelihood Assessment:** **High.** Extremely common in marketing and recovery systems with loose attribution models.
- **Severity Assessment:** **Moderate.** Corrupts internal financial analytics and decision-making.
- **Preventive Control:** Cryptographic & Temporal Attribution Matching: Payment receipt must match the exact case transaction ID, amount, currency, and occur within 72 hours of action dispatch.
- **Detection / Recovery Mechanism:** Attribution verifier rejects payments without matching dispatch correlation tokens.
- **Verification Test Scenario:** Record a successful payment 10 days after a recovery action; assert that it is classified as `ORGANIC_SETTLEMENT` and excluded from recovery metrics.
- **Required Before MVP?** **YES (Mandatory Blocking Invariant).**

---

### Hazard HAZ-010: Model-Generated Instructions That Bypass Policy
- **Description:** An LLM or AI agent generates a hallucinated action (e.g., `FORCE_CHARGE_CARD` or `ISSUE_FULL_REFUND`) that bypasses safety controls.
- **Potential Impact:** Unpredictable, catastrophic financial side effects executed by an AI.
- **Likelihood Assessment:** **High.** LLMs inherently hallucinate and invent creative parameter names.
- **Severity Assessment:** **Catastrophic.** Total loss of system determinism and safety.
- **Preventive Control:** Strict Allow-List & Separation of Authority: The AI agent has zero direct tool execution authority. Its output is parsed strictly into a typed Pydantic intent enum; any non-allow-listed action is rejected immediately.
- **Detection / Recovery Mechanism:** Pydantic validation error triggers immediate fallback to safe deterministic baseline.
- **Verification Test Scenario:** Feed a mock LLM output containing an unauthorized tool name (`REFUND_ALL`); assert that parser rejects it and invokes fallback.
- **Required Before MVP?** **YES (Mandatory Blocking Invariant).**

---

### Hazard HAZ-011: Sensitive Information (PII/PCI) Appearing in Logs
- **Description:** Full credit card numbers (PAN), CVVs, or unmasked bank account numbers are written to application logs during error handling.
- **Potential Impact:** Major PCI-DSS violation, data breach risk, severe regulatory fines.
- **Likelihood Assessment:** **High.** Standard logging frameworks often serialize entire request objects on exceptions.
- **Severity Assessment:** **Critical.** PCI-DSS non-compliance leads to revocation of card processing privileges.
- **Preventive Control:** Log Masking & Payload Sanitization: Dedicated logging filters that strip PAN, CVV, and customer passwords before emitting structured JSON logs. Synthetic data used in MVP.
- **Detection / Recovery Mechanism:** Automated static analysis grep checks for credit card regex patterns in test log outputs.
- **Verification Test Scenario:** Ingest a payload with a mock card number; assert that log output contains only masked representation (`****-****-****-1234`).
- **Required Before MVP?** **YES (Mandatory Security Control).**

---

### Hazard HAZ-012: Unauthorized Access to Financial Data
- **Description:** An unauthenticated user or low-privilege account accesses the recovery dashboard and views customer debt information.
- **Potential Impact:** Customer privacy violation, data leak, regulatory penalty.
- **Likelihood Assessment:** **Medium.** Occurs when API endpoints lack authentication middleware.
- **Severity Assessment:** **Critical.** Breaches financial confidentiality.
- **Preventive Control:** Secure API boundaries with authentication middleware, CORS protection, and encrypted transport (HTTPS).
- **Detection / Recovery Mechanism:** Access control audit logs record all data retrieval requests.
- **Verification Test Scenario:** Attempt to access `/api/v1/cases` without credentials; assert HTTP 401/403.
- **Required Before MVP?** **Pragmatic MVP (Local single-tenant; full RBAC post-MVP).**

---

### Hazard HAZ-013: Database Failure During an In-Flight Action
- **Description:** The database server crashes immediately after a payment retry is dispatched to the gateway but before the outcome state is saved.
- **Potential Impact:** Orphaned transaction; system does not know the charge occurred and may retry again upon reboot.
- **Likelihood Assessment:** **Low.** Occurs during infrastructure restarts or network partitions.
- **Severity Assessment:** **Critical.** Causes state inconsistency and duplicate charging risk.
- **Preventive Control:** Transactional Outbox Pattern & Two-Phase State Commit: Case transitions to `ACTION_DISPATCHED` *before* the external call is made, persisting the idempotency key durably.
- **Detection / Recovery Mechanism:** On startup, a crash-recovery scanner inspects cases stuck in `ACTION_DISPATCHED` and polls the gateway simulator to reconcile status.
- **Verification Test Scenario:** Simulate database connection drop mid-workflow; assert that reconciliation worker recovers correct state on reboot.
- **Required Before MVP?** **YES (State transition ordering enforced in MVP).**

---

### Hazard HAZ-014: Concurrent Workers Processing the Same Case
- **Description:** Two background Celery/FastAPI workers pick up the same recovery case simultaneously from the queue.
- **Potential Impact:** Race condition resulting in two concurrent retry API calls to the gateway.
- **Likelihood Assessment:** **High.** Standard concurrency hazard in multi-worker environments.
- **Severity Assessment:** **Critical.** Causes duplicate payment attempts.
- **Preventive Control:** Row-Level Database Locking: Workers use `SELECT ... FOR UPDATE` (or optimistic concurrency version tokens `case.version`) when claiming a case.
- **Detection / Recovery Mechanism:** OptimisticLockException aborts the second worker.
- **Verification Test Scenario:** Spawn two parallel threads attempting to mutate the same case; assert that one succeeds and the other receives a conflict lock error.
- **Required Before MVP?** **YES (Mandatory Concurrency Control).**

---

### Hazard HAZ-015: False Claims About Recovered Revenue
- **Description:** An engineering demonstration reports $100,000 in "recovered revenue," but the number is based on synthetic predictions or unverified assumptions.
- **Potential Impact:** Misleading stakeholders, regulatory scrutiny for false advertising, loss of engineering integrity.
- **Likelihood Assessment:** **High.** Very common in AI project marketing.
- **Severity Assessment:** **Moderate-to-Critical.** Destroys technical and business credibility.
- **Preventive Control:** Mandatory Simulation Disclosure & Cryptographic Verification: All reports must explicitly label synthetic data as prototype regression benchmarks. Zero claims of production revenue without verified bank settlement logs.
- **Detection / Recovery Mechanism:** Audit report validator checks for provider receipt signatures.
- **Verification Test Scenario:** Audit all generated documentation and evaluation reports to ensure explicit synthetic disclaimers are present.
- **Required Before MVP?** **YES (Mandatory Reporting Standard).**

---

## 3. Non-Functional Quality Objectives

| Quality Dimension | Mandatory Invariant (Non-Negotiable) | Optimization Goal (Target) | Verification Method |
|---|---|---|---|
| **Reliability** | Zero unhandled exceptions causing lost financial state. | 99.9% availability for webhook ingestion. | Automated chaos testing / exception assertion suite. |
| **Data Integrity** | All financial amounts stored strictly as integer minor units. Zero floating-point rounding errors. | Append-only audit log retains 100% of state transitions. | Database column type assertions; schema migrations. |
| **Security** | Zero hardcoded secrets in repository; HMAC webhook signature validation enforced. | Principle of least privilege applied to database connections. | Automated secret scanning (`trufflehog` / `git-secrets`); unit tests. |
| **Privacy** | Zero real customer PII or cardholder data (PAN) processed in local project. | Masked logging for all account and customer identifiers. | Synthetic fixture inspection; log regex assertions. |
| **Maintainability** | Clean modular monolith with strict separation of Ingestion, Policy, Tools, and Brain. | Code maintainability index > 80; type hints across 100% of signatures. | MyPy strict mode; Ruff / Flake8 linting checks. |
| **Testability** | Deterministic tests run without external network or LLM dependencies. | Test suite execution time < 10 seconds for rapid feedback. | Pytest suite running in local CI with mock adapters. |
| **Reproducibility** | Batch evaluation runs produce identical results under fixed seeds (e.g., seed `42`). | Deterministic scenario generator versioned in repository. | Checksum verification of generated evaluation reports. |
| **Observability** | Structured JSON logging with `request_id`, `case_id`, and log level on every request. | OpenTelemetry trace propagation across internal service boundaries. | Log output schema inspection. |
| **Performance** | Webhook acknowledgment latency < 500ms; memory footprint < 512MB RAM locally. | Sub-100ms policy evaluation time per case. | Benchmark timing tests under 100 concurrent requests. |
| **Local Development** | System runs completely locally via standard Python virtual environment or Docker Compose. | Zero paid third-party API dependencies required to run the demo. | Clean setup walkthrough validation on fresh environment. |

---

## 4. Jurisdiction-Dependent Compliance Considerations (For Later Review)

The following regulatory requirements depend on operating jurisdiction and must be formally reviewed prior to production deployment:

1. **Card Network Retry Rules (Visa / Mastercard):**
   - Visa limits merchants to maximum 15 retry attempts within 30 calendar days across card-not-present transactions.
   - Category 1 declines (Hard: Stolen, Fraud) must NEVER be retried; doing so incurs fines.
2. **India UPI Autopay & RBI e-Mandates:**
   - Mandates require pre-debit notification sent to the customer at least 24 hours prior to debit.
   - Explicit mandate registration authorization limits debit amounts.
3. **European PSD2 / Strong Customer Authentication (SCA):**
   - Merchant-Initiated Transactions (MIT) must be linked to an initial Customer-Initiated Transaction (CIT) with two-factor authentication.
   - Off-session retries must include specific SCA exemption flags.
4. **US FDCPA & TCPA (Debt Collection & Communications):**
   - Prohibits automated calls/texts outside 08:00 AM to 09:00 PM local customer time.
   - Requires immediate cessation of communication upon written or digital opt-out.
