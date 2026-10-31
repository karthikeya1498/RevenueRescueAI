# RevenueRescueAI — Component Responsibilities Specification
## Phase 1.1: System Boundaries, Module Ownership, and Contracts

**Document Version:** 1.0.0  
**Status:** Approved Component Architecture  
**Primary Authors:** Principal Software Architect, Senior Full-Stack Engineer, AI Systems Architect, Security Engineer  

---

## 1. Architectural Scope & Module Organization

To guarantee strict separation of concerns, RevenueRescueAI defines **18 distinct system modules** within a cohesive **Modular Monolith**. Every module owns a singular, well-defined responsibility with strict public contracts, explicit data access boundaries, and documented failure behaviors.

```
+-----------------------------------------------------------------------------------------------+
|                                     MODULE RESPONSIBILITY MAP                                 |
+--------------------------+------------------------------------+-------------------------------+
| Ingestion & Risk         | Workflow & Decision Layer          | Execution & Infrastructure    |
| • Event Ingestion        | • Recovery Workflow Engine (FSM)   | • Payment Provider Simulator  |
| • Event Validator        | • Recovery Eligibility Engine      | • Bounded Tool Registry       |
| • Duplicate Detector     | • Failure Diagnosis Engine         | • Outcome Verification Service|
| • Risk Assessment Engine | • AI Recommendation Engine         | • Audit Service               |
|                          | • Deterministic Policy Gate        | • Analytics & Evaluation      |
|                          | • Retry Scheduler                  | • Database & Persistence Layer|
+--------------------------+------------------------------------+-------------------------------+
```

---

## 2. Detailed Component Specifications

### 2.1 Frontend Application
- **Responsibility:** Renders the dark neon fintech command center, recovery queue, agent decision traces, and evaluation reports. Allows human operators to review escalations and trigger evaluation runs.
- **Inputs:** User clicks/inputs, HTTP REST responses from backend API, real-time WebSocket event frames.
- **Outputs:** HTTP requests (`GET /cases`, `POST /evaluation/run`, `POST /cases/{id}/escalate`), WebSocket handshake.
- **Dependencies:** Backend API Gateway.
- **Business Rules Owned:** Client-side display formatting, currency minor unit rendering (`$8,420.00`), search/filter query building.
- **Data Reads:** Read-only representations of cases, attempts, traces, and metrics.
- **Data Modifies:** Zero direct database access.
- **Failure Behavior:** Displays error toasts and offline reconnection indicators; retains local UI state without crashing.
- **MVP Status:** **Required.**

### 2.2 Backend API (Gateway & Routing)
- **Responsibility:** Exposes typed REST and WebSocket endpoints, manages HTTP request lifecycles, and enforces observability tracing.
- **Inputs:** Inbound HTTP requests and WebSocket connections.
- **Outputs:** JSON responses, HTTP error codes (400, 401, 403, 404, 422, 500), WebSocket frame streams.
- **Dependencies:** All application services, Core Logging, Observability Middleware.
- **Business Rules Owned:** HTTP protocol conformance, content negotiation, request correlation ID generation.
- **Data Reads:** None directly (delegates to services).
- **Data Modifies:** None directly.
- **Failure Behavior:** Returns structured JSON RFC-7807 error responses; catches unhandled exceptions to prevent process crash.
- **MVP Status:** **Required.**

### 2.3 Authentication and Authorization
- **Responsibility:** Validates caller identity, verifies HMAC webhook signatures, and enforces Role-Based Access Control (Admin, Operator, Read-Only, Service).
- **Inputs:** `Authorization: Bearer <token>` headers, `X-Signature-SHA256` webhook headers.
- **Outputs:** Authenticated `ActorContext` (user ID, roles, permissions) or HTTP 401/403.
- **Dependencies:** Cryptographic libraries (`hmac`, `hashlib`), Core Config.
- **Business Rules Owned:** BR-004 (Webhook signature verification), BR-025 (Operator permission hierarchy).
- **Data Reads:** Provider webhook secrets, user role mappings.
- **Data Modifies:** None.
- **Failure Behavior:** Rejects untrusted callers immediately with HTTP 401 Unauthorized or HTTP 403 Forbidden.
- **MVP Status:** **Required (Mocked/Header-based for local MVP; strict HMAC for webhooks).**

