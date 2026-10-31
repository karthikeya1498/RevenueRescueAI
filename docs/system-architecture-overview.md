# RevenueRescueAI — Consolidated System Architecture Overview
## Phase 1.4: System Architecture Validation and End-to-End Component Topology

**Document Version:** 1.0.0  
**Status:** Approved Architectural Blueprint  
**Primary Authors:** Senior Software Architect, System Designer, Technical Reviewer  
**Target Audience:** Engineering Team, System Architects, Technical Interviewers, Novice Developers  

---

## 1. Executive Summary & Core Architectural Paradigm

RevenueRescueAI is an autonomous, bounded, and auditable revenue recovery platform designed to detect payment failures in subscription and transactional commerce, diagnose root causes, recommend recovery actions, strictly enforce financial safety invariants, and verify recovery outcomes.

The platform is designed around the architectural doctrine of **Deterministic Policy Supremacy with Zero-Trust AI Intelligence**:
- **The AI Recommends; It Never Executes:** The AI agent is an untrusted external reasoning component that outputs structured candidate intent. It possesses zero execution permissions and zero tool-calling authority.
- **The Policy Engine Holds Absolute Veto Power:** Deterministic Python business rules validate all actions against hardcoded safety invariants (INV-001 through INV-016), retry budgets (max 2 retries), and customer cooling-off periods before any financial tool can be touched.
- **Execution is Strictly Bounded and Idempotent:** Every recovery action against the payment simulator carries a deterministic, unique `Idempotency-Key` preventing duplicate charges.
- **Outcomes Require Hard Verification:** A case cannot transition to `RECOVERED` based on optimistic expectations; it requires matching transaction evidence settled within 72 hours.
- **Single Deployable Modular Monolith:** Packaged into cleanly segregated internal domain modules running in one process with atomic ACID database transactions, avoiding the network latency and distributed transaction hazards of premature microservices.

---

## 2. Consolidated System Architecture Diagram

The following Mermaid diagram visualizes the complete end-to-end topology of RevenueRescueAI, showing communication paths between user actors, client applications, API gateways, internal engines, policy gates, persistent storage, and the payment simulator.

```mermaid
graph TB
    subgraph ClientTier["Client Tier (Presentation Layer)"]
        Operator["Fintech Operator / Risk Analyst"]
        Dashboard["React 19 Dashboard\n(Vite + TypeScript + Neon Tokens)\n[Overview, Queue, Traces, Eval]"]
        Operator -->|"Interacts via HTTPS / WSS"| Dashboard
    end

    subgraph APIGateway["Application API Gateway (FastAPI 0.115)"]
        Router["HTTP Router & Middleware"]
        AuthMiddleware["Auth & RBAC Middleware\n(Bearer JWT & HMAC Verify)"]
        ObsMiddleware["Observability Middleware\n(Correlation ID Tracing)"]
        WSServer["WebSocket Hub\n(/api/v1/ws/realtime)"]
        
        Dashboard -->|"REST API Calls"| Router
        Dashboard <-->|"WSS Event Stream"| WSServer
        Router --> ObsMiddleware --> AuthMiddleware
    end

    subgraph CoreEngine["Modular Monolith Core (In-Memory Python Domain)"]
        subgraph IngestionBoundary["1. Ingestion & Risk Subsystem"]
            Validator["Payment Event Validator"]
            Deduplicator["Duplicate Event Detector\n(7-Day Window Filter)"]
            RiskEngine["Risk Assessment Engine\n(Severity & Urgency Scoring)"]
        end

        subgraph WorkflowBoundary["2. Workflow & State Management"]
            RecoveryFSM["Recovery Workflow Engine\n(Finite State Machine)"]
            Eligibility["Recovery Eligibility Engine"]
            Scheduler["Retry & Backoff Scheduler"]
        end

        subgraph IntelligenceBoundary["3. Decision & Policy Subsystem"]
            DiagnosisEngine["Failure Diagnosis Engine\n(Soft vs. Hard Decline)"]
            AIBrain["AI Recommendation Engine\n(Baseline / LLM Advisor)"]
            PolicyGate{"Deterministic Policy Gate\n(Invariants INV-001..016)\n[ABSOLUTE VETO]"}
        end

        subgraph ExecutionBoundary["4. Execution & Verification"]
            ToolRegistry["Bounded Tool Registry"]
            PaymentSimulator["Payment Provider Simulator\n(Deterministic Seed 42)"]
            VerificationService["Outcome Verification Service\n(72h Attribution Proof)"]
        end

        subgraph AnalyticsBoundary["5. Audit & Metrics Subsystem"]
            AuditService["Audit Trail Service\n(Monotonic Sequence Counter)"]
            MetricsService["Dashboard Metrics Engine\n(Authoritative Minor Units)"]
            EvaluationEngine["500-Scenario Evaluation Lab"]
        end
    end

    AuthMiddleware -->|"Validated Webhook"| Validator
    Validator --> Deduplicator --> RiskEngine --> RecoveryFSM
    RecoveryFSM --> Eligibility --> DiagnosisEngine --> AIBrain
    AIBrain -->|"Candidate Decision Contract"| PolicyGate

    PolicyGate -->|"ALLOWED"| ToolRegistry
    PolicyGate -->|"VETOED / ESCALATE"| RecoveryFSM

    ToolRegistry -->|"Dispatch Charge / Link"| PaymentSimulator
    PaymentSimulator -->|"Simulated Outcome"| VerificationService
    VerificationService -->|"Verified Proof"| RecoveryFSM

    RecoveryFSM -.->|"State Transitions"| AuditService
    ToolRegistry -.->|"Execution Attempt"| AuditService
    PolicyGate -.->|"Validation Record"| AuditService

    Router -->|"Query Metrics"| MetricsService
    Router -->|"Batch Trigger"| EvaluationEngine
    EvaluationEngine --> IngestionBoundary

    AuditService -.->|"Live Notification"| WSServer
    RecoveryFSM -.->|"Case Update"| WSServer

    subgraph PersistenceTier["Persistence Tier (PostgreSQL 16 / SQLite Dialect)"]
        DB[(ACID Relational Database)]
        Customers["customers"]
        Transactions["transactions"]
        Webhooks["provider_webhook_events"]
        Cases["recovery_cases"]
        Attempts["recovery_attempts"]
        Decisions["agent_decisions"]
        Transitions["case_state_transitions"]
        AuditEvents["audit_events"]
        Evidence["recovery_evidence"]
    end

    Deduplicator <-->|"Unique (provider, event_id)"| Webhooks
    RecoveryFSM <-->|"Atomic Case State & Version"| Cases
    RecoveryFSM <-->|"FSM History"| Transitions
    ToolRegistry <-->|"Unique Idempotency Key"| Attempts
    PolicyGate <-->|"Decision Record"| Decisions
    AuditService <-->|"Append-Only Sequence"| AuditEvents
    VerificationService <-->|"Unique Attribution Proof"| Evidence
    MetricsService <-->|"Covering B-Tree Aggregations"| Evidence
```

