# RevenueRescueAI — Stakeholder Analysis & User Stories

> **Document ID:** DOC-STK-003  
> **Phase:** 0.1 (Problem Analysis & Use-Case Selection)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

A financial recovery system interacts with diverse human users and autonomous background services. A common defect in AI applications is treating every user as an "admin" or failing to distinguish between human decision-makers and automated background workers.

This document establishes the stakeholder matrix, operational boundaries, permission constraints, and core user stories for RevenueRescueAI. It cleanly separates human operators from automated system actors and establishes a pragmatic access-control model for the MVP while documenting future enterprise requirements.

---

## 2. Stakeholder Profiles & Permissions Matrix

The system recognizes seven distinct stakeholders (five human roles and two technical actors).

---

### 1. Business Owner / Finance Manager (Human)
- **Primary goal:** Maximize recovered business cash flow, protect operating margins, and maintain an accurate, predictable forecast of involuntary churn.
- **Information needed:** High-level financial KPIs: Total revenue at risk, confirmed recovered revenue, net recovery rate (after payment fees), recovery ROI vs. baseline, and macro churn impact.
- **Actions permitted:** Viewing financial dashboards; setting macro recovery policies (e.g., maximum allowable retry fee budget); approving global escalation policies; exporting executive summaries.
- **Actions not permitted:** Editing raw transaction logs; modifying code-level policy rules directly; manually executing raw gateway charges without policy validation.
- **Main risks or concerns:** Inaccurate financial reporting; hidden payment processing fees eroding margins; brand damage caused by aggressive customer dunning.
- **Relevant screens/reports:** Executive Command Center, Revenue Recovery Trends, Macro Financial Report, Baseline Comparison Lab.
- **How success is measured:** Total confirmed dollars recovered; reduction in gross churn rate; positive net return on recovery operations.

---

### 2. Revenue Operations Analyst (RevOps) (Human)
- **Primary goal:** Monitor active recovery pipelines, fine-tune recovery rules and scheduling models, inspect high-value cases, and resolve escalated recovery anomalies.
- **Information needed:** Granular case telemetry: Failure codes, bank decline reasons, customer risk scores, retry counts, AI diagnostic rationale, policy approval records.
- **Actions permitted:** Reviewing the recovery queue; manually approving or rejecting escalated medium/high-risk cases; triggering batch evaluation simulations; adjusting test simulation parameters.
- **Actions not permitted:** Bypassing security checks; deleting audit trails; altering payment gateway keys.
- **Main risks or concerns:** High false-positive escalation rates creating operational fatigue; suboptimal retry timing wasting retry budgets.
- **Relevant screens/reports:** Recovery Case Queue, Case Detail Drawer / Diagnostic Trace, Evaluation Lab, Policy Configuration Viewer.
- **How success is measured:** Case recovery rate (%); mean time to resolution (MTTR) on escalated cases; low operator touch time per recovered dollar.

---

### 3. Customer Support Agent (Human)
- **Primary goal:** Quickly understand why a customer's account or payment failed when they reach out for assistance, explain what happened transparently, and help them restore service.
- **Information needed:** Customer-centric payment history: Why the card failed (in non-technical language), whether an automated retry is currently scheduled, and whether a payment update link was sent.
- **Actions permitted:** Searching cases by Customer ID or Email; pausing active automated retries upon customer request; generating a secure payment update link; logging customer promises to pay.
- **Actions not permitted:** Manually triggering immediate card charges without customer presence; viewing full unmasked credit card numbers (PAN); modifying system-wide policies.
- **Main risks or concerns:** Inability to explain mysterious charges to angry customers; accidentally sending conflicting communications while the customer is on the phone.
- **Relevant screens/reports:** Customer Lookup Screen, Case Timeline View, Communication History.
- **How success is measured:** Customer satisfaction score (CSAT); fast inquiry resolution; zero erroneous double-charges reported by customers.

---

### 4. Customer / Payer (Human)
- **Primary goal:** Maintain uninterrupted access to their subscribed service or complete their purchase with minimal friction, maximum security, and zero unexpected charges.
- **Information needed:** Clear, honest notification of payment failure; exact amount due; explanation of how to update payment details safely; self-service payment receipt.
- **Actions permitted:** Clicking secure payment links; updating expired card or bank details via hosted gateway portal; requesting communication pauses or opting out.
- **Actions not permitted:** Accessing internal recovery queues; viewing system diagnostics or internal risk scores.
- **Main risks or concerns:** Being surprised by unexpected bank overdraft fees from rogue retries; receiving spammy or threatening dunning emails; payment credential theft.
- **Relevant screens/reports:** Hosted Payment Update Portal (Gateway-hosted), Payment Receipt Email.
- **How success is measured:** Zero unauthorized card attempts; seamless restoration of subscription access upon payment.

---

