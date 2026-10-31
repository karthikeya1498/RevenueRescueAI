# RevenueRescueAI — Assumptions & Open Questions Register

> **Document ID:** DOC-OQ-009  
> **Phase:** 0.1 (Problem Analysis & Use-Case Selection)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

In software architecture, unrecorded assumptions are technical debt incurred before a single line of code is written. When team members hold conflicting implicit assumptions about system behavior—such as whether time advances via the real wall clock or a simulated virtual clock—entire subsystems must often be rewritten when the conflict surfaces.

This document establishes the formal Open Questions & Assumptions Register for RevenueRescueAI. It catalogs ten mandatory architectural questions, provides reasoned provisional recommendations, evaluates the blast radius if an assumption is incorrect, and identifies which decisions block subsequent phases versus which can be safely deferred.

---

## 2. Master Open Questions Register

---

### Question OQ-001: Scope of the First MVP (Failed Payments vs. All Flows)
- **Question:** Should the initial MVP focus exclusively on failed-payment and recurring subscription recovery, or should it include checkout abandonment, B2B invoices, and voice collection?
- **Why the answer matters:** Governs the entire data model, external integration surface, testing harness complexity, and frontend user journey.
- **Recommended Provisional Assumption:** The MVP will focus **exclusively on failed-payment and recurring subscription recovery**. All other use cases are deferred to post-MVP phases.
- **Consequences if the assumption is wrong:** If broader flows are mandated immediately, the project timeline expands by 3x–5x, testing becomes brittle, and the beginner developer faces severe cognitive overload.
- **Blocks Next Phase?** **YES (Blocking). Must be accepted to baseline Phase 0.2.**
- **Who should decide:** Lead Product Architect & Project Sponsor.
- **How decision will be recorded:** Architecture Decision Record (ADR) and Phase 0.1 acceptance sign-off.

---

### Question OQ-002: Adequacy of Simulated Payment Provider for Engineering Demonstration
- **Question:** Is a deterministic, local payment provider simulator sufficient for evaluating and demonstrating RevenueRescueAI, or is a live connection to an external gateway sandbox (e.g., live Stripe/Razorpay test mode) required?
- **Why the answer matters:** Live sandbox environments require external internet connectivity, secret key configuration, rate limits, and can introduce non-deterministic network failures during automated test runs.
- **Recommended Provisional Assumption:** A **deterministic local simulator is completely sufficient and preferred for the MVP demonstration**. It provides 100% reproducible scenarios, faster unit tests, zero secret key exposure, and controllable edge cases (e.g., simulating a 504 timeout on demand).
- **Consequences if the assumption is wrong:** If a live external sandbox is required, automated CI tests will fail without internet or active credentials, slowing development cycles.
- **Blocks Next Phase?** **YES (Blocking). Governs adapter implementation.**
- **Who should decide:** Lead Architect & QA Engineer.
- **How decision will be recorded:** Documented in [docs/mvp-scope.md](mvp-scope.md) and tool adapter interface contracts.

---

### Question OQ-003: Multi-Currency Support vs. Single Base Currency
- **Question:** What currencies must be supported initially, and how should currency conversions be handled?
- **Why the answer matters:** Multi-currency systems require real-time FX rate tables, cross-currency reconciliation, and localized minor-unit rounding rules.
- **Recommended Provisional Assumption:** Support **USD (United States Dollar, minor units: Cents) and INR (Indian Rupee, minor units: Paise)** as discrete currencies. Cross-currency conversion is explicitly excluded; all calculations and batch evaluations occur within the case's native currency.
- **Consequences if the assumption is wrong:** Attempting dynamic FX conversions in MVP introduces external financial oracle dependencies and rounding inaccuracies.
- **Blocks Next Phase?** **Non-blocking (Data model uses ISO-4217 string and integer minor units, accommodating any single currency naturally).**
- **Who should decide:** Business Analyst & Data Engineer.
- **How decision will be recorded:** Schema definition in Data Model specifications.

---