### 2.4 Event Ingestion
- **Responsibility:** Serves as the raw entry point for synthetic or external payment event notifications.
- **Inputs:** Raw JSON payloads from payment providers.
- **Outputs:** Parsed internal event envelopes.
- **Dependencies:** Payment Event Validator, Duplicate Event Detector.
- **Business Rules Owned:** BR-001 (Raw event capture), BR-002 (Ingress latency < 50ms).
- **Data Reads:** None.
- **Data Modifies:** Inserts raw event into `provider_webhook_events`.
- **Failure Behavior:** Returns HTTP 400 on malformed transport; logs security alert if payload exceeds size limit (1MB).
- **MVP Status:** **Required.**

### 2.5 Payment Event Validator
- **Responsibility:** Validates that incoming payment events conform to exact structural, monetary, and currency schemas.
- **Inputs:** Ingested event dictionary.
- **Outputs:** Typed, validated `PaymentEvent` domain schema.
- **Dependencies:** Pydantic v2 domain schemas.
- **Business Rules Owned:** BR-003 (Non-negative minor unit check: `amount_minor >= 0`), BR-005 (ISO-4217 uppercase 3-character currency check).
- **Data Reads:** None.
- **Data Modifies:** None.
- **Failure Behavior:** Raises typed `ValidationError`; returns HTTP 422 Unprocessable Entity.
- **MVP Status:** **Required.**

### 2.6 Duplicate Event Detector (Idempotency Engine)
- **Responsibility:** Guarantees that duplicate webhook deliveries or replayed requests are identified and handled idempotently without re-triggering workflows.
- **Inputs:** Provider name, external event ID, payload SHA-256 hash.
- **Outputs:** Deduplication verdict (`NEW_EVENT`, `DUPLICATE_PROCESSED`, `DUPLICATE_IN_PROGRESS`).
- **Dependencies:** `ProviderWebhookEventRepository`, Database Layer.
- **Business Rules Owned:** BR-006 (7-day deduplication window), INV-006 (Idempotent processing).
- **Data Reads:** `provider_webhook_events` by `(provider, external_event_id)`.
- **Data Modifies:** Inserts new event record or updates processed status.
- **Failure Behavior:** On database lock contention, safely retries lookup; drops duplicate with HTTP 200/202 to satisfy provider retry loops.
- **MVP Status:** **Required.**

### 2.7 Risk Assessment Engine
- **Responsibility:** Evaluates validated payment events to determine if revenue is actively at risk and computes risk urgency and priority.
- **Inputs:** Validated `PaymentEvent`, customer transaction history.
- **Outputs:** `RiskAssessmentResult` (is_at_risk, risk_score, severity, urgency).
- **Dependencies:** Database Layer (customer query).
- **Business Rules Owned:** BR-007 (Failed payment = High Risk), BR-008 (Pending payment > 24h = Stale Risk), BR-009 (Succeeded payment = Zero Risk / Protected).
- **Data Reads:** Customer status, recent transaction statuses.
- **Data Modifies:** None.
- **Failure Behavior:** Fails safe: if risk cannot be calculated, defaults to `RiskLevel.HIGH` to ensure revenue is monitored.
- **MVP Status:** **Required.**