### 5. System Administrator / Platform Engineer (Human)
- **Primary goal:** Ensure system availability, data integrity, secure secret management, healthy gateway connectivity, and reliable background job execution.
- **Information needed:** System health metrics: Queue lag, API response latency, database connection pool status, provider webhook error rates, container memory/CPU utilization.
- **Actions permitted:** Managing deployment configuration; rotating API keys and webhook secrets; triggering database schema migrations; inspecting structured JSON system logs.
- **Actions not permitted:** Altering financial recovery states directly in the database without an audit event; overriding compliance gates.
- **Main risks or concerns:** Infrastructure outages during critical billing runs; database deadlocks on concurrent transactions; secret leaks in logs.
- **Relevant screens/reports:** System Health (`/health`, `/ready`), Structured Log Stream, Queue Monitor.
- **How success is measured:** 99.9% uptime; zero secret leaks; sub-second webhook processing latency.

---

### 6. Recovery Workflow Engine (Automated System Actor)
- **Primary goal:** Autonomously process ingested revenue-at-risk events through the lifecycle: orchestrate risk scoring, validate policy, dispatch controlled tools, and record immutable audit records.
- **Information needed:** Raw event payloads, customer account metadata, retry policy parameters, gateway simulation responses.
- **Actions permitted:** Ingesting webhooks; executing AI recommendation requests; querying policy rules; calling allow-listed gateway simulator methods with idempotency keys; writing audit records.
- **Actions not permitted:** Executing any action that fails deterministic policy validation; inventing unauthorized actions; bypassing idempotency keys.
- **Main risks or concerns:** Infinite execution loops; deadlocks; race conditions processing concurrent webhooks for the same invoice.
- **Relevant screens/reports:** Emits data to all operational dashboards; verified via automated test harnesses.
- **How success is measured:** 100% adherence to safety policy; zero duplicate charges; 100% audit log completeness.

---

### 7. Auditor / Compliance Reviewer (Human or External Actor)
- **Primary goal:** Independently verify that financial recovery operations comply with card network rules (Visa/Mastercard), consumer financial protection laws, privacy mandates, and accounting standards.
- **Information needed:** Append-only immutable audit trail; cryptographic evidence of webhook receipts; reconciliation reports linking recovery actions to bank settlement deposits.
- **Actions permitted:** Read-only access to historical audit logs, policy change histories, and evaluation scenario results; generating compliance export reports.
- **Actions not permitted:** Modifying any data; triggering recovery actions; changing system configurations.
- **Main risks or concerns:** Altered or missing audit records; unverified revenue claims; illegal retry frequencies violating payment network rules.
- **Relevant screens/reports:** Audit Trail Explorer, Policy Version History, Evaluation Verification Reports.
- **How success is measured:** 100% auditable traceability from initial failure to verified settlement; zero non-compliant recovery actions.

---

## 3. Human vs. Automated Actor Distinction

| Characteristic | Human Stakeholders | Automated Workflow Engine |
|---|---|---|
| **Identity Verification** | Username/Password, SSO, MFA session tokens | Service account, cryptographic webhook signatures, mTLS |
| **Execution Authority** | Strategic oversight, policy definition, exception approvals | Operational execution strictly within pre-approved policy envelopes |
| **Operational Speed** | Minutes to hours (deliberative) | Milliseconds to seconds (real-time automated) |
| **Failure Response** | Manual case escalation, investigation, operational decisions | Fail-safe stop: Halt workflow, log error, escalate to human queue |
| **Audit Requirement** | User ID recorded on manual actions and approvals | Worker ID, step ID, and correlation ID stamped on every transition |

---

## 4. MVP Access-Control Design & Future Roadmap

### 4.1 Pragmatic MVP Boundary
For the initial local engineering demonstration and Phase 0.1/1.0 baseline:
- The system runs in a single-tenant local environment.
- Access control is role-conceptualized rather than locked behind complex OAuth/SSO servers.
- The UI exposes role-based perspective toggles (e.g., viewing as "Finance Manager" vs. "RevOps Analyst").
- System mutations (like manual approvals) record a simulated operator identity (`operator_id: "analyst_sarah"`).
- All external webhook inputs require HMAC signature validation.

### 4.2 Future Enterprise Authorization Roadmap (Post-MVP)
Prior to production deployment with real financial data:
1. **Authentication:** Implement OpenID Connect (OIDC) / SAML 2.0 integration with enterprise identity providers (Okta, Azure AD).
2. **Role-Based Access Control (RBAC):** Enforce strict role decorators on backend endpoints:
   - `ROLE_VIEWER`: Read-only access to dashboards.
   - `ROLE_ANALYST`: Queue inspection and case escalation approval.
   - `ROLE_ADMIN`: Policy configuration and system settings.
   - `ROLE_AUDITOR`: Read-only export access to immutable audit tables.
3. **Session Management:** Enforce short-lived JWT access tokens with secure HTTP-only cookies and automatic session revocation.

---

## 5. Core User Stories & Business Outcomes

The initial implementation focuses on four foundational user stories that deliver the core value proposition.

---