### Question OQ-004: Execution Timing: Real Wall-Clock vs. Deterministic Simulated Clock
- **Question:** How should scheduled retries (e.g., "retry in 48 hours") be tested and demonstrated? Should the system use real wall-clock elapsed time (requiring days to test) or a deterministic simulated virtual clock?
- **Why the answer matters:** Automated tests cannot wait 48 real hours to assert that a retry succeeded. Fast, reproducible batch simulation requires instantaneous time-travel.
- **Recommended Provisional Assumption:** Implement a **Virtual Clock / Time-Provider Interface**. In production mode, it reads `datetime.now(timezone.utc)`; in evaluation/simulation mode, the clock is programmatically stepped forward, enabling a 500-scenario, multi-day simulation to complete in seconds.
- **Consequences if the assumption is wrong:** Hardcoding real `time.sleep()` or waiting for system cron jobs makes automated regression testing impossible in CI pipelines.
- **Blocks Next Phase?** **YES (Blocking for resilience and evaluation design).**
- **Who should decide:** Software Architect & QA Lead.
- **How decision will be recorded:** Architecture Decision Record on Time-Provider Abstraction.

---

### Question OQ-005: Definition of Confirmed Payment Success
- **Question:** At what exact point is a payment officially declared "recovered"? Upon dispatch of the retry? Upon receipt of a gateway 200 OK? Or upon settlement reconciliation?
- **Why the answer matters:** Distinguishes real financial recovery from phantom predictions. Declaring recovery prematurely corrupts financial metrics.
- **Recommended Provisional Assumption:** A payment is confirmed recovered **only when the payment provider simulator returns an authoritative receipt with `status: "succeeded"` and an authoritative settlement transaction ID**, verified against the case parameters.
- **Consequences if the assumption is wrong:** The system claims credit for payments that may have failed at the bank or were rejected during clearing.
- **Blocks Next Phase?** **YES (Blocking for metric and verification logic).**
- **Who should decide:** Financial Controller / Auditor Persona.
- **How decision will be recorded:** Formal definition in [docs/metrics-specification.md](metrics-specification.md).

---

### Question OQ-006: Attribution Window & Attribution Rules
- **Question:** If a payment succeeds after a recovery action, how do we guarantee the recovery action caused the success rather than the customer paying organically?
- **Why the answer matters:** Over-attribution falsely inflates recovery metrics; under-attribution obscures system value.
- **Recommended Provisional Assumption:** A successful payment is attributed to the recovery action **if and only if**: (1) it uses the action's unique idempotency token, (2) the amount matches exactly in minor units, and (3) it settles within an **Attribution Window of 72 hours** from action dispatch.
- **Consequences if the assumption is wrong:** Long attribution windows (e.g., 30 days) falsely claim organic payments; short windows (e.g., 1 hour) miss legitimate asynchronous ACH/bank settlements.
- **Blocks Next Phase?** **Non-blocking (Window parameter can be configured in settings).**
- **Who should decide:** RevOps Analyst & Data Scientist.
- **How decision will be recorded:** Attribution configuration constants in application settings.

---

### Question OQ-007: Allow-Listed Recovery Action Taxonomy
- **Question:** What constitutes a valid, permitted recovery action in the MVP?
- **Why the answer matters:** The AI agent and policy gate must share a strictly bounded enum of permissible actions to prevent invalid tool execution.
- **Recommended Provisional Assumption:** The MVP action taxonomy is strictly restricted to five operations:
  1. `RETRY_PAYMENT` (Execute immediate or scheduled card charge via simulator).
  2. `SCHEDULE_RETRY` (Queue a retry for a future virtual timestamp).
  3. `SEND_PAYMENT_UPDATE_LINK` (Simulate issuing a self-service update notification).
  4. `ESCALATE_TO_HUMAN` (Route case to manual review queue).
  5. `HALT_RECOVERY` (Terminate recovery permanently without further action).
- **Consequences if the assumption is wrong:** Unbounded action spaces allow the AI to invent unauthorized actions (e.g., `OFFER_90_PERCENT_DISCOUNT`).
- **Blocks Next Phase?** **YES (Blocking for Agent & Policy interface design).**
- **Who should decide:** Lead Architect & Product Engineer.
- **How decision will be recorded:** Pydantic Action Enum in domain contract definitions.

---

### Question OQ-008: Mandatory Conditions for Human Escalation
- **Question:** What explicit thresholds mandate routing a case to a human operator rather than resolving it automatically?
- **Why the answer matters:** Balances operational automation efficiency against financial risk exposure.
- **Recommended Provisional Assumption:** Mandatory escalation occurs when:
  1. Nominal amount >= $1,000.00 (100,000 minor units).
  2. Gateway outcome remains `UNCERTAIN` after 3 reconciliation attempts.
  3. AI model diagnostic confidence score is < 0.60.
  4. Payment failure code indicates active dispute or chargeback alert.
