# RevenueRescueAI — Complete API Endpoint Catalogue
## Phase 1.3: Comprehensive Route Specifications, Contracts, and Realistic Payloads

**Document Version:** 1.0.0  
**Status:** Approved Endpoint Catalogue  
**Primary Authors:** Senior Backend Architect, API Designer, Security Engineer  

---

## 1. Summary of Approved MVP Endpoints

The RevenueRescueAI MVP defines **17 approved API endpoints** grouped into 9 functional areas:

```
+-----------------------------------------------------------------------------------------------+
|                                      ENDPOINT SUMMARY MATRIX                                  |
+--------------------------+--------+------------------------------------+----------------------+
| Functional Group         | Method | URI Path                           | Primary Actor Role   |
+--------------------------+--------+------------------------------------+----------------------+
| 1. System Health         | GET    | `/health`                          | Public / Automated   |
|                          | GET    | `/ready`                           | Public / Automated   |
+--------------------------+--------+------------------------------------+----------------------+
| 2. Dashboard Analytics   | GET    | `/api/v1/dashboard/metrics`        | `ROLE_OPERATOR`      |
|                          | GET    | `/api/v1/dashboard/trend`          | `ROLE_OPERATOR`      |
+--------------------------+--------+------------------------------------+----------------------+
| 3. Recovery Cases        | GET    | `/api/v1/cases`                    | `ROLE_OPERATOR`      |
|                          | GET    | `/api/v1/cases/{case_id}`          | `ROLE_OPERATOR`      |
|                          | GET    | `/api/v1/cases/{case_id}/timeline` | `ROLE_OPERATOR`      |
+--------------------------+--------+------------------------------------+----------------------+
| 4. Payment Ingress       | POST   | `/api/v1/webhooks/provider`        | `ROLE_INGESTOR` (HMAC)|
|                          | POST   | `/api/v1/events/simulate-failure`  | `ROLE_OPERATOR`      |
+--------------------------+--------+------------------------------------+----------------------+
| 5. AI Recommendations    | POST   | `/api/v1/recovery/decision-preview`| `ROLE_OPERATOR`      |
|                          | POST   | `/api/v1/cases/{case_id}/recommend`| `ROLE_OPERATOR`      |
+--------------------------+--------+------------------------------------+----------------------+
| 6. Policy Governance     | POST   | `/api/v1/cases/{case_id}/validate` | `ROLE_OPERATOR`      |
+--------------------------+--------+------------------------------------+----------------------+
| 7. Recovery Actions      | POST   | `/api/v1/cases/{case_id}/actions/retry`| `ROLE_OPERATOR`  |
|                          | POST   | `/api/v1/cases/{case_id}/actions/escalate`| `ROLE_OPERATOR`|
|                          | POST   | `/api/v1/cases/{case_id}/actions/stop`| `ROLE_OPERATOR`   |
+--------------------------+--------+------------------------------------+----------------------+
| 8. Audit & Evidence      | GET    | `/api/v1/cases/{case_id}/audit-trail`| `ROLE_AUDITOR`     |
|                          | POST   | `/api/v1/verification/verify-evidence`| `ROLE_INGESTOR`    |
+--------------------------+--------+------------------------------------+----------------------+
| 9. Evaluation & Stream   | POST   | `/api/v1/evaluation/run`           | `ROLE_ADMIN`         |
|                          | GET    | `/api/v1/evaluation/results/{run_id}`| `ROLE_OPERATOR`    |
|                          | GET    | `/api/v1/ws/realtime`              | `ROLE_OPERATOR`      |
+--------------------------+--------+------------------------------------+----------------------+
```

---

## 2. Detailed Endpoint Specifications

### 2.1 System Health Endpoints

#### Endpoint 1: Service Liveness Probe
- **Name:** Check Service Liveness
- **Method:** `GET`
- **Path:** `/health`
- **Purpose:** Verifies whether the ASGI web process is running.
- **Authentication:** None (Public).
- **Headers:** None.
- **Response Schema:**
  ```json
  {
    "status": "healthy",
    "service": "RevenueRescue AI",
    "phase": "mvp-evaluation"
  }
  ```
- **HTTP Status Codes:** `200 OK`.
- **Database Side Effects / State Changes / Audit Events:** None.

