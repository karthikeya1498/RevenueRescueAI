# RevenueRescueAI — API System Communication Sequence Diagrams
## Phase 1.3: End-to-End Interaction Models, Component Handshakes, and Failure Recovery

**Document Version:** 1.0.0  
**Status:** Approved Sequence Models  
**Primary Authors:** Senior Backend Architect, API Designer, Systems Engineer  

---

## 1. Flow 1: Inbound Payment Failure to Recovery Recommendation

This sequence traces an incoming failed payment webhook as it is authenticated, deduplicated, evaluated for revenue risk, diagnosed, and converted into a validated AI recommendation.

```mermaid
sequenceDiagram
    autonumber
    actor Provider as Payment Simulator / Gateway
    participant API as Ingress Gateway (FastAPI)
    participant Dedup as Deduplication Engine
    participant DB as Relational Database
    participant Risk as Risk Assessment Engine
    participant Agent as AI Recommendation Engine
    participant Policy as Deterministic Policy Gate
    participant WS as Realtime WebSocket Stream
    actor Operator as Dashboard UI (React 19)

    Provider->>API: POST /api/v1/webhooks/provider (HMAC Signature Header)
    Note over API: Verifies HMAC-SHA256 signature and 5-min timestamp window
    API->>Dedup: Check duplicate (provider, external_event_id)
    Dedup->>DB: Query provider_webhook_events
    DB-->>Dedup: Not found (New Event)
    Dedup->>DB: INSERT INTO provider_webhook_events (processed=FALSE)
    
    API->>Risk: Evaluate Payment Event (amount_minor: 842000, code: 'insufficient_funds')
    Risk-->>API: Result: is_at_risk=TRUE, severity=HIGH, tier=SOFT_DECLINE
    
    API->>DB: INSERT INTO transactions (status='failed', failure_code='insufficient_funds')
    API->>DB: INSERT INTO recovery_cases (state='DETECTED', priority=100)
    API->>DB: INSERT INTO case_state_transitions (from=NULL, to='DETECTED', seq=1)
    API->>DB: INSERT INTO audit_events (event_type='CASE_DETECTED', seq=1)
    
    API->>Agent: Request Recommendation (failure: 'insufficient_funds', attempts: 0)
    Agent-->>Policy: Propose Decision: RETRY_NOW (confidence: 0.94)
    
    Note over Policy: Evaluating Invariants: INV-001, INV-002 (budget < 2), INV-003
    Policy->>DB: INSERT INTO agent_decisions (action='retry_now', status='VALIDATED')
    Policy-->>API: Authorized: RETRY_NOW
    
    API->>DB: UPDATE recovery_cases SET state='ACTION_SELECTED'
    API->>DB: INSERT INTO case_state_transitions (from='DETECTED', to='ACTION_SELECTED', seq=2)
    
    API->>WS: Broadcast event: recovery.risk_signal (case_id, amount_minor: 842000)
    WS-->>Operator: Live Update: Case appears in Recovery Queue
    API-->>Provider: HTTP 202 Accepted (event_id: 'evt_sim_99812')
```

### Flow 1 Failure & Decision Summary:
- **Initiator:** External Gateway / Payment Simulator.
- **Decision Makers:** 
  1. `PaymentEventValidator` (decides structural validity).
  2. `RiskAssessmentEngine` (decides if revenue is at risk).
  3. `DeterministicPolicyGate` (authorizes action feasibility).
- **Storage:** Persisted in `provider_webhook_events`, `transactions`, `recovery_cases`, `agent_decisions`, and `audit_events`.
- **Failure Recovery:** If signature fails $\to$ HTTP 401. If duplicate $\to$ cached HTTP 200 returned. If AI times out $\to$ falls back to `deterministic-logistic-v1`.

---

## 2. Flow 2: Recommendation to Recovery Action Execution

This sequence models an operator triggering an approved recovery retry from the Command Center, verifying policy rules, executing against the provider simulator, and updating the audit log.

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Dashboard UI (React 19)
    participant API as Backend API Gateway
    participant Policy as Deterministic Policy Gate
    participant Tool as Bounded Tool Executor
    participant DB as Relational Database
    participant Sim as Payment Provider Simulator
    participant Verify as Verification Service
    participant WS as Realtime WebSocket Stream

    Operator->>API: POST /api/v1/cases/{id}/actions/retry (Header: Idempotency-Key)
    API->>DB: SELECT * FROM recovery_cases WHERE id = :id FOR UPDATE
    DB-->>API: Return Case (state='ACTION_SELECTED', version=1)
    
    API->>Policy: Validate Action against Invariants (attempts < 2, not terminal)
    Policy-->>API: Verdict: ALLOWED (Attempt 1 of 2)
    
    API->>DB: INSERT INTO recovery_attempts (seq=1, status='STARTED', key=Idempotency-Key)
    API->>DB: UPDATE recovery_cases SET state='ACTION_PENDING', version=2
    API->>DB: INSERT INTO case_state_transitions (from='ACTION_SELECTED', to='ACTION_PENDING', seq=3)
    API->>DB: COMMIT TRANSACTION; -- Release database lock!
    
    API->>Tool: Dispatch retry_payment (amount: 842000, key: Idempotency-Key)
    Tool->>Sim: POST /v1/charges (amount: 842000, currency: 'USD')
    Sim-->>Tool: HTTP 200 OK (status: 'succeeded', charge_id: 'ch_sim_8F31_01')
    
    Tool->>DB: BEGIN TRANSACTION;
    Tool->>DB: UPDATE recovery_attempts SET status='SUCCEEDED', provider_reference='ch_sim_8F31_01'
    Tool->>Verify: Submit Evidence for Verification
    Verify->>Verify: Verify match (amount: 842000, customer match, <72h)
    Verify->>DB: INSERT INTO recovery_evidence (attributable=TRUE, amount_minor=842000)
    
    Tool->>DB: UPDATE recovery_cases SET state='RECOVERED', closed_at=NOW(), version=3
    Tool->>DB: INSERT INTO case_state_transitions (from='ACTION_PENDING', to='RECOVERED', seq=4)
    Tool->>DB: INSERT INTO audit_events (event_type='CASE_RECOVERED', seq=4)
    Tool->>DB: COMMIT TRANSACTION;
    
    API->>WS: Broadcast event: recovery.payment_recovered ($8,420.00)
    WS-->>Operator: Live Notification: Case marked RECOVERED
    API-->>Operator: HTTP 200 OK (state: 'recovered', recovered_minor: 842000)
