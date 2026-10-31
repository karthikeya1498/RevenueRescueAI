# RevenueRescueAI — System Architecture Diagrams
## Phase 1.1: Visual Architecture, Data Flows, and Sequence Models

**Document Version:** 1.0.0  
**Status:** Approved Architectural Diagrams  
**Format:** GitHub Flavored Markdown with Native Mermaid Syntax  

---

## 1. High-Level System Architecture Diagram

This diagram visualizes the modular monolith architecture of RevenueRescueAI, showing the flow of control from the user interface down through the API gateway, core processing engines, policy security boundary, and the persistent relational database ledger.

```mermaid
graph TB
    subgraph Client["Client Tier (Presentation Layer)"]
        User["Fintech Operator / Risk Manager"]
        Dashboard["React 19 Dashboard\n(Vite + TypeScript + Neon Tokens)"]
        User -->|"Interacts with UI"| Dashboard
    end

    subgraph API["Application Gateway (FastAPI 0.115)"]
        IngressRoute["/api/v1/webhooks/payment-events"]
        QueueRoute["/api/v1/recovery/cases"]
        EvaluationRoute["/api/v1/evaluation/run"]
        RealtimeRoute["/api/v1/ws/realtime"]
        AuthMiddleware["Auth & RBAC Middleware\n(JWT / Role Enforcement)"]
        ObsMiddleware["Observability Middleware\n(Request ID / Structured Logs)"]
    end

    Dashboard -->|"HTTPS Requests"| IngressRoute
    Dashboard -->|"Queue Operations"| QueueRoute
    Dashboard -->|"Trigger Batch Run"| EvaluationRoute
    Dashboard <-->|"WebSocket Stream"| RealtimeRoute

    subgraph CoreEngine["Modular Monolith Core (In-Memory Python Domain)"]
        subgraph Ingestion["Ingestion & Validation Engine"]
            Validator["Payment Event Validator"]
            Deduplicator["Duplicate Event Detector\n(Idempotency Filter)"]
            RiskEngine["Risk Assessment Engine\n(Severity & Urgency Scoring)"]
        end

        subgraph Workflow["Workflow & State Management"]
            RecoveryFSM["Recovery Workflow Engine\n(Finite State Machine)"]
            Eligibility["Recovery Eligibility Engine"]
            Scheduler["Retry & Backoff Scheduler"]
        end

        subgraph Intelligence["Decision & Policy Layer"]
            DiagnosisEngine["Failure Diagnosis Engine"]
            AIBrain["AI Recommendation Engine\n(Baseline / LLM Advisor)"]
            PolicyGate{"Deterministic Policy Gate\n(Safety Invariants INV-001..016)"}
        end

        subgraph Execution["Execution & Verification"]
            ToolRegistry["Bounded Tool Registry"]
            PaymentSimulator["Payment Provider Simulator\n(Deterministic Seed 42)"]
            VerificationService["Outcome Verification Service\n(72h Window Attribution)"]
        end

        subgraph Analytics["Audit & Analytics"]
            AuditService["Audit Trail Service\n(Monotonic Sequence Counter)"]
            EvaluationEngine["Analytics & Evaluation Engine\n(Batch Metrics Calculator)"]
        end
    end

    IngressRoute --> ObsMiddleware --> AuthMiddleware --> Validator
    Validator --> Deduplicator --> RiskEngine --> RecoveryFSM
    RecoveryFSM --> Eligibility --> DiagnosisEngine --> AIBrain
    AIBrain -->|"Structured Intent"| PolicyGate

    PolicyGate -->|"ALLOWED"| ToolRegistry
    PolicyGate -->|"VETOED / BLOCKED"| RecoveryFSM
    PolicyGate -->|"ESCALATE"| RecoveryFSM

    ToolRegistry -->|"Execute Charge / Update"| PaymentSimulator
    PaymentSimulator -->|"Simulated Outcome"| VerificationService
    VerificationService -->|"Verified Evidence"| RecoveryFSM

    RecoveryFSM -.->|"Record Transitions"| AuditService
    ToolRegistry -.->|"Record Attempts"| AuditService
    PolicyGate -.->|"Record Decisions"| AuditService

    EvaluationRoute --> EvaluationEngine
    EvaluationEngine --> Ingestion

    subgraph Persistence["Persistence Tier (ACID Relational Storage)"]
        DB[(PostgreSQL 16 Engine / SQLite Test Dialect)]
        CustomersTable["customers"]
        TxnTable["transactions"]
        CasesTable["recovery_cases"]
        AttemptsTable["recovery_attempts"]
        DecisionsTable["agent_decisions"]
        AuditTable["audit_events"]
        EvidenceTable["recovery_evidence"]
        WebhookEventsTable["provider_webhook_events"]
    end

    Deduplicator <-->|"Check (provider, event_id)"| WebhookEventsTable
    RecoveryFSM <-->|"Persist State & Version"| CasesTable
    ToolRegistry <-->|"Store Attempt & Key"| AttemptsTable
    PolicyGate <-->|"Store Validated Decision"| DecisionsTable
    AuditService <-->|"Append Only Ledger"| AuditTable
    VerificationService <-->|"Store Verified Proof"| EvidenceTable
    Analytics <-->|"Compute Batch KPI Queries"| DB
```