---

#### Endpoint 2: Dependency Readiness Probe
- **Name:** Check Dependency Readiness
- **Method:** `GET`
- **Path:** `/ready`
- **Purpose:** Verifies database pool connectivity without side effects.
- **Authentication:** None (Public).
- **Response Schema:**
  ```json
  {
    "status": "ready",
    "service": "RevenueRescue AI",
    "environment": "development",
    "dependencies": {
      "configuration": "ready",
      "database": "ready",
      "simulator": "ready"
    }
  }
  ```
- **HTTP Status Codes:** `200 OK`, `503 Service Unavailable`.
- **Database Side Effects / State Changes / Audit Events:** None.

---

### 2.2 Dashboard Analytics Endpoints

#### Endpoint 3: Recovered & At-Risk Metrics Summary
- **Name:** Retrieve Dashboard Metrics
- **Method:** `GET`
- **Path:** `/api/v1/dashboard/metrics`
- **Purpose:** Supplies authoritative financial KPIs to the Command Center.
- **Authentication:** Bearer Token (`ROLE_OPERATOR`, `ROLE_ADMIN`, `ROLE_AUDITOR`).
- **Query Parameters:**
  - `currency` (String, Optional, Default: `'USD'`): Filter by currency.
  - `time_range` (String, Optional, Default: `'all_time'`): `'today'`, `'last_7_days'`, `'last_30_days'`, `'all_time'`.
- **Response Schema (200 OK):**
  ```json
  {
    "currency": "USD",
    "time_range": "all_time",
    "at_risk_revenue_minor": 216320000,
    "recovered_revenue_minor": 98088700,
    "recovery_rate_pct": "45.34%",
    "case_recovery_rate_pct": "45.50%",
    "total_at_risk_cases": 400,
    "total_recovered_cases": 182,
    "escalated_cases": 90,
    "verification_pending_cases": 91,
    "stopped_cases": 46,
    "safety_rate_pct": "100.00%",
    "generated_at": "2026-10-30T12:04:11.000Z"
  }
  ```
- **HTTP Status Codes:** `200 OK`, `401 Unauthorized`.
- **Security Considerations:** The frontend never calculates revenue recovery totals; values are computed authoritatively on the backend using integer minor units.

---

#### Endpoint 4: Recovered Revenue Trend Time Series
- **Name:** Retrieve Revenue Trend Time Series
- **Method:** `GET`
- **Path:** `/api/v1/dashboard/trend`
- **Purpose:** Delivers chronological time-bucketed points to render the dashboard SVG trend curve.
- **Authentication:** Bearer Token (`ROLE_OPERATOR`).
- **Query Parameters:**
  - `currency` (String, Optional, Default: `'USD'`)
  - `interval` (String, Optional, Default: `'day'`): `'hour'`, `'day'`, `'week'`.
- **Response Schema (200 OK):**
  ```json
  {
    "currency": "USD",
    "interval": "day",
    "points": [
      { "timestamp": "2026-10-01T00:00:00Z", "recovered_minor": 1248000, "at_risk_minor": 2500000 },
      { "timestamp": "2026-10-08T00:00:00Z", "recovered_minor": 2840000, "at_risk_minor": 5100000 },
      { "timestamp": "2026-10-15T00:00:00Z", "recovered_minor": 5910000, "at_risk_minor": 11200000 },
      { "timestamp": "2026-10-22T00:00:00Z", "recovered_minor": 7820000, "at_risk_minor": 16400000 },
      { "timestamp": "2026-10-29T00:00:00Z", "recovered_minor": 9808870, "at_risk_minor": 21632000 }
    ]
  }
  ```

---

### 2.3 Recovery Cases Endpoints

#### Endpoint 5: List Recovery Cases
- **Name:** List Recovery Cases
- **Method:** `GET`
- **Path:** `/api/v1/cases`
- **Purpose:** Returns a paginated, filtered recovery queue for operator inspection.
- **Authentication:** Bearer Token (`ROLE_OPERATOR`, `ROLE_ADMIN`).
- **Query Parameters:**
  - `state` (String, Optional): Filter by state (`detected`, `action_pending`, `escalated`, `verification_pending`, `recovered`).
  - `risk_level` (String, Optional): `high`, `medium`, `low`.
  - `search` (String, Optional): Search string across customer name and case key.
  - `limit` (Integer, Default: `20`, Max: `100`).
  - `offset` (Integer, Default: `0`).
  - `sort` (String, Default: `'last_state_changed_at:desc'`).