```

---

## 3. Flow 3: Uncertain Recovery Outcome (HTTP 504 Timeout)

This sequence illustrates how the system prevents double-charging when an external gateway times out, transitions the case to `VERIFICATION_PENDING`, and safely resolves the transaction.

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Dashboard UI (React 19)
    participant API as Backend API Gateway
    participant Tool as Bounded Tool Executor
    participant DB as Relational Database
    participant Sim as Payment Provider Simulator
    participant Verify as Verification Service
    actor Daemon as Status Inquiry Worker

    Operator->>API: POST /api/v1/cases/{id}/actions/retry (Idempotency-Key: idemp_01)
    API->>DB: Record attempt status='STARTED' (seq=1)
    API->>Tool: Dispatch charge to Simulator
    
    Tool->>Sim: POST /v1/charges (idemp_01)
    Note over Tool,Sim: Network Drop / Simulator Injects HTTP 504 Gateway Timeout
    Sim--xTool: HTTP 504 Gateway Timeout (No Body)
    
    Note over Tool: UNCERTAIN OUTCOME! Invariant INV-008: DO NOT RETRY BLINDLY!
    Tool->>DB: UPDATE recovery_attempts SET status='UNCERTAIN', error_class='HTTP_504'
    Tool->>DB: UPDATE recovery_cases SET state='VERIFICATION_PENDING'
    Tool->>DB: INSERT INTO audit_events (event_type='OUTCOME_UNCERTAIN_TIMEOUT')
    
    API-->>Operator: HTTP 504 Gateway Timeout (state: 'verification_pending')
    Note over Operator: UI shows amber "Verification Pending" banner
    
    Note over Daemon: Background worker initiates delayed verification inquiry
    Daemon->>Sim: GET /v1/charges?idempotency_key=idemp_01
    Sim-->>Daemon: Return Settled Status: 'succeeded' (charge_id: 'ch_sim_delayed_01')
    
    Daemon->>Verify: Submit Evidence (charge_id, amount_minor: 842000)
    Verify->>DB: INSERT INTO recovery_evidence (attributable=TRUE)
    Daemon->>DB: UPDATE recovery_cases SET state='RECOVERED', closed_at=NOW()
    Daemon->>DB: INSERT INTO audit_events (event_type='DELAYED_VERIFICATION_SUCCEEDED')
    Note over DB: Case cleanly settled. Zero duplicate charges executed.
```

---

## 4. Flow 4: Dashboard Loading & Authoritative KPI Computation

This sequence illustrates how the React dashboard retrieves authoritative financial metrics without performing client-side math.

```mermaid
sequenceDiagram
    autonumber
    actor Operator as Fintech Operator
    participant UI as React 19 Dashboard
    participant API as Dashboard API Gateway
    participant Service as Analytics Service
    participant DB as Relational Database

    Operator->>UI: Navigates to Command Center (/overview)
    UI->>API: GET /api/v1/dashboard/metrics?currency=USD&time_range=all_time
    
    API->>Service: Compute KPIs for Currency 'USD'
    Service->>DB: SELECT SUM(amount_minor) FROM recovery_evidence WHERE attributable = TRUE AND currency = 'USD'
    DB-->>Service: recovered_revenue_minor = 98088700 ($980,887.00)
    
    Service->>DB: SELECT SUM(amount_minor) FROM transactions WHERE id IN (SELECT trigger_transaction_id FROM recovery_cases WHERE state IN ('detected', 'action_pending', 'recovered', 'escalated'))
    DB-->>Service: at_risk_revenue_minor = 216320000 ($2,163,200.00)
    
    Service->>Service: Compute Rates in Integer Math: (98088700 / 216320000) = 45.34%
    Service->>DB: SELECT count(*) FROM recovery_cases GROUP BY state
    DB-->>Service: total=400, recovered=182, escalated=90, pending=91, stopped=46
    
    Service-->>API: Return Typed Metrics Payload
    API-->>UI: HTTP 200 OK (recovered: $980.9k, at_risk: $2.16m, rate: '45.34%')
    
    UI->>API: GET /api/v1/dashboard/trend?currency=USD&interval=day
    API->>DB: Query aggregated daily sums from recovery_evidence
    DB-->>API: Return 5 chronological bucket points
    API-->>UI: HTTP 200 OK (points array)
    
    Note over UI: Renders symmetrical 152px KPI cards and SVG trendline
```
