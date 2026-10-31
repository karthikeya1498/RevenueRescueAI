# RevenueRescueAI — System Architecture Specification
## Phase 1.1: System Architecture Design and Technology Selection

**Document Version:** 1.0.0  
**Status:** Approved Architectural Blueprint  
**Primary Authors:** Principal Software Architect, Senior Full-Stack Engineer, AI Systems Architect, Database Architect, DevOps & Security Engineer  
**Target Audience:** Engineering Team, Technical Interviewers, Novice Developers  

---

## 1. Executive Summary & Architectural Vision

RevenueRescueAI is an autonomous, auditable, and bounded revenue recovery platform designed to detect payment failures in subscription and transactional commerce, diagnose root causes, recommend recovery actions, strictly enforce financial safety invariants, and verify recovery outcomes.

The core mission of the architecture is summarized by the problem statement:
> *"Find revenue that's slipping away and win it back safely, deterministically, and with mathematically verified proof."*

### The Core Architectural Challenge
Modern AI agents frequently fail in enterprise financial systems because probabilistic large language models (LLMs) are given unconstrained tool-calling authority. If an AI hallucinates a retry on an already-settled invoice or executes a 10th retry on an empty bank account, it incurs gateway fees, damages customer trust, and violates regulatory card network mandates (such as Visa/Mastercard retry limits).

RevenueRescueAI solves this with an architectural paradigm called **Deterministic Policy Supremacy with Zero-Trust AI Intelligence**:
1. **The AI recommends; it never executes.** The AI agent is treated as an untrusted external advisor that produces structured intent.
2. **The Policy Engine holds absolute veto authority.** Deterministic Python rules evaluate strict safety invariants (INV-001 through INV-016) before any action touches banking rails.
3. **Execution is strictly bounded and idempotent.** Every state change, simulated charge, and escalation is executed within ACID transactional boundaries with unique idempotency keys.
4. **Outcomes are verified against hard provider evidence.** Revenue is declared "recovered" only when matching transaction evidence is received within a 72-hour attribution window.

---

## 2. Architectural Style Evaluation

We evaluated four architectural patterns to select the optimal design for the RevenueRescueAI MVP:

| Architectural Style | Complexity | Dev Velocity | Deployment | Testing | Data Consistency | Operational Cost | Suitability for MVP |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Monolithic (Ad-Hoc)** | Very Low | Fast initially, degrades rapidly | Single binary/script | Difficult as code grows | High (single DB) | Very Low | Poor (leads to "spaghetti code") |
| **Modular Monolith** | **Low–Medium** | **High & Sustainable** | **Single Container** | **Fast & Isolated** | **ACID Guaranteed** | **Minimal** | **Optimal (Recommended)** |
| **Microservices** | Very High | Very Slow (network plumbing) | Multi-container orchestration | Complex (contract tests, mocks) | Eventual consistency (Sagas/2PC) | High (cloud overhead) | Poor (Unjustified Overengineering) |
| **Event-Driven (Broker)** | Medium–High | Medium | Broker + Workers + App | Async test complexity | Eventual consistency | Medium | Overkill for synchronous core |

### Why Modular Monolith is the Right Decision (Beginner-Friendly Explanation)

A **Modular Monolith** is a single deployable application where the code is strictly organized into independent, decoupled internal modules (packages) with clearly defined public interfaces.

#### Why NOT Microservices?
In beginner software discussions or hype-driven engineering, people often suggest splitting an application into 10 separate microservices (e.g., Auth Service, Ingestion Service, Policy Service, AI Service, Simulator Service). In reality:
- **Network Failures & Latency:** Every HTTP call between microservices can fail, timeout, or drop packets, requiring complex retry mechanisms, circuit breakers, and distributed tracing.
- **Distributed Transactions:** In banking and revenue recovery, when a payment succeeds, we must update the case state, record the audit log, increment the sequence counter, and store the evidence. In a single database, this happens in **one atomic ACID transaction** (all succeed or all rollback). Across microservices, this requires complex distributed two-phase commits (2PC) or Saga patterns.
- **Operational Overhead:** Running 10 services requires Docker orchestrators, Kubernetes clusters, service meshes, and expensive cloud infrastructure.
- **Interview Standpoint:** Senior FAANG architects consistently look for engineers who choose the *simplest architecture that satisfies the requirements*. Choosing microservices for an early-stage fintech MVP is an anti-pattern.