- **Response Schema (200 OK):**
  ```json
  {
    "items": [
      {
        "id": "f7a28190-8812-4c22-b912-334455667788",
        "case_key": "case_sim_8F31A_01",
        "customer": {
          "id": "e9f8a3c1-4b72-4d9a-9e11-8201bfa82a10",
          "display_name": "Northstar Labs",
          "status": "active"
        },
        "trigger_transaction": {
          "id": "c4b19280-3e21-4f11-9a72-1084bce19401",
          "external_id": "txn_sim_8F31A",
          "amount_minor": 842000,
          "currency": "USD",
          "failure_code": "insufficient_funds"
        },
        "state": "action_pending",
        "priority": 100,
        "attempts_count": 1,
        "opened_at": "2026-10-30T12:04:12.000Z",
        "last_state_changed_at": "2026-10-30T12:04:14.000Z"
      }
    ],
    "pagination": {
      "total": 400,
      "limit": 20,
      "offset": 0,
      "has_more": true
    }
  }
  ```

---

#### Endpoint 6: Retrieve Recovery Case Details
- **Name:** Retrieve Recovery Case Details
- **Method:** `GET`
- **Path:** `/api/v1/cases/{case_id}`
- **Path Parameters:** `case_id` (UUIDv4).
- **Purpose:** Fetches full case details, trigger transactions, attempt histories, and decisions.
- **Response Schema (200 OK):**
  ```json
  {
    "id": "f7a28190-8812-4c22-b912-334455667788",
    "case_key": "case_sim_8F31A_01",
    "customer": {
      "id": "e9f8a3c1-4b72-4d9a-9e11-8201bfa82a10",
      "external_id": "cus_sim_9A12F",
      "display_name": "Northstar Labs",
      "email": "alex.m***@northstar.io",
      "status": "active"
    },
    "trigger_transaction": {
      "id": "c4b19280-3e21-4f11-9a72-1084bce19401",
      "external_id": "txn_sim_8F31A",
      "amount_minor": 842000,
      "currency": "USD",
      "failure_code": "insufficient_funds",
      "failure_message_safe": "Card has insufficient funds.",
      "occurred_at": "2026-10-30T12:04:11.000Z"
    },
    "state": "action_pending",
    "priority": 100,
    "version": 2,
    "attempts": [
      {
        "id": "11223344-5566-7788-99aa-bbccddeeff00",
        "sequence_number": 1,
        "action_type": "retry_now",
        "status": "succeeded",
        "provider_reference": "ch_sim_8F31_01",
        "started_at": "2026-10-30T12:04:14.100Z",
        "finished_at": "2026-10-30T12:04:18.400Z"
      }
    ],
    "latest_decision": {
      "action_type": "retry_now",
      "reason_code": "soft_decline_retry_eligible",
      "confidence": "0.940",
      "rationale_safe": "Soft decline on active account; retry allowed.",
      "validation_status": "validated"
    },
    "opened_at": "2026-10-30T12:04:12.000Z",
    "last_state_changed_at": "2026-10-30T12:04:18.000Z",
    "closed_at": null
  }
  ```
- **Error Codes:** `404 RESOURCE_NOT_FOUND` if `case_id` does not exist.

---

#### Endpoint 7: Retrieve Case Timeline Transitions
- **Name:** Retrieve Case Timeline Transitions
- **Method:** `GET`
- **Path:** `/api/v1/cases/{case_id}/timeline`
- **Purpose:** Supplies the sequence of FSM state transitions to render the visual "Agent Journey".
- **Response Schema (200 OK):**
  ```json
  {
    "case_id": "f7a28190-8812-4c22-b912-334455667788",
    "transitions": [
      {
        "sequence_number": 1,
        "from_state": null,
        "to_state": "detected",
        "reason_code": "initial_payment_failure_ingested",
        "actor_type": "system",
        "occurred_at": "2026-10-30T12:04:12.000Z"
      },
      {
        "sequence_number": 2,
        "from_state": "detected",
        "to_state": "analyzing",
        "reason_code": "diagnosis_initiated",
        "actor_type": "system",
        "occurred_at": "2026-10-30T12:04:13.000Z"
      },
      {
        "sequence_number": 3,
        "from_state": "analyzing",
        "to_state": "action_selected",
        "reason_code": "policy_approved_retry",
        "actor_type": "agent_policy",
        "occurred_at": "2026-10-30T12:04:14.000Z"
      }
    ]
  }
  ```

