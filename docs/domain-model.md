# RevenueRescueAI — Domain Model Specification
## Phase 1.2: Domain-Driven Design, Bounded Contexts, and Aggregate Roots

**Document Version:** 1.0.0  
**Status:** Approved Domain Architecture  
**Primary Authors:** Principal Database Architect, Domain-Driven Design Specialist, Senior Financial Systems Engineer  
**Target Audience:** Engineering Team, System Architects, Technical Interviewers, Novice Developers  

---

## 1. Executive Summary & Domain Definition

In Domain-Driven Design (DDD), software architecture begins by deeply understanding the core business problem before writing database schemas or code.

### 1.1 The Core Business Domain: Autonomous Revenue Recovery
The core domain of RevenueRescueAI is **Autonomous, Bounded, and Verified Revenue Recovery**:
> *"Detecting revenue at risk from payment failures, diagnosing the root cause, selecting the optimal recovery intervention, strictly enforcing financial safety policies, and verifying the outcome against hard banking evidence."*

#### Why Revenue Recovery is the Core Domain (and not generic payments):
- Generic payment gateways (like Stripe or Adyen) specialize in *processing* transactions. They do not know a merchant's business recovery policies, customer lifetime value, or regulatory retry limits.
- Generic CRM or subscription platforms specialize in *billing cycles*. They do not diagnose card network decline codes or perform automated exponential backoff retries.
- **RevenueRescueAI is the intelligent recovery bridge:** It turns payment failures into structured recovery cases, preventing involuntary customer churn and saving merchants millions in lost subscription revenue while strictly protecting cardholders from predatory or duplicate retries.

### 1.2 Domain Classification Matrix
To keep the system focused and avoid building unnecessary features, we partition the system into three domain classifications:

| Domain Category | Capabilities Included | Why It Matters |
| :--- | :--- | :--- |
| **Core Domain** (Unique Business Value) | • Risk Assessment & Detection<br>• Root-Cause Decline Diagnosis<br>• AI Recommendation Engine<br>• Deterministic Policy Gate (Safety Invariants)<br>• Verified Outcome Attribution | This is the proprietary business logic that wins back revenue safely and differentiates the product. |
| **Supporting Subdomains** (Necessary Capabilities) | • Recovery Workflow State Machine<br>• Bounded Tool Execution Registry<br>• 500-Scenario Batch Evaluation Engine<br>• Retry Backoff Scheduler | Complements the core domain to make recovery repeatable, observable, and measurable. |
| **Generic Subdomains** (Standard Technical Needs) | • Authentication & RBAC<br>• Structured JSON Logging & Observability<br>• Relational Persistence (SQLAlchemy/Postgres)<br>• Webhook Signature Verification | Solved using off-the-shelf industry patterns rather than inventing custom tools. |

---

## 2. Bounded Contexts

A **Bounded Context** is an explicit boundary within which a specific domain model applies. Inside the boundary, all terms in the domain language (Ubiquitous Language) have an unambiguous, singular meaning.

RevenueRescueAI defines **7 Bounded Contexts**:

```
+---------------------------------------------------------------------------------------------------+
|                                      REVENUERESCUEAI SYSTEM                                       |
|                                                                                                   |
|  +-----------------------+     +-----------------------+     +---------------------------------+  |
|  | 1. Payment Management | --> | 2. Revenue Risk Engine| --> | 3. Recovery Case Management     |  |
|  | Context               |     | Context               |     | Context (CENTRAL AGGREGATE)     |  |
|  +-----------------------+     +-----------------------+     +---------------------------------+  |
|                                                                              |                    |
|                                                                              v                    |
|  +-----------------------+     +-----------------------+     +---------------------------------+  |
|  | 5. Outcome            | <-- | 4. Workflow Execution | <-- | Decision & Policy Subsystem     |  |
|  | Verification Context  |     | & Tools Context       |     | (AI Advisor + Policy Gate)      |  |
|  +-----------------------+     +-----------------------+     +---------------------------------+  |
|             |                                                                |                    |
|             v                                                                v                    |
|  +-----------------------------------------------------+     +---------------------------------+  |
|  | 6. Audit & Compliance Context                       |     | 7. Analytics & Evaluation       |  |
|  | (Append-Only Event Ledger)                          |     | Context (Batch Benchmarking)    |  |
|  +-----------------------------------------------------+     +---------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

### Context 1: Payment Management Context
- **Purpose:** Ingests, authenticates, and normalizes raw payment event notifications from external providers or the payment simulator.
- **Responsibilities:** HMAC signature verification, payload schema validation, deduplication filtering, and storing immutable transaction records.
- **Owned Entities:** `Customer`, `Transaction`, `ProviderWebhookEvent`.
- **Inputs:** Raw webhook JSON payloads and headers.
- **Outputs:** Validated `PaymentEvent` domain messages.
- **Ubiquitous Language:** *Transaction, External Event ID, Payload Hash, Idempotency Receipt.*

### Context 2: Revenue Risk Assessment Context
- **Purpose:** Evaluates incoming payment events to determine if revenue is at risk and calculates risk severity and urgency.
- **Responsibilities:** Distinguishing failed payments from pending or succeeded payments, calculating at-risk minor units, identifying stale pending transactions (>24h).
- **Owned Entities:** Stateless scoring algorithms (uses `Transaction` data).
- **Inputs:** Validated `PaymentEvent`, customer historical payment profile.
- **Outputs:** `RiskAssessmentResult` (is_at_risk: bool, risk_score: float, urgency: UrgencyTier).
- **Ubiquitous Language:** *At-Risk Revenue, Soft Decline, Hard Decline, Stale Threshold.*

### Context 3: Recovery Case Management Context (Core)
- **Purpose:** Acts as the central operational coordinator for an at-risk revenue episode.
- **Responsibilities:** Case creation, managing lifecycle state transitions, tracking retry budgets, enforcing customer cooling-off windows, and linking decisions to outcomes.
- **Owned Entities:** `RecoveryCase`, `CaseStateTransition`.
- **Inputs:** Risk signals, trigger transactions, policy evaluations, verified evidence.
- **Outputs:** Case state updates, operator queue notifications, workflow execution commands.
- **Ubiquitous Language:** *Recovery Case, Case Key, State Machine, Terminal State, Priority.*

### Context 4: Recovery Workflow Execution & Tools Context
- **Purpose:** Executes bounded, safe actions against payment providers or customer communication adapters.
- **Responsibilities:** Generating unique idempotency keys, scheduling exponential backoff with jitter, invoking allow-listed provider tools, and capturing raw execution responses.
- **Owned Entities:** `RecoveryAttempt`, `ToolRegistry`.
- **Inputs:** Approved action commands from the Policy Gate.
- **Outputs:** `ExecutionResult` (succeeded, failed, uncertain).
- **Ubiquitous Language:** *Recovery Attempt, Idempotency Key, Sequence Number, Bounded Tool, Soft Decline Retry.*

### Context 5: Payment Outcome Verification Context
- **Purpose:** Proves that an alleged payment success legitimately recovers a specific failed transaction before revenue credit is granted.
- **Responsibilities:** Validating exact minor unit matches, customer matching, checking the 72-hour attribution window, and creating immutable evidence records.
- **Owned Entities:** `RecoveryEvidence`.
- **Inputs:** Provider success event, original failed transaction ID, case context.
- **Outputs:** Attribution verdict (`VERIFIED_ATTRIBUTED`, `REJECTED_UNMATCHED`).
- **Ubiquitous Language:** *Attribution Window, Verified Proof, Recovery Evidence, Matching Provider Event.*

### Context 6: Audit and Compliance Context
- **Purpose:** Records an append-only, chronologically ordered, tamper-resistant history of every operational decision, state change, and financial attempt.
- **Responsibilities:** Generating monotonic sequence numbers per case, recording correlation IDs, ensuring data minimization (zero PII/PCI in logs), and providing audit trails for compliance.
- **Owned Entities:** `AuditEvent`.
- **Inputs:** Lifecycle events from all contexts.
- **Outputs:** Immutable audit stream.
- **Ubiquitous Language:** *Audit Trail, Monotonic Sequence, Correlation ID, Actor Type, Safe Payload.*

### Context 7: Analytics and Evaluation Context
- **Purpose:** Computes aggregate performance benchmarks across 500-scenario batches with fixed random seeds (Seed 42) to evaluate recovery models across commits.
- **Responsibilities:** Running deterministic simulation batches, computing financial recovery rates, safety policy compliance rates, and generating evaluation markdown reports.
- **Owned Entities:** `EvaluationRun`, `EvaluationScenario`, `EvaluationResult`.
- **Inputs:** Evaluation batch configurations, seed integers, strategy versions.
- **Outputs:** `BatchMetrics` (recovered_revenue_minor, recovery_rate_pct, safety_rate_pct).
- **Ubiquitous Language:** *Evaluation Run, Scenario Category, Ground Truth, Safety Compliance, Baseline.*

---

## 3. Aggregate Roots & Consistency Boundaries

In Domain-Driven Design, an **Aggregate** is a cluster of associated domain objects that we treat as a single unit for data changes. Every aggregate has an **Aggregate Root** (an entity that external objects are allowed to hold references to).

### Why Aggregate Boundaries Matter (Beginner Explanation)
If two background workers or a worker and an operator update different parts of the same recovery case at the same time without an aggregate boundary, the data becomes corrupted. 
For example:
- Worker 1 adds a 2nd retry attempt.
- Worker 2 simultaneously adds a 3rd retry attempt because it didn't see Worker 1's change yet.
- Result: The customer is charged 3 times, violating **Invariant INV-002 (Max 2 Retries)**!

By enforcing aggregate boundaries, **all mutations to attempts, state transitions, and decisions must pass through the `RecoveryCase` Aggregate Root in a single ACID database transaction.**

---

### Aggregate 1: `RecoveryCase` (Central Domain Aggregate)
- **Aggregate Root:** `RecoveryCase`
- **Internal Entities & Value Objects:**
  - `RecoveryAttempt` (Internal Child Entity)
  - `CaseStateTransition` (Internal Child Entity)
  - `AgentDecision` (Internal Child Entity)
  - `AuditEvent` (Internal Append-Only Record)
- **Invariants Protected by the Root:**
  1. **INV-001 (Policy Supremacy):** No attempt can be created without a validated `AgentDecision` bearing `validation_status = 'VALIDATED'`.
  2. **INV-002 (Bounded Retries):** `count(RecoveryAttempt WHERE status != 'CANCELLED') <= 2`. Attempt 3 is strictly blocked.
  3. **INV-004 (Terminal State Lock):** If `state` is `RECOVERED`, `FAILED`, or `TERMINATED`, no further state transitions or attempts are permitted. Ever.
  4. **INV-005 (Monotonic Sequencing):** Sequence numbers for transitions, attempts, and audit events must increase monotonically (`1, 2, 3...`) with zero gaps or duplicates.
  5. **INV-006 (Strict Idempotency):** Every attempt must possess a deterministic, unique `idempotency_key`.
- **Transactional Boundary:** Synchronous ACID transaction. When a recovery action executes, the case state update, attempt record, transition record, and audit event are committed together or all rolled back.

```
+-----------------------------------------------------------------------------------+
|                        AGGREGATE ROOT: RecoveryCase                               |
|                                                                                   |
|  Root Attributes: id, case_key, state, version, opened_at, closed_at              |
|                                                                                   |
|  [ Invariant Checks: Terminal Lock | Retry Budget <= 2 | Valid Transitions ]     |
|                                                                                   |
|  +--------------------+   +---------------------+   +--------------------------+  |
|  |  RecoveryAttempt   |   | CaseStateTransition |   |     AgentDecision        |  |
|  |  (Attempt 1..2)    |   | (Sequential FSM)    |   | (Validated Action Intent)|  |
|  +--------------------+   +---------------------+   +--------------------------+  |
|            |                         |                           |                |
|            +-------------------------+---------------------------+                |
|                                      |                                            |
|                                      v                                            |
|                        +---------------------------+                              |
|                        |        AuditEvent         |                              |
|                        | (Append-Only Audit Record)|                              |
|                        +---------------------------+                              |
+-----------------------------------------------------------------------------------+
```

---

### Aggregate 2: `Customer` (Reference Aggregate)
- **Aggregate Root:** `Customer`
- **Role:** Master reference record representing the merchant's customer identity, account standing, and contact status.
- **Invariants Protected:**
  - External customer identity is unique per provider: `UniqueConstraint("provider", "external_customer_id")`.
  - Customers with `status = 'RESTRICTED'` or `'INACTIVE'` cannot have active recovery cases opened against them.

---

### Aggregate 3: `Transaction` (Financial Event Aggregate)
- **Aggregate Root:** `Transaction`
- **Role:** Immutable ledger of financial payment attempts received from providers or created during recovery.
- **Invariants Protected:**
  - Non-negative minor units: `amount_minor >= 0`.
  - Valid ISO-4217 3-character uppercase currency.
  - External transaction identity is globally unique per provider: `UniqueConstraint("provider", "external_transaction_id")`.

---

### Aggregate 4: `EvaluationRun` (Batch Experiment Aggregate)
- **Aggregate Root:** `EvaluationRun`
- **Internal Entities:** `EvaluationScenario`, `EvaluationResult`
- **Invariants Protected:**
  - Reproducibility invariant: Given the same `random_seed` (Seed 42) and `scenario_count` (500), the generated scenario dataset and expected baseline outcomes are identical.
  - Evaluation results are marked `is_synthetic = True` and are strictly partitioned from operational production metrics.