---

## 2. End-to-End Data Flow Diagram

This flow diagram illustrates the end-to-end journey of an at-risk payment transaction through every processing stage, showing normal recovery, policy veto, provider timeout, and compliant escalation paths.

```mermaid
flowchart TD
    Start([Payment Failure Event Ingested]) --> Step1[Step 1: Ingestion & HMAC Signature Check]
    
    Step1 --> CheckSig{Signature Valid?}
    CheckSig -- No --> Drop401([Reject HTTP 401 / Alert Security])
    CheckSig -- Yes --> Step2[Step 2: Schema Validation & Normalization]

    Step2 --> CheckSchema{Schema Valid?}
    CheckSchema -- No --> Drop422([Reject HTTP 422 Unprocessable])
    CheckSchema -- Yes --> Step3[Step 3: Deduplication & Idempotency Check]

    Step3 --> CheckDup{Already Processed?}
    CheckDup -- Yes --> Return200([Return Cached HTTP 200 / Drop Duplicate])
    CheckDup -- No --> Step4[Step 4: Revenue Risk Assessment]

    Step4 --> CheckRisk{Risk Detected?}
    CheckRisk -- No --> StoreOnly([Store Event / No Recovery Needed])
    CheckRisk -- Yes --> Step5[Step 5: Recovery Case Creation & Eligibility Check]

    Step5 --> CheckEligible{Eligible for Recovery?}
    CheckEligible -- No: Frozen/Disputed/Terminated --> Step5Escalate[Transition to TERMINATED or ESCALATED]
    CheckEligible -- Yes --> Step6[Step 6: Root-Cause Diagnosis]

    Step6 --> Step7[Step 7: AI Brain Recommendation Generation]
    Step7 --> Step8[Step 8: Deterministic Policy Gate Evaluation]

    Step8 --> CheckPolicy{Policy Check Result?}
    
    CheckPolicy -- REJECTED / VETOED --> Step8Reject[Reject Action / Transition to FAILED]
    CheckPolicy -- ESCALATE: Retry Budget / Cooling-off --> Step8Escalate[Transition to ESCALATED / Operator Queue]
    CheckPolicy -- APPROVED --> Step9[Step 9: Bounded Tool Execution via Simulator]

    Step9 --> CheckSimResult{Simulator Outcome?}
    
    CheckSimResult -- Hard Decline: Expired/Stolen --> Step9Hard[Mark Attempt Failed / Stop Retry / Escalate]
    CheckSimResult -- Transient 504 / Timeout --> Step9Timeout[Transition to VERIFICATION_PENDING]
    CheckSimResult -- Soft Decline: Insufficient Funds --> Step9Soft[Schedule Exponential Backoff Retry]
    CheckSimResult -- Succeeded --> Step10[Step 10: Outcome Verification Service]

    Step9Timeout --> Step10Verify{Inquire Provider Status}
    Step10Verify -- Confirmed Succeeded --> Step10
    Step10Verify -- Confirmed Failed --> Step9Soft
    Step10Verify -- Still Uncertain --> KeepPending[Remain in VERIFICATION_PENDING / Alert Human]

    Step10 --> CheckEvidence{Evidence Matches & < 72h?}
    CheckEvidence -- No --> RejectRecovery[Deny Attribution / Escalate]
    CheckEvidence -- Yes --> Step11[Step 11: Create Immutable Evidence Record & Mark RECOVERED]

    Step11 --> Step12[Step 12: Record Append-Only Audit Event]
    Step8Escalate --> Step12
    Step9Hard --> Step12
    Step9Soft --> Step12
    
    Step12 --> Step13[Step 13: Push Realtime WebSocket Update to Dashboard]
    Step13 --> Step14[Step 14: Update Batch Analytics & Revenue Metrics]
    Step14 --> End([Lifecycle Complete])
```