---

### 2.4 Payment Event Ingress & Simulation Endpoints

#### Endpoint 8: Provider Webhook Ingress
- **Name:** Ingest Provider Webhook Event
- **Method:** `POST`
- **Path:** `/api/v1/webhooks/provider`
- **Purpose:** Idempotently receives and processes external or simulated payment webhook notifications.
- **Authentication:** HMAC Signature Check (`X-Signature-SHA256`).
- **Required Headers:**
  - `X-Signature-SHA256`: Hexadecimal HMAC digest.
  - `X-Event-ID`: Provider's unique event string.
- **Request Body (JSON):**
  ```json
  {
    "id": "evt_sim_99812",
    "type": "payment_intent.payment_failed",
    "created": 1730289851,
    "data": {
      "object": {
        "id": "txn_sim_8F31A",
        "customer": "cus_sim_9A12F",
        "amount": 842000,
        "currency": "usd",
        "status": "failed",
        "last_payment_error": {
          "code": "insufficient_funds",
          "message": "The card has insufficient funds to complete the purchase."
        }
      }
    }
  }
  ```
- **Response Schema (200 OK / 202 Accepted):**
  ```json
  {
    "accepted": true,
    "duplicate": false,
    "event_id": "evt_sim_99812",
    "event_type": "payment_intent.payment_failed",
    "reason": "event_ingested_and_dispatched",
    "verified": true
  }
  ```
- **Duplicate Behavior:** If identical `(provider, event_id)` arrives again, returns `200 OK` with `"duplicate": true` and drops duplicate side effects.

---

#### Endpoint 9: Simulate Synthetic Payment Failure
- **Name:** Simulate Synthetic Payment Failure
- **Method:** `POST`
- **Path:** `/api/v1/events/simulate-failure`
- **Purpose:** Generates a synthetic payment failure event for demonstration and interactive testing.
- **Authentication:** Bearer Token (`ROLE_OPERATOR`).
- **Request Body (JSON):**
  ```json
  {
    "customer_id": "cus_sim_9A12F",
    "amount_minor": 842000,
    "currency": "USD",
    "failure_code": "insufficient_funds",
    "failure_message": "Card has insufficient funds."
  }
  ```
- **Response Schema (201 Created):**
  ```json
  {
    "case_id": "f7a28190-8812-4c22-b912-334455667788",
    "case_key": "case_sim_8F31A_01",
    "transaction_id": "c4b19280-3e21-4f11-9a72-1084bce19401",
    "state": "detected",
    "message": "Synthetic payment failure created and recovery case opened."
  }
  ```

---

### 2.5 AI Recommendation & Reasoning Endpoints

#### Endpoint 10: Stateless Decision Preview
- **Name:** Preview Recovery Decision
- **Method:** `POST`
- **Path:** `/api/v1/recovery/decision-preview`
- **Purpose:** Returns a transparent recommendation and mathematical feature score without executing any side effects.
- **Authentication:** Bearer Token (`ROLE_OPERATOR`).
- **Request Body:**
  ```json
  {
    "amount_minor": 842000,
    "currency": "USD",
    "failure_code": "insufficient_funds",
    "failure_message": "Card has insufficient funds.",
    "prior_attempts": 0,
    "customer_success_rate": 0.85,
    "alternate_method_available": true,
    "unusual_velocity": false,
    "customer_restricted": false
  }
  ```