- **Consequences if the assumption is wrong:** Setting thresholds too low floods human operators with low-value tickets; setting thresholds too high allows risky transactions to execute autonomously.
- **Blocks Next Phase?** **Non-blocking (Thresholds can be tuned in configuration).**
- **Who should decide:** RevOps Manager & Finance Director.
- **How decision will be recorded:** Policy configuration parameters in application settings.

---

### Question OQ-009: Dashboard Data Sourcing: Synthetic Seed vs. Live Backend State
- **Question:** Should the frontend dashboard render static mock JSON files or query the live FastAPI backend via REST APIs?
- **Why the answer matters:** A dashboard disconnected from the backend is merely a visual prototype; a connected dashboard demonstrates true end-to-end software engineering.
- **Recommended Provisional Assumption:** The dashboard must **query the live FastAPI backend via REST API endpoints (`GET /api/v1/cases`, `GET /api/v1/metrics/overview`)**. The backend seeds its database with deterministic synthetic scenarios so the UI reflects live, filterable, and inspectable backend state.
- **Consequences if the assumption is wrong:** Disconnected mock UIs create integration debt and hide backend defects.
- **Blocks Next Phase?** **Non-blocking for Phase 0.2; blocking for Phase 0.9 (Frontend).**
- **Who should decide:** Full-Stack Architect.
- **How decision will be recorded:** API Design contract and frontend integration specification.

---

### Question OQ-010: Trustworthiness & Retention of Existing Repository Components
- **Question:** The existing repository contains legacy AI-generated artifacts, migration files, and documentation claiming completion of Phases 1 through 10. Which components are trustworthy, and how should they be treated?
- **Why the answer matters:** A beginner developer must know whether to treat existing code as working truth or as an unverified prototype.
- **Recommended Provisional Assumption:** **Treat the existing repository as an unverified prototype and reference implementation.** 
  - *Retain:* Database models, Pydantic schemas, and simulator skeletons if they satisfy Phase 0.1 invariants.
  - *Discard/Rewrite:* Any unverified claims of production readiness, inflated recovery metrics, or unstructured agent scripts that bypass policy gates.
  - *Do not delete or rename existing files in Phase 0.1; record discrepancies clearly in documentation.*
- **Consequences if the assumption is wrong:** Assuming existing code works without verification will cause hidden bugs and architectural inconsistencies to propagate into new phases.
- **Blocks Next Phase?** **YES (Blocking for Phase 1 planning).**
- **Who should decide:** Technical Mentor & Lead Architect.
- **How decision will be recorded:** Documented in [docs/problem-analysis.md](problem-analysis.md) and Phase 0.1 acceptance report.

---

## 3. Summary of Blocking vs. Non-Blocking Decisions

| Question ID | Question Topic | Status | Impact on Phase 0.2 |
|---|---|---|---|
| **OQ-001** | Scope of MVP (Failed payments only) | **BLOCKING** | Must be agreed before drafting detailed acceptance criteria. |
| **OQ-002** | Simulated Provider Adequacy | **BLOCKING** | Must be agreed before designing tool adapter interfaces. |
| **OQ-003** | Currency Handling (USD/INR minor units) | Non-blocking | Default integer minor units accommodates single currency. |
| **OQ-004** | Virtual Clock vs. Wall Clock | **BLOCKING** | Affects state machine and evaluation design. |
| **OQ-005** | Definition of Confirmed Success | **BLOCKING** | Required for metric and outcome verifier design. |
| **OQ-006** | Attribution Window (72 hours) | Non-blocking | Configurable parameter. |
| **OQ-007** | Allow-Listed Action Taxonomy | **BLOCKING** | Required for agent prompt and policy gate schemas. |
| **OQ-008** | Human Escalation Thresholds | Non-blocking | Configurable business rules. |
| **OQ-009** | Dashboard Live API Connection | Non-blocking | Affects later frontend phase. |
| **OQ-010** | Existing Repository Trust Boundary | **BLOCKING** | Establishes baseline code review strategy. |