---

## 3. Communication Patterns & Information Flow

The architecture defines six explicit communication streams:

| Stream Type | Origin $\to$ Destination | Communication Style | Protocol | Guarantees |
| :--- | :--- | :--- | :--- | :--- |
| **User Requests** | Operator $\to$ Frontend $\to$ Backend | Request-Response | HTTPS REST | TLS 1.3, Bearer JWT Auth, Idempotency-Key on POSTs |
| **Realtime Push**| Backend $\to$ Frontend Dashboard | Persistent Streaming | WSS WebSocket | Low-latency updates (<100ms), automatic backoff reconnect |
| **Internal Domain**| Router $\to$ Services $\to$ Policy $\to$ FSM | In-Memory Function Calls | Python Native Types | Sub-millisecond latency, zero serialization, typed contracts |
| **Database Operations**| Domain Repositories $\to$ Database | Transactional Queries | psycopg / SQLAlchemy | ACID transactions, row-level locking, foreign key integrity |
| **AI Intelligence**| Diagnosis $\to$ AI Engine $\to$ Policy Gate | Structured JSON Contract | Pydantic Schema | Zero execution privileges; pure intent proposal |
| **External Simulation**| Tool Registry $\to$ Payment Simulator | Emulated Banking Rails | In-Memory Adapter | Deterministic Seed 42, fault injection, idempotency cache |

---

## 4. Component Responsibility Breakdown

1. **Frontend Dashboard:** Renders the dark neon fintech interface, symmetrical 152px KPI cards, recovery queues, and agent journey timelines. Never computes authoritative metrics locally.
2. **Backend API Gateway:** Validates request formats, enforces authentication/RBAC, extracts correlation IDs, formats RFC 7807 error envelopes, and terminates TLS.
3. **Ingestion & Deduplication:** Catches inbound webhooks, verifies HMAC signatures, checks 7-day deduplication windows via `uq_provider_event`, and logs receipts.
4. **Revenue Risk Engine:** Evaluates transaction amounts and decline codes to score urgency and calculate at-risk minor units.
5. **AI Recommendation Engine:** Generates candidate decision proposals using the deterministic baseline or an external LLM advisor.
6. **Deterministic Policy Gate:** Holds supreme authority over execution. Evaluates Invariants INV-001 through INV-016 and vetoes unauthorized actions.
7. **Recovery Workflow Engine (FSM):** Manages atomic lifecycle transitions across nine explicit case states with monotonic sequence numbering and optimistic concurrency versioning.
8. **Payment Provider Simulator:** Emulates card charges, soft/hard declines, and network timeouts with 100% reproducible outcomes under Seed 42.
9. **Outcome Verification Service:** Proves legitimate recovery attribution against matching evidence within 72 hours before cases can transition to `RECOVERED`.
10. **Audit Service:** Maintains a permanent, append-only chronological event ledger with monotonically increasing sequence numbers and zero update/delete permissions.
11. **Dashboard Metrics Service:** Computes authoritative financial KPIs directly from the relational database using exact integer minor units.