---

## 3. Sequence Diagrams: Critical Interaction Flows

### 3.1 Normal Recovery Flow (Soft Decline with Successful Recovery)

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Synthetic Customer
    participant Provider as Payment Simulator
    participant Ingestion as Ingestion Service
    participant FSM as Recovery FSM
    participant Agent as AI Recommendation Engine
    participant Policy as Deterministic Policy Gate
    participant Tools as Tool Execution Service
    participant Verify as Verification Service
    participant DB as Relational Database
    participant UI as Operator Dashboard

    Customer->>Provider: Transaction Fails (insufficient_funds)
    Provider->>Ingestion: Webhook: payment_intent.failed
    Ingestion->>DB: Check idempotency (provider, event_id)
    Note over Ingestion,DB: Record stored in provider_webhook_events
    Ingestion->>FSM: Create or Update RecoveryCase (state: DETECTED)
    FSM->>DB: INSERT INTO recovery_cases (state='DETECTED')
    FSM->>Agent: Request Recommendation (code: insufficient_funds)
    Agent->>Policy: Propose Decision: RETRY_NOW (confidence: 0.94)
    Policy->>Policy: Check Invariants (INV-001, INV-002, INV-006)
    Note over Policy: Invariants PASS: Attempt 1 of 2, Not Terminal
    Policy->>DB: INSERT INTO agent_decisions (status='VALIDATED')
    Policy->>FSM: Authorize Action: RETRY_NOW
    FSM->>Tools: Execute retry_payment (idempotency_key: idemp_001)
    Tools->>DB: INSERT INTO recovery_attempts (status='IN_PROGRESS')
    Tools->>Provider: POST /charges (amount: 842000, key: idemp_001)
    Provider-->>Tools: 200 OK (status: 'succeeded', charge_id: 'ch_8F31')
    Tools->>DB: UPDATE recovery_attempts (status='SUCCEEDED')
    Tools->>Verify: Submit Evidence for Verification
    Verify->>Verify: Validate exact match (amount, customer, <72h)
    Verify->>DB: INSERT INTO recovery_evidence (attributable=TRUE)
    Verify->>FSM: Transition State to RECOVERED
    FSM->>DB: UPDATE recovery_cases (state='RECOVERED', closed_at=NOW)
    FSM->>DB: INSERT INTO audit_events (from='ACTION_PENDING', to='RECOVERED')
    FSM->>UI: WebSocket broadcast (case_id, state: 'RECOVERED')
```

### 3.2 Safety Escalation Flow (Retry Budget Exceeded — INV-002)

```mermaid
sequenceDiagram
    autonumber
    participant Ingestion as Ingestion Service
    participant FSM as Recovery FSM
    participant Agent as AI Recommendation Engine
    participant Policy as Deterministic Policy Gate
    participant DB as Relational Database
    participant UI as Operator Dashboard

    Ingestion->>FSM: Third Payment Failure Event Arrives
    FSM->>DB: Query existing attempts for Case
    DB-->>FSM: Count = 2 attempts already executed
    FSM->>Agent: Request Recommendation
    Agent->>Policy: Propose Action: RETRY_NOW (confidence: 0.88)
    Note over Policy: Evaluating Invariant INV-002: Maximum 2 Retries
    Policy->>Policy: VETO: Retry budget exhausted (2/2)
    Policy->>DB: INSERT INTO agent_decisions (action='ESCALATE_TO_HUMAN', status='OVERRIDDEN_BY_POLICY')
    Policy->>FSM: Force Escalation: STOP_ACTION_ESCALATE
    FSM->>DB: UPDATE recovery_cases (state='ESCALATED')
    FSM->>DB: INSERT INTO audit_events (type='CASE_ESCALATED', reason='retry_limit_reached')
    FSM->>UI: WebSocket Alert: Case placed in Human-in-the-Loop Queue
    Note over UI: Operator inspects case with full trace log