- **Response Schema (200 OK):**
  ```json
  {
    "mode": "decision_preview",
    "currency": "USD",
    "model_version": "deterministic-logistic-v1",
    "policy_authority": "deterministic",
    "failure_classification": {
      "category": "soft_decline",
      "retryable": true,
      "confidence": "0.940",
      "explanation": "Temporary cardholder liquidity shortfall; eligible for scheduled retry."
    },
    "recommendation": {
      "action": "retry_now",
      "confidence": "0.940",
      "rationale": [
        "Failure code classified as soft decline",
        "Zero prior attempts recorded on case",
        "Account has 85% historical settlement rate"
      ]
    }
  }
  ```

---

### 2.6 Recovery Actions & Attempts Endpoints

#### Endpoint 11: Execute Approved Payment Retry
- **Name:** Execute Payment Retry
- **Method:** `POST`
- **Path:** `/api/v1/cases/{case_id}/actions/retry`
- **Purpose:** Executes an authorized retry against the payment simulator using a unique idempotency key.
- **Authentication:** Bearer Token (`ROLE_OPERATOR`).
- **Required Headers:**
  - `Idempotency-Key`: UUIDv4 string (e.g., `idemp_f7a28190_seq1`).
- **Request Body:**
  ```json
  {
    "justification": "Operator manual retry approval following verification of account liquidity."
  }
  ```
- **Response Schema (200 OK):**
  ```json
  {
    "case_id": "f7a28190-8812-4c22-b912-334455667788",
    "attempt_id": "11223344-5566-7788-99aa-bbccddeeff00",
    "sequence_number": 1,
    "action_type": "retry_now",
    "status": "succeeded",
    "case_state": "verification_pending",
    "provider_reference": "ch_sim_8F31_01",
    "message": "Payment retry accepted by provider; awaiting outcome verification."
  }
  ```
- **Error Codes:**
  - `400 RETRY_LIMIT_REACHED`: If `attempt_count >= 2` (Invariant INV-002).
  - `409 CONFLICT`: If case is in terminal state (`RECOVERED`, `FAILED`, `TERMINATED`).
  - `409 IDEMPOTENCY_CONFLICT`: If same key used with conflicting payload.

---

#### Endpoint 12: Escalate Case to Human Queue
- **Name:** Escalate Case
- **Method:** `POST`
- **Path:** `/api/v1/cases/{case_id}/actions/escalate`
- **Purpose:** Moves a case to `ESCALATED` for manual human-in-the-loop review.
- **Request Body:**
  ```json
  {
    "reason_code": "operator_manual_escalation",
    "notes": "Customer requested callback regarding billing change."
  }
  ```
- **Response Schema (200 OK):**
  ```json
  {
    "case_id": "f7a28190-8812-4c22-b912-334455667788",
    "previous_state": "action_pending",
    "new_state": "escalated",
    "escalated_at": "2026-10-30T12:05:00.000Z"
  }
  ```

---

#### Endpoint 13: Stop Recovery (Terminal Lock)
- **Name:** Permanently Stop Recovery
- **Method:** `POST`
- **Path:** `/api/v1/cases/{case_id}/actions/stop`
- **Purpose:** Terminates recovery attempts and permanently locks the case against future actions.
- **Request Body:**
  ```json
  {
    "stop_reason": "cardholder_requested_cancellation",
    "notes": "Subscription cancelled by customer."
  }
  ```
- **Response Schema (200 OK):**
  ```json
  {
    "case_id": "f7a28190-8812-4c22-b912-334455667788",
    "state": "terminated",
    "closed_at": "2026-10-30T12:05:10.000Z",
    "message": "Recovery terminated. Case is locked against future actions."
  }
  ```

---

### 2.7 Audit & Evidence Verification Endpoints