#### The Modular Monolith Advantage:
- **In-Memory Speed & Reliability:** Modules communicate via direct, type-safe Python function calls. There is zero network latency and zero serialization overhead between internal components.
- **Strict Separation of Concerns:** Even though the code runs in one process, the `policy` module cannot tamper with `models` directly; the `agents` module has zero knowledge of database sessions; the `workflow` module orchestrates state transitions through strict service contracts.
- **Effortless Future Extraction:** If a specific component (e.g., the high-volume ingestion pipeline) ever experiences extreme traffic in production, its clean boundaries allow it to be extracted into a standalone microservice in hours without rewriting business logic.

---

## 3. High-Level System Boundaries

The application is partitioned into 7 distinct architectural layers, ensuring that business logic, persistence, and external communication remain cleanly separated:

```
+---------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER                                 |
|   React 19 Dashboard (Vite + TypeScript + Vanilla CSS Tokens + SVG Canvas/Recharts)   |
+---------------------------------------------------------------------------------------+
                                           |  HTTPS / WebSocket
                                           v
+---------------------------------------------------------------------------------------+
|                                APPLICATION API GATEWAY                                |
|          FastAPI 0.115 (Routes, Observability Middleware, Exception Handlers)         |
+---------------------------------------------------------------------------------------+
        |                        |                        |                       |
        v                        v                        v                       v
+----------------+      +----------------+      +------------------+    +---------------+
| INGESTION &    |      | WORKFLOW &     |      | AI INTELLIGENCE  |    | SIMULATION &  |
| DEDUPLICATION  | ---> | STATE MACHINE  | ---> | & POLICY GATE    | -> | TOOLS ADAPTER |
+----------------+      +----------------+      +------------------+    +---------------+
                                 |                        |                       |
                                 +------------------------+-----------------------+
                                                          |
                                                          v
+---------------------------------------------------------------------------------------+
|                               DOMAIN ENTITIES & PERSISTENCE                           |
|       SQLAlchemy 2.0 Core Models (PostgreSQL 16 Engine / SQLite Test Dialect)         |
|   ACID Transactions, 64-bit Integer Minor Units, Append-Only Audit & Evidence Logs    |
+---------------------------------------------------------------------------------------+
```

### Layer Definitions:
1. **Presentation Layer (`frontend/`):** A responsive, dark neon fintech dashboard providing real-time visibility into recovery queues, agent decision traces, safety policy overrides, and 500-scenario evaluation benchmarks.
2. **Application API Gateway (`backend/app/api/`):** FastAPI endpoints exposing RESTful contracts for ingestion webhooks, operator queue actions, real-time WebSocket streams, and evaluation execution.
3. **Ingestion & Deduplication (`backend/app/repositories/`, `services/risk_detection.py`):** Validates incoming payload schemas, verifies provider HMAC signatures, enforces idempotent receipt using `(provider, external_event_id)` uniqueness, and flags revenue risk.
4. **Workflow Engine (`backend/app/workflows/`):** Implements a deterministic finite state machine (FSM) managing recovery case lifecycles across explicit states (`DETECTED` -> `ANALYZING` -> `ACTION_SELECTED` -> `ACTION_PENDING` -> `RECOVERED` / `FAILED` / `ESCALATED` / `TERMINATED`).
5. **AI Intelligence & Policy Gate (`backend/app/agents/`, `backend/app/policy/`):**
   - *Agent Brain:* Produces structured candidate decisions using a deterministic baseline or LLM advisor.
   - *Policy Engine:* Evaluates safety invariants (INV-001 through INV-016), retry budgets, terminal state locks, and customer cooling-off windows.