### 2.8 Recovery Eligibility Engine
- **Responsibility:** Assesses whether an at-risk customer account is legally, commercially, and operationally eligible for automated recovery.
- **Inputs:** Customer entity, open recovery case.
- **Outputs:** Eligibility verdict (`ELIGIBLE`, `INELIGIBLE_FROZEN`, `INELIGIBLE_DISPUTED`, `INELIGIBLE_TERMINATED`).
- **Dependencies:** Database Layer.
- **Business Rules Owned:** BR-010 (Frozen/delinquent account protection), BR-011 (Active chargeback/dispute lock), INV-004 (Terminal state immutability).
- **Data Reads:** `customers.status`, `recovery_cases.state`.
- **Data Modifies:** None.
- **Failure Behavior:** Ineligible cases are immediately flagged for human review or marked `TERMINATED`.
- **MVP Status:** **Required.**

### 2.9 Failure Diagnosis Engine
- **Responsibility:** Analyzes payment provider error codes and maps raw error strings into canonical failure classifications.
- **Inputs:** Raw failure code (`insufficient_funds`, `card_expired`, `do_not_honor`, `stolen_card`).
- **Outputs:** `FailureDiagnosis` (category: `SOFT_DECLINE`, `HARD_DECLINE`, `NETWORK_TIMEOUT`, `FRAUD_BLOCK`, retryable: bool).
- **Dependencies:** Canonical Failure Taxonomy.
- **Business Rules Owned:** BR-012 (Soft decline retryability), BR-013 (Hard decline immediate stop).
- **Data Reads:** None.
- **Data Modifies:** None.
- **Failure Behavior:** Unknown error codes are classified as `UNCERTAIN` and marked non-retryable without human review.
- **MVP Status:** **Required.**

### 2.10 AI Recommendation Engine (Agent Brain)
- **Responsibility:** Generates structured recovery recommendations using either a deterministic baseline estimator or an external LLM advisor.
- **Inputs:** Anonymized failure diagnosis, attempt count, customer tenure, transaction amount.
- **Outputs:** Structured `AgentDecision` (action: `RETRY_NOW`, `SCHEDULE_RETRY`, `REQUEST_PAYMENT_METHOD_UPDATE`, `ESCALATE_TO_HUMAN`, `STOP_RECOVERY`; reason_code; confidence; rationale).
- **Dependencies:** `app.agents.contracts`, External LLM Client (optional).
- **Business Rules Owned:** BR-014 (Action proposal schema compliance), BR-015 (Confidence threshold enforcement).
- **Data Reads:** Anonymized case context.
- **Data Modifies:** Inserts unvalidated candidate into `agent_decisions`.
- **Failure Behavior:** On timeout (>3.0s), API error, or schema failure, seamlessly falls back to `deterministic-logistic-v1`.
- **MVP Status:** **Required.**

### 2.11 Deterministic Policy Engine (Safety Gate)
- **Responsibility:** Evaluates proposed agent decisions against strict safety invariants and holds absolute veto authority over financial actions.
- **Inputs:** Proposed `AgentDecision`, Case context, Customer history, Attempt count.
- **Outputs:** Policy verdict (`ALLOWED`, `VETOED_OVERRIDE`, `FORCED_ESCALATE`).
- **Dependencies:** `app.policy.safety`, Safety Invariants (INV-001 through INV-016).
- **Business Rules Owned:** BR-016 (Max 2 retry limit enforcement), BR-017 (24h cooling-off window), INV-001 (Supremacy), INV-002 (Bounded retries), INV-003 (Customer blocklist).
- **Data Reads:** `recovery_attempts` count, `case.state`.
- **Data Modifies:** Updates `agent_decisions.validation_status` (`VALIDATED` or `OVERRIDDEN_BY_POLICY`).
- **Failure Behavior:** On policy failure or exception, fails safe to `FORCED_ESCALATE` (blocks execution).
- **MVP Status:** **Required.**