#### Endpoint 14: Retrieve Case Audit Trail
- **Name:** Retrieve Case Audit Trail
- **Method:** `GET`
- **Path:** `/api/v1/cases/{case_id}/audit-trail`
- **Purpose:** Returns the complete, chronologically sequenced audit ledger for compliance.
- **Authentication:** Bearer Token (`ROLE_AUDITOR`, `ROLE_ADMIN`).
- **Response Schema (200 OK):**
  ```json
  {
    "case_id": "f7a28190-8812-4c22-b912-334455667788",
    "total_events": 5,
    "events": [
      {
        "sequence_number": 1,
        "event_type": "CASE_DETECTED",
        "actor_type": "system",
        "actor_id": "ingestor_worker_01",
        "correlation_id": "corr_8f31_4492",
        "event_time": "2026-10-30T12:04:12.000Z",
        "payload_safe": {
          "trigger_transaction": "txn_sim_8F31A",
          "amount_minor": 842000,
          "currency": "USD"
        }
      },
      {
        "sequence_number": 2,
        "event_type": "POLICY_EVALUATION",
        "actor_type": "agent_policy",
        "actor_id": "policy_gate_v1",
        "correlation_id": "corr_8f31_4492",
        "event_time": "2026-10-30T12:04:14.000Z",
        "payload_safe": {
          "action": "retry_now",
          "invariants_checked": ["INV-001", "INV-002", "INV-006"],
          "result": "ALLOWED"
        }
      }
    ]
  }
  ```

---

#### Endpoint 15: Verify Recovery Evidence
- **Name:** Verify Recovery Evidence
- **Method:** `POST`
- **Path:** `/api/v1/verification/verify-evidence`
- **Purpose:** Submits provider payment confirmation to establish legitimate recovery attribution within the 72-hour window.
- **Authentication:** HMAC Signature Check (`ROLE_INGESTOR`).
- **Request Body:**
  ```json
  {
    "intervention_id": "11223344-5566-7788-99aa-bbccddeeff00",
    "provider_event_id": "evt_sim_99815",
    "failed_transaction_id": "txn_sim_8F31A",
    "successful_transaction_id": "txn_sim_8F31B",
    "amount_minor": 842000,
    "currency": "USD"
  }
  ```
- **Response Schema (200 OK):**
  ```json
  {
    "evidence_id": "33445566-7788-99aa-bbcc-ddeeff001122",
    "attributable": true,
    "amount_minor": 842000,
    "currency": "USD",
    "verified_at": "2026-10-30T12:04:18.600Z",
    "case_state": "recovered",
    "message": "Payment verified and attributed to recovery intervention."
  }
  ```

---

### 2.8 Evaluation Lab & Real-Time Endpoints

#### Endpoint 16: Run Evaluation Batch
- **Name:** Run Evaluation Batch
- **Method:** `POST`
- **Path:** `/api/v1/evaluation/run`
- **Purpose:** Triggers a reproducible 500-scenario evaluation run using fixed random seed 42.
- **Authentication:** Bearer Token (`ROLE_ADMIN`).
- **Request Body:**
  ```json
  {
    "scenario_count": 500,
    "random_seed": 42,
    "strategy_version": "phase8.v1"
  }
  ```
- **Response Schema (200 OK):**
  ```json
  {
    "run_id": "eval-run-20261030-0042",
    "status": "completed",
    "duration_ms": 7610,
    "scenarios": 500,
    "at_risk_cases": 400,
    "recovered_cases": 182,
    "at_risk_revenue_minor": 216320000,
    "recovered_revenue_minor": 98088700,
    "revenue_recovery_rate": "45.34%",
    "case_recovery_rate": "45.50%",
    "action_accuracy": "20.00%",
    "safety_rate": "100.00%",
    "failures": 181,
    "escalations": 90,
    "verifications": 91,
    "stopped": 46,
    "is_synthetic": true
  }
  ```

---

#### Endpoint 17: Real-Time Event WebSocket Stream
- **Name:** Real-Time Dashboard Event Stream
- **Protocol:** `WSS` / `WS`
- **Path:** `/api/v1/ws/realtime`
- **Purpose:** Pushes low-latency JSON event frames to the dashboard for live queue, state, and evaluation updates.
- **Authentication:** Token query param (`/ws/realtime?token=<jwt>`).
- **Frame Schema (Outbound JSON):**
  ```json
  {
    "version": 1,
    "id": "evt_stream_10492",
    "occurred_at": "2026-10-30T12:04:18.650Z",
    "event": {
      "type": "recovery.payment_recovered",
      "title": "Payment recovered",
      "message": "Northstar Labs paid $8,420.00",
      "account": "Northstar Labs",
      "case_id": "f7a28190-8812-4c22-b912-334455667788",
      "amount_minor": 842000,
      "severity": "success",
      "icon": "check"
    }
  }
  ```