6. **Simulation & Tools Adapter (`backend/app/tools/`, `backend/app/evaluation/`):** Emulates payment provider charges, card updates, transient timeouts, and webhooks with deterministic scenario seeding.
7. **Domain Persistence & Ledger (`backend/app/models/`):** Relational schema enforcing monetary integrity in integer minor units, immutable audit logs with monotonic sequence counters, and verified recovery attribution evidence.

---

## 4. Core Design Principles

1. **Deterministic Policy Supremacy (INV-001):** The policy gate is the ultimate authority. No external recommendation, operator prompt, or LLM output can override safety invariants, retry limits, or terminal states.
2. **Financial Integer Precision:** All monetary amounts are stored and calculated as 64-bit integers representing minor currency units (e.g., $42.50 USD is stored as `4250` cents). Floating-point math is strictly forbidden.
3. **Zero-Trust AI Boundaries:** External AI models receive strictly scrubbed context (zero PCI/PII data) and must respond in a rigid, validated JSON schema. If the model times out, errors, or recommends an unpermitted action, the system falls back safely to deterministic rules or operator escalation.
4. **Idempotent Side Effects (INV-006):** Every recovery action executed against a payment provider carries a unique, deterministic idempotency key. Repeating an action cannot cause a duplicate charge.
5. **Verified Recovery Attribution (INV-007):** A recovery case cannot transition to `RECOVERED` based on optimistic assumptions. It requires hard proof: a matching successful transaction record linked to the exact failed transaction within a 72-hour window.
6. **Immutable Audit Ledger:** Every state transition, agent decision, policy evaluation, and financial attempt is recorded in append-only database tables with strictly increasing sequence numbers and correlation IDs.
7. **Fail-Safe Defaults:** If any component experiences an unexpected exception, the system escalates the case to human review rather than guessing or retrying blindly.

---

## 5. Architectural Communication Patterns

Communication between modules is strictly structured based on the nature of the operation:

| Communication Style | Where It Is Used | Justification | Error Handling |
| :--- | :--- | :--- | :--- |
| **In-Memory Function Calls** | Between API routes, Services, Policy Engine, and Workflow | Zero latency, full type safety via Pydantic/Python types, runs in same ACID transaction. | Caught via typed exceptions; triggers transaction rollback. |
| **ACID Database Transactions** | State transitions, attempt creation, audit logging | Guarantees that state change and audit log record succeed together or fail together. | Rollback on DB error; locks released. |
| **Async Webhook Ingestion** | Ingestion from simulated/external payment providers | Decouples webhook receipt from recovery processing; responds with HTTP 200/202 in <50ms. | Persisted in `provider_webhook_events` before processing. |
| **WebSocket Streaming** | Real-time push from backend to frontend dashboard | Low-latency updates for operator queue, trace logs, and evaluation progress without polling. | Reconnect with exponential backoff; heartbeat ping/pong. |
| **Seeded In-Memory Simulation** | Evaluation engine running 500 scenarios | Fast execution (runs 500 cases in <10 seconds) with 100% reproducible outcomes via Seed 42. | Deterministic error capture per scenario. |

---

## 6. Alignment with Phase 0 Requirements

This architecture directly fulfills every approved Phase 0 requirement:
- **Scope Alignment:** Implements the failed-payment recovery lifecycle (Event Ingestion -> Validation -> Duplicate Detection -> Risk Assessment -> Recovery Eligibility -> Failure Diagnosis -> Intervention Selection -> Policy Enforcement -> Recovery Execution -> Outcome Verification -> Audit Logging -> Revenue Evaluation).
- **Invariants Preservation:** Implements strict architectural hooks for all 16 safety invariants (INV-001 through INV-016).
- **Fintech UI Specification:** Architected to support the dark neon dashboard tokens, 152px symmetrical KPI cards, and responsive workflow views without premature UI complexity.
- **Traceability:** Fully traceable to functional requirements FR-001 through FR-040 and business rules BR-001 through BR-030.