### 2.12 Recovery Workflow Engine (State Machine)
- **Responsibility:** Orchestrates the lifecycle of a `RecoveryCase` through valid state transitions in an atomic state machine.
- **Inputs:** Trigger transactions, policy approvals, tool execution results.
- **Outputs:** Case state updates (`DETECTED` -> `ANALYZING` -> `ACTION_SELECTED` -> `ACTION_PENDING` -> `RECOVERED` / `FAILED` / `ESCALATED` / `TERMINATED`).
- **Dependencies:** Database Layer, Audit Service.
- **Business Rules Owned:** BR-018 (Valid state transition matrix), INV-004 (Terminal state cannot be reversed), INV-005 (Monotonic transition numbering).
- **Data Reads:** `recovery_cases`, `case_state_transitions`.
- **Data Modifies:** Updates `recovery_cases.state`, inserts `case_state_transitions`.
- **Failure Behavior:** Invalid transitions raise `InvalidStateTransitionError` and roll back the database transaction.
- **MVP Status:** **Required.**

### 2.13 Retry Scheduler
- **Responsibility:** Calculates deterministic exponential backoff intervals with jitter for soft decline retries.
- **Inputs:** Attempt count, failure category.
- **Outputs:** `scheduled_at` timestamp.
- **Dependencies:** Core Time Provider.
- **Business Rules Owned:** BR-019 (Exponential backoff: Base 4h, max 24h), BR-020 (Daylight hours scheduling preference).
- **Data Reads:** None.
- **Data Modifies:** Sets `recovery_attempts.scheduled_at`.
- **Failure Behavior:** Defaults to fixed 12-hour retry delay on calculation error.
- **MVP Status:** **Required.**

### 2.14 Payment Provider Simulator
- **Responsibility:** Emulates external card network and gateway behaviors with deterministic outcomes and injected fault modes.
- **Inputs:** Charge request (amount, currency, idempotency_key).
- **Outputs:** Simulated response (`status: succeeded | failed | uncertain`, `charge_id`, `error_code`).
- **Dependencies:** Seeded Random Engine (Seed 42).
- **Business Rules Owned:** BR-021 (Deterministic scenario seeding), BR-022 (Idempotent response caching).
- **Data Reads:** Idempotency store.
- **Data Modifies:** In-memory or database provider logs.
- **Failure Behavior:** Simulates 504 timeouts, 429 rate limits, and network connection drops for resilience testing.
- **MVP Status:** **Required.**

### 2.15 Outcome Verification Service
- **Responsibility:** Verifies that a reported payment success legitimately matches a specific failed transaction within a strict attribution window before declaring recovery.
- **Inputs:** Successful transaction event, original failed transaction ID, case context.
- **Outputs:** Attribution verdict (`VERIFIED_ATTRIBUTED`, `REJECTED_UNMATCHED`, `REJECTED_WINDOW_EXPIRED`).
- **Dependencies:** Database Layer.
- **Business Rules Owned:** BR-023 (72-hour attribution window), INV-007 (Verified evidence requirement: exact amount, matching customer).
- **Data Reads:** `transactions`, `recovery_cases`.
- **Data Modifies:** Inserts record into `recovery_evidence`.
- **Failure Behavior:** If evidence cannot be verified with 100% certainty, recovery is denied and the case is marked `VERIFICATION_PENDING`.
- **MVP Status:** **Required.**

### 2.16 Audit Service
- **Responsibility:** Records an immutable, append-only chronological log of every action, state transition, and decision.
- **Inputs:** Audit payload (case_id, event_type, actor, from_state, to_state, correlation_id).
- **Outputs:** Persisted audit record.
- **Dependencies:** Database Layer.
- **Business Rules Owned:** BR-024 (Strictly increasing monotonic sequence numbers per case), INV-005 (Audit immutability).
- **Data Reads:** Latest sequence number for case.
- **Data Modifies:** Inserts into `audit_events`.
- **Failure Behavior:** If the audit write fails, the entire surrounding database transaction is rolled back.
- **MVP Status:** **Required.**