### Story US-01: Deterministic Risk Detection & Ingestion
- **As a** Revenue Operations Analyst,
- **I want** the system to automatically ingest and validate failed payment webhooks,
- **So that** every instance of revenue at risk is captured immediately with zero manual data entry.

**Business Outcome:** Eliminates unmonitored payment drops; ensures 100% of failed transactions enter a tracked recovery pipeline.

**Acceptance Criteria (Gherkin format):**
```gherkin
Scenario: Ingest valid payment failure webhook
  Given a simulated payment gateway emits a "payment.failed" webhook
  And the webhook contains a valid HMAC signature and required fields (amount, currency, customer_id, payment_id)
  When the Ingestion Service processes the webhook
  Then a new Recovery Case is created with state "DETECTED"
  And the exact amount at risk is recorded in integer minor units
  And an immutable Audit Event "CASE_DETECTED" is appended to the ledger
  And the system returns HTTP 200 OK with a unique case ID

Scenario: Reject duplicate failure webhook
  Given a Recovery Case already exists for payment ID "pay_98234"
  When an identical "payment.failed" webhook is received with payment ID "pay_98234"
  Then the system detects the duplicate via idempotency key
  And the webhook is acknowledged without creating a secondary case or duplicate charge
```

---

### Story US-02: Policy-Governed Strategy Selection
- **As a** Finance Manager,
- **I want** the AI's recovery recommendation to be strictly validated by deterministic policy rules,
- **So that** automated actions never violate business constraints, retry limits, or customer agreements.

**Business Outcome:** Eliminates rogue AI actions, guarantees regulatory compliance, and protects customer goodwill.

**Acceptance Criteria:**
```gherkin
Scenario: AI recommendation passes policy gate
  Given a recovery case with failure code "insufficient_funds"
  And the case has had 0 prior retries
  When the AI Brain recommends action "RETRY_PAYMENT" scheduled in 48 hours
  Then the Deterministic Policy Gate evaluates retry count, backoff interval, and active customer status
  And the policy evaluation evaluates to "APPROVED"
  And the case state transitions to "POLICY_APPROVED"
  And the scheduled execution timestamp is persisted

Scenario: AI recommendation violates retry budget
  Given a recovery case that has already undergone 3 failed retries
  When the AI Brain recommends action "RETRY_PAYMENT"
  Then the Deterministic Policy Gate identifies that max retries (3) has been reached
  And the policy evaluation evaluates to "REJECTED_MAX_RETRIES_EXCEEDED"
  And the case state transitions to "HALTED_UNRECOVERED"
  And no payment action is dispatched to the gateway
```

---

### Story US-03: Controlled Execution & Authoritative Verification
- **As an** Auditor,
- **I want** recovery to be declared only after receiving authoritative settlement proof from the payment provider,
- **So that** financial reports never claim unconfirmed or phantom revenue.

**Business Outcome:** Provides 100% trustworthy financial reporting that withstands rigorous financial audit.

**Acceptance Criteria:**
```gherkin
Scenario: Successful recovery verified by provider receipt
  Given a case in state "ACTION_DISPATCHED" with idempotency key "idemp_case_551_att1"
  When the payment provider simulator executes the retry
  And the provider returns status "succeeded" with a matching transaction ID, amount, and currency
  Then the Outcome Verifier validates the receipt against case parameters
  And the case state transitions to "RECOVERED"
  And the Confirmed Recovered Revenue metric increases by the exact captured amount
  And an Audit Event "VERIFIED_RECOVERY" is permanently recorded

Scenario: Gateway timeout handled as uncertain outcome
  Given a case in state "ACTION_DISPATCHED"
  When the provider network call times out without an HTTP status
  Then the Outcome Verifier flags the result as "UNCERTAIN"
  And the case state transitions to "VERIFICATION_PENDING"
  And immediate re-execution is strictly blocked to prevent double-charging
  And an asynchronous reconciliation check is scheduled
```

---

### Story US-04: Operator Visibility & Traceability
- **As a** Revenue Operations Analyst,
- **I want** to inspect a clear command center dashboard with an end-to-end diagnostic trace for every case,
- **So that** I can explain exactly why an action was taken, what rule approved it, and how much was recovered.

**Business Outcome:** Empowers human operators with instant explainability and eliminates the "black box" problem of AI automation.

**Acceptance Criteria:**
```gherkin
Scenario: Inspect case diagnostic trace in dashboard
  Given a user views the Recovery Case Queue in the frontend
  When the user clicks on Case ID "CASE-1049"
  Then a detail drawer opens displaying:
    | Section | Information Displayed |
    | Header | Case ID, Amount in currency, Customer ID, Current State |
    | Telemetry | Raw Gateway Error Code, Ingestion Timestamp |
    | AI Reasoning | Diagnosed Failure Class, Confidence Score, Selected Action |
    | Policy Gate | Individual Policy Rules Evaluated (Pass/Fail) |
    | Provider Proof | Gateway Transaction ID, Captured Amount, Settlement Timestamp |
  And the full sequential timeline of audit events is visually rendered
```
