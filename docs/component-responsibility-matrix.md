# RevenueRescueAI — Component Responsibility Matrix & Boundary Isolation
## Phase 1.4: Formal Separation of Responsibilities, Invariants, and Failure Behaviors

**Document Version:** 1.0.0  
**Status:** Approved Component Matrix  
**Primary Authors:** Senior Software Architect, Security Engineer, Systems Designer  

---

## 1. Executive Summary & The Separation of Powers Doctrine

In automated financial systems, blending recommendation, policy validation, execution, and verification into a single component leads to unchecked execution, security breaches, and fraudulent metric reporting.

RevenueRescueAI strictly enforces the **Separation of Powers Doctrine**:

```
+---------------------------------------------------------------------------------------------------+
|                                SEPARATION OF POWERS ARCHITECTURE                                  |
|                                                                                                   |
|  [ 1. AI ADVISOR ]      [ 2. POLICY GATE ]     [ 3. WORKFLOW FSM ]    [ 4. VERIFICATION ENGINE ]  |
|  Proposes candidate    Holds ABSOLUTE VETO    Orchestrates bounded   Proves legitimate           |
|  action intent based   power; checks safety   atomic transitions &   recovery attribution        |
|  on decline context.   invariants (INV-001).  enforces retry budget. against hard bank proof.     |
|                                                                                                   |
|  Zero execution        Zero execution         Zero payment calls;    Zero execution               |
|  permissions.          permissions.           delegates to tool reg. permissions.                 |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Detailed Component Responsibility Matrix

### 2.1 AI Recommendation Engine (Agent Brain)
- **Main Responsibility:** Diagnoses payment failure codes and generates candidate action proposals with confidence scores and explainable rationale.
- **Inputs:** Anonymized transaction amount, currency, decline code, prior attempt count, customer tenure.
- **Outputs:** Validated `AgentDecisionContract` (action: `RETRY_NOW`, `SCHEDULE_RETRY`, `REQUEST_PAYMENT_METHOD_UPDATE`, `ESCALATE_TO_HUMAN`, `STOP_RECOVERY`; confidence; reason_code; rationale).
- **Dependencies:** `app.agents.contracts`, Deterministic Baseline Model, Optional LLM Client.
- **Data Owned/Managed:** `agent_decisions` table (creates unvalidated decision rows).
- **Actions Allowed:** Propose actions from the 5 permitted enum values; calculate confidence scores; summarize decline narratives.
- **Actions Strictly Forbidden:**
  - **MUST NEVER** authorize or execute a payment attempt.
  - **MUST NEVER** call payment provider APIs directly.
  - **MUST NEVER** bypass policy invariant checks.
  - **MUST NEVER** declare a payment as recovered.
- **Failure Scenarios:** Model timeout (>3.0s), API rate limit (429), or malformed JSON output $\to$ System seamlessly falls back to `deterministic-logistic-v1` or routes to `ESCALATE_TO_HUMAN`.

---

### 2.2 Deterministic Policy Gate (Safety Guardian)
- **Main Responsibility:** Evaluates proposed agent decisions against strict safety invariants and holds absolute veto authority over financial actions.
- **Inputs:** Candidate `AgentDecision`, case context, customer restriction status, attempt history.
- **Outputs:** Policy verdict (`ALLOWED`, `VETOED_OVERRIDE`, `FORCED_ESCALATE`).
- **Dependencies:** `app.policy.safety`, Invariants (INV-001 through INV-016).
- **Data Owned/Managed:** Updates `agent_decisions.validation_status`.
- **Actions Allowed:** Validate proposed actions; veto unsafe recommendations; force case transitions to `ESCALATED` when retry limits are reached; override actions with safe defaults.
- **Actions Strictly Forbidden:**
  - **MUST NEVER** execute external network calls or banking charges.
  - **MUST NEVER** permit an action outside the allow-list.
  - **MUST NEVER** loosen a safety invariant based on an AI prompt or operator override.
- **Failure Scenarios:** Internal logic exception or unhandled state $\to$ Fails safe to `FORCED_ESCALATE` (blocks execution immediately).

---

### 2.3 Recovery Workflow Engine (State Machine Orchestrator)
- **Main Responsibility:** Coordinates the finite state machine lifecycle of a recovery case across explicit states in atomic ACID transactions.
- **Inputs:** Case trigger transactions, policy authorization verdicts, tool execution outcomes.
- **Outputs:** Case state transitions, optimistic version updates, attempt scheduling.
- **Dependencies:** Relational Database, `TransitionService`, `AuditService`.
- **Data Owned/Managed:** `recovery_cases`, `case_state_transitions`.
- **Actions Allowed:** Move cases through valid FSM states; allocate sequential transition numbers; enforce optimistic locking; lock terminal states (`RECOVERED`, `FAILED`, `TERMINATED`).
- **Actions Strictly Forbidden:**
  - **MUST NEVER** reopen a case in a terminal state (Invariant INV-004).
  - **MUST NEVER** execute illegal backward transitions (e.g., `RECOVERED` $\to$ `DETECTED`).
  - **MUST NEVER** charge a payment card directly (delegates to Tool Registry).
- **Failure Scenarios:** Concurrent update conflict $\to$ Aborts with `OptimisticLockError`; invalid transition $\to$ Rolls back transaction and raises `InvalidStateTransitionError`.

---

### 2.4 Payment Provider Simulator (Emulated Banking Rails)
- **Main Responsibility:** Emulates external card network gateway operations with deterministic outcomes, fault injection, and idempotency caching.
- **Inputs:** Charge requests (`amount_minor`, `currency`, `idempotency_key`).
- **Outputs:** Simulated gateway responses (`status: succeeded | failed | uncertain`, `charge_id`, `error_code`).
- **Dependencies:** Pseudo-random seeded generator (`random.Random(42)`).
- **Data Owned/Managed:** In-memory / database simulator charge ledger.
- **Actions Allowed:** Simulate successful charges, soft declines, hard declines, rate limits (429), and gateway timeouts (504).
- **Actions Strictly Forbidden:**
  - **MUST NEVER** connect to live banking networks or live payment credentials.
  - **MUST NEVER** accept real customer credit card numbers (PANs) or CVVs.
  - **MUST NEVER** alter internal case states directly.
- **Failure Scenarios:** Simulated timeout (HTTP 504) $\to$ Engine captures uncertain outcome and moves case to `VERIFICATION_PENDING`.

---

### 2.5 Outcome Verification Service (Attribution Auditor)
- **Main Responsibility:** Proves that an alleged payment success legitimately recovers a specific failed transaction within a 72-hour window before revenue credit is granted.
- **Inputs:** Provider success event, failed transaction ID, case context.
- **Outputs:** Attribution verdict (`VERIFIED_ATTRIBUTED`, `REJECTED_UNMATCHED`).
- **Dependencies:** Relational Database, `transactions` table.
- **Data Owned/Managed:** `recovery_evidence` table.
- **Actions Allowed:** Verify exact minor unit matches, customer matches, and 72-hour window constraints; create immutable evidence records.
- **Actions Strictly Forbidden:**
  - **MUST NEVER** attribute revenue without matching transaction evidence.
  - **MUST NEVER** count an uncertain or pending payment as recovered revenue.
  - **MUST NEVER** permit duplicate attribution of the same provider event (Invariant INV-007).
- **Failure Scenarios:** Mismatched amount or expired window $\to$ Denies attribution; flags case for human investigation.

---

### 2.6 Audit Service (Compliance Ledger)
- **Main Responsibility:** Records an immutable, append-only chronological history of every decision, state change, and financial attempt.
- **Inputs:** Audit payloads from all domain components.
- **Outputs:** Sequenced audit records.
- **Dependencies:** Relational Database (`audit_events` table).
- **Data Owned/Managed:** `audit_events` table.
- **Actions Allowed:** Insert audit events with strictly monotonic sequence numbers (`1, 2, 3...`) and correlation IDs; mask sensitive data.
- **Actions Strictly Forbidden:**
  - **MUST NEVER** update or delete an existing audit record.
  - **MUST NEVER** record unmasked credit card numbers (PANs) or provider credentials.
- **Failure Scenarios:** Database write failure $\to$ The entire surrounding business transaction is aborted and rolled back.

---

### 2.7 Dashboard Metrics Service (Financial Authority)
- **Main Responsibility:** Computes authoritative financial KPIs (Recovered Revenue, At-Risk Revenue, Recovery Rate, Safety Rate) directly from database tables.
- **Inputs:** Time range, currency code.
- **Outputs:** Authoritative metrics payload in integer minor units.
- **Dependencies:** Relational Database (`recovery_evidence`, `recovery_cases`).
- **Data Owned/Managed:** Read-only calculation engine.
- **Actions Allowed:** Aggregate confirmed evidence; compute rates with zero-division safety; partition synthetic evaluation metrics from production revenue.
- **Actions Strictly Forbidden:**
  - **MUST NEVER** use floating-point math as the source of financial truth.
  - **MUST NEVER** count pending, uncertain, or unverified payments as recovered revenue.
- **Failure Scenarios:** Database read error $\to$ Returns structured HTTP 500 without corrupting cached metrics.