### 2.17 Analytics and Evaluation Service
- **Responsibility:** Aggregates recovery metrics across batches, computes recovery rates, and produces reproducible evaluation benchmarks.
- **Inputs:** Evaluation batch configurations (scenario count: 500, seed: 42).
- **Outputs:** Batch metrics (recovered revenue, at-risk revenue, recovery rate, safety rate, action accuracy).
- **Dependencies:** All Core Engines, Database Layer.
- **Business Rules Owned:** BR-026 (Revenue recovery rate calculation), BR-027 (Safety rate: 100% policy compliance).
- **Data Reads:** All domain tables.
- **Data Modifies:** None (read-only calculation).
- **Failure Behavior:** Returns zero-safe metrics if no data matches; logs calculation warnings.
- **MVP Status:** **Required.**

### 2.18 Database & Persistence Layer
- **Responsibility:** Manages relational connections, enforces table-level constraints, and guarantees ACID transaction boundaries.
- **Inputs:** SQLAlchemy 2.0 ORM operations.
- **Outputs:** Persisted rows, query result sets.
- **Dependencies:** PostgreSQL 16 / SQLite 3 engine, psycopg driver.
- **Business Rules Owned:** Database constraints (`amount_minor >= 0`, `currency = upper(currency)`, foreign key referential integrity).
- **Data Reads:** All persistent entities.
- **Data Modifies:** All persistent entities.
- **Failure Behavior:** On constraint violation or deadlock, rolls back transaction and raises typed exception.
- **MVP Status:** **Required.**

---

## 3. Component Responsibility Matrix

| Module Name | Primary Responsibility | Primary Input | Primary Output | Database Writes | MVP Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Frontend App** | Dark neon fintech dashboard & queue | User interactions, API responses | UI views, Actions | None | Required |
| **Backend API Gateway** | Routing, HTTP serialization, CORS | HTTP & WebSocket traffic | JSON / WS frames | None | Required |
| **Auth & Authorization** | Security validation, HMAC checks | Headers & Signature tokens | Validated `ActorContext` | None | Required |
| **Event Ingestion** | Raw webhook receipt & payload logging | Raw Provider Webhook JSON | Ingestion envelope | `provider_webhook_events` | Required |
| **Event Validator** | Schema & data type validation | Ingestion envelope | Validated `PaymentEvent` | None | Required |
| **Duplicate Detector** | Idempotency & replay protection | `(provider, event_id)` | Deduplication verdict | `provider_webhook_events` | Required |
| **Risk Engine** | Identifies at-risk revenue & severity | `PaymentEvent` | `RiskAssessmentResult` | None | Required |
| **Eligibility Engine** | Evaluates customer account eligibility| Customer status & Case | Eligibility verdict | None | Required |
| **Diagnosis Engine** | Classifies failure codes (soft vs hard)| Provider error code | `FailureDiagnosis` | None | Required |
| **AI Recommendation** | Proposes structured recovery action | Anonymized case context | Candidate `AgentDecision` | `agent_decisions` | Required |
| **Policy Engine** | Enforces safety invariants (INV-001..16)| Candidate `AgentDecision` | Validated or Vetoed Action | `agent_decisions` | Required |
| **Workflow Engine** | FSM case state management | Validated actions & triggers | State transition | `recovery_cases`, `transitions` | Required |
| **Retry Scheduler** | Exponential backoff calculation | Attempt count & failure type | `scheduled_at` timestamp | `recovery_attempts` | Required |
| **Payment Simulator** | Emulates banking rails & error modes | Charge request | Simulated charge outcome | Simulator logs | Required |
| **Verification Service**| Proves legitimate recovery (<72h) | Succeeded transaction | Attribution verdict | `recovery_evidence` | Required |
| **Audit Service** | Append-only tamper-proof ledger | State & action events | Sequenced audit record | `audit_events` | Required |
| **Analytics & Eval** | Batch metrics (500 scenarios, Seed 42)| Batch run requests | Recovery & Safety metrics | Evaluation reports | Required |
| **Database Layer** | ACID transactions & constraint checks | ORM models | Persisted relational data| All tables | Required |