```

### 3.3 Uncertain Outcome & Verification Handshake (Timeout — INV-008)

```mermaid
sequenceDiagram
    autonumber
    participant FSM as Recovery FSM
    participant Tools as Tool Execution Service
    participant Provider as Payment Simulator
    participant Verify as Verification Service
    participant DB as Relational Database
    participant UI as Operator Dashboard

    FSM->>Tools: Execute Action: RETRY_NOW
    Tools->>DB: INSERT INTO recovery_attempts (status='IN_PROGRESS')
    Tools->>Provider: POST /charges (charge_req_002)
    Note over Provider,Tools: Network Drop / Simulator Injects 504 Gateway Timeout
    Provider--xTools: HTTP 504 Gateway Timeout (No Body)
    Note over Tools: Outcome is UNCERTAIN. Never retry blindly!
    Tools->>DB: UPDATE recovery_attempts (status='UNCERTAIN', error='HTTP_504')
    Tools->>FSM: Report Result: UNCERTAIN
    FSM->>DB: UPDATE recovery_cases (state='VERIFICATION_PENDING')
    FSM->>DB: INSERT INTO audit_events (to='VERIFICATION_PENDING', reason='provider_timeout')
    FSM->>UI: WebSocket Update: Case in Verification Pending
    
    loop Scheduled Verification Inquiries (Backoff)
        Verify->>Provider: GET /charges?idempotency_key=charge_req_002
        Provider-->>Verify: Return Charge Status ('succeeded' after delayed settlement)
    end
    
    Verify->>DB: INSERT INTO recovery_evidence (attributable=TRUE)
    Verify->>FSM: Confirm Legitimate Recovery
    FSM->>DB: UPDATE recovery_cases (state='RECOVERED')
    FSM->>DB: INSERT INTO audit_events (to='RECOVERED', reason='delayed_verification_succeeded')
    FSM->>UI: WebSocket: Case Cleared to Recovered
```

---

## 4. Deployment Architecture

This diagram contrasts the local development environment against the containerized production deployment topology.

```mermaid
graph TB
    subgraph LocalDev["Local Development Environment"]
        ViteDev["Vite Dev Server (Port 5173)\nReact 19 + HMR"]
        UvicornDev["Uvicorn ASGI Server (Port 8000)\nFastAPI Application with Reload"]
        SQLiteDB[("SQLite Database File\n(revenuerescue.db)\nFK Enforced & Thread-Safe")]
        InMemSim["In-Memory Payment Simulator\nDeterministic Seed 42"]

        ViteDev <-->|"Proxy /ws & /api"| UvicornDev
        UvicornDev <-->|"SQLAlchemy 2.0 Sessions"| SQLiteDB
        UvicornDev <-->|"In-Memory Function Calls"| InMemSim
    end

    subgraph ProductionDeployment["Production / Staging Container Architecture"]
        subgraph Internet["Public Ingress"]
            ClientBrowser["Client Browser / Mobile"]
            ProviderWebhook["Payment Gateway Webhook"]
        end

        subgraph ReverseProxy["Ingress Tier (Nginx / Cloudflare)"]
            Nginx["Nginx Reverse Proxy & SSL Termination\nRate Limiting & Static Asset Hosting"]
        end

        subgraph ContainerCluster["Docker Container Network"]
            BackendApp["FastAPI ASGI Container (Gunicorn + Uvicorn Workers)\nStateless Modular Monolith"]
            PostgresContainer[("PostgreSQL 16 Alpine Container\n(Persistent Volume: postgres-data)\nStrict Schema Constraints & Indexes")]
        end

        subgraph ExternalAPIs["External AI Provider (Optional)"]
            OpenAIAPI["OpenAI API (GPT-4o-mini)\nStrict JSON Schema Contract\nZero PCI / Masked Metadata"]
        end

        ClientBrowser -->|"HTTPS (Port 443)"| Nginx
        ProviderWebhook -->|"HTTPS Webhook POST"| Nginx
        Nginx -->|"Serve Precompiled SPA"| ClientBrowser
        Nginx -->|"Proxy API & WebSocket (Port 8000)"| BackendApp
        BackendApp <-->|"psycopg 3 Connection Pool"| PostgresContainer
        BackendApp -.->|"HTTPS Structured Advice (Optional)"| OpenAIAPI
    end
```
