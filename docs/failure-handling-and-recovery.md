# RevenueRescueAI — Failure Handling and Recovery Specification

## 1. Executive Summary & Philosophy of Failure Handling

In a financial recovery platform like **RevenueRescueAI**, failure is not an unexpected anomaly—it is a routine operational reality. External banking gateways experience transient network drops, machine learning models experience hallucinations or API timeouts, merchants send duplicate webhook payloads, and customer payment methods fail repeatedly.

The foundational design principle of RevenueRescueAI is:
> **"Fail Closed, Never Assume Success, and Preserve Strict Financial Auditability."**

Under no circumstances does the system:
1. Blindly retry unverified transactions.
2. Mark money as recovered without authoritative proof.
3. Allow an AI agent to bypass deterministic safety rules upon failure.
4. Leave workflow states in ambiguous, partially mutated states.

---

## 2. Failure Scenarios and Detailed Handling Workflows

```
                                  FAILURE DISPATCHER
                                          │
       ┌─────────────────┬────────────────┼────────────────┬────────────────┐
       ▼                 ▼                ▼                ▼                ▼
 [Scenario A]      [Scenario B]     [Scenario C]     [Scenario D]     [Scenario E]
Duplicate Event     AI Failure     Policy Rejection Provider Decline  Network Timeout
 (Idempotency)   (Fallback Rules)     (Veto Log)     (Retry Decrement)  (UNCERTAIN State)
```

---

### Scenario A: Duplicate Payment Event

#### 1. Context and Problem
An upstream merchant system or payment gateway experiences network instability and retries sending a `PAYMENT_FAILED` webhook payload multiple times within seconds.

#### 2. Detection Mechanism
- **Natural Business Key:** `(merchant_id, provider_event_id)` has a unique database constraint in `payment_events`.
- **Payload Hash:** SHA-256 fingerprint of the normalized request payload.
- **Workflow Query:** Before inserting a new event, the `EventIngestionService` queries the database for existing `provider_event_id`.

#### 3. Handling Workflow & Response
1. The incoming webhook is intercepted by `EventIngestionFilter`.
2. A database lookup on `payment_events.provider_event_id` detects an existing record.
3. **Guard Action:** The system drops the insertion into `payment_events` and skips creating a new `recovery_cases` record.
4. **Audit Trail:** An audit log event `EVENT_INGESTION_DUPLICATE_IGNORED` is emitted.
5. **HTTP Response:** The API returns `HTTP 200 OK` (or `HTTP 409 Conflict` depending on endpoint semantics) with a standardized idempotent acknowledgement payload:
   ```json
   {
     "status": "DUPLICATE_IGNORED",
     "case_id": "case_live_99214a",
     "message": "Payment event already ingested and associated with active recovery case."
   }
   ```
6. **Financial Invariant:** No duplicate financial cases, balance amounts, or revenue-at-risk totals are created.

---

### Scenario B: AI Recommendation Failure

#### 1. Context and Problem
The external LLM provider (e.g., OpenAI API or Anthropic API) returns an HTTP 500 error, experiences high latency exceeding the 3,000ms deadline, or returns an unparseable JSON output that violates the strict Zod/Pydantic output schema.

#### 2. Detection Mechanism
- **HTTP Client Timeout:** Circuit-breaker and timeout wrapper enforcing strict 3,000ms SLA.
- **Schema Validation:** Strict JSON schema validation on the AI response payload (`action_type`, `channel`, `recommended_delay_hours`, `reasoning_summary`).

#### 3. Handling Workflow & Response
1. The AI engine catches the `LLMTimeoutException` or `ValidationError`.
2. The orchestrator transitions the case state from `ANALYSING` to `RECOMMENDED` using an **Approved Deterministic Rule-Based Fallback Strategy**.
3. **Approved Fallback Matrix:**
   - *Soft Decline (Insufficient Funds):* Default fallback action is `SCHEDULED_PAYMENT_RETRY` with a standard 24-hour delay.
   - *Technical Drop / Network Timeout:* Default fallback action is `SCHEDULED_PAYMENT_RETRY` with a 4-hour delay.
   - *Hard Decline / Expired Card:* Default fallback action is `DISPATCH_CUSTOMER_EMAIL_UPDATE_CARD` immediately.
4. **Audit Recording:** Emits `AI_RECOMMENDATION_FAILED` containing the error message, followed by `FALLBACK_STRATEGY_APPLIED`.
5. **Safety Guard:** The system NEVER halts silently or allows an unapproved arbitrary action. The fallback recommendation must still pass through the Policy Validation Gate.

---

### Scenario C: Policy Rejection (AI Proposes an Illegal Action)

#### 1. Context and Problem
The LLM hallucinates or reasons improperly, recommending a 4th payment retry when the case has already suffered 3 failed attempts, or recommends an aggressive SMS recovery attempt at 03:00 AM local customer time, violating anti-harassment/TCPA regulations.

#### 2. Detection Mechanism
- **Deterministic Policy Gate:** Executes before any orchestrator tool execution.
- Evaluates 6 deterministic rules:
  1. `MAX_RETRIES_EXCEEDED`: `current_retry_count >= 3`.
  2. `COOLDOWN_VIOLATION`: Time since last retry `< 4 hours`.
  3. `TIME_WINDOW_VIOLATION`: Outreach scheduled outside 08:00 - 20:00 local time.
  4. `BLACKLISTED_PAYMENT_METHOD`: Account flagged for fraud or chargeback risk.
  5. `INACTIVE_MERCHANT`: Merchant subscription suspended.
  6. `DISALLOWED_CHANNEL`: Customer opted out of SMS notifications.

#### 3. Handling Workflow & Response
1. The Policy Gate flags the proposed action with status `REJECTED`.
2. **Execution Block:** The orchestrator refuses to pass the command to the Payment Simulator or Communication Provider.
3. **Database Update:** The recommendation record is updated with `is_policy_approved = false` and `rejection_reason = "Rule MAX_RETRIES_EXCEEDED violated: current count 3 exceeds limit of 3"`.
4. **State Transition:** The case is transitioned to `ESCALATED` or `AWAITING_APPROVAL` for human review.
5. **Audit Trail:** Emits `POLICY_GATE_EVALUATED` (Decision: `REJECTED`, Violated Rule: `MAX_RETRIES_EXCEEDED`).
6. **UI Visibility:** Dashboard displays a prominent amber badge: *"AI Action Vetoed by Policy Gate (Max Retries Exceeded)"*.

---

### Scenario D: Recovery Execution Failure (Provider Decline)

#### 1. Context and Problem
The orchestrator executes a permitted retry attempt against the Payment Simulator/Stripe Gateway, but the card network declines the charge again with code `card_declined:insufficient_funds`.

#### 2. Detection Mechanism
- The Payment Simulator or Gateway returns a definitive decline response (`HTTP 200` with status `failed`, code `insufficient_funds`, or `HTTP 402 Payment Required`).

#### 3. Handling Workflow & Response
1. The execution result is parsed by `PaymentExecutionHandler`.
2. **Attempt Recording:** A record is created in `recovery_attempts`:
   - `attempt_number = case.attempt_count + 1`
   - `status = "FAILED"`
   - `failure_code = "insufficient_funds"`
   - `finished_at = NOW()`
3. **Retry Counter:** `recovery_cases.attempt_count` is incremented by 1.
4. **Branching Decision:**
   - *If `attempt_count < 3`:* Case moves to `PENDING` with a new scheduled retry time (e.g., in 48 hours).
   - *If `attempt_count >= 3`:* Case moves to terminal failure or human escalation state `ESCALATED`.
5. **Zero Phantom Recovery:** `recovered_amount_cents` remains `0`.
6. **Audit Trail:** Emits `RECOVERY_ATTEMPT_FAILED`.

---

### Scenario E: Network Timeout (Uncertain Outcome / Gateway 504)

#### 1. Context and Problem
The backend submits a charge attempt to Stripe or the Payment Simulator. The TCP socket abruptly terminates, or the gateway returns `HTTP 504 Gateway Timeout` after 15 seconds. The backend has no knowledge whether the customer's card was charged or not.

#### 2. Detection Mechanism
- `HTTPClientTimeoutException` or socket hang-up during outbound HTTP POST to the payment provider.

#### 3. Handling Workflow & Response (The UNCERTAIN Protocol)
1. **Never Blindly Retry:** Under financial safety invariants, retrying an in-flight transaction can cause **double-charging the customer**, leading to disputes and fines.
2. **State Transition:** The case transitions immediately to the special safety state: **`UNCERTAIN`**.
3. **Attempt Recording:** A record in `recovery_attempts` is saved with `status = "UNCERTAIN"` and `provider_transaction_id = pending_verification`.
4. **Active Verification Job:** The system schedules an automated asynchronous reconciliation job via `VerificationWorker`:
   - The worker executes an **Idempotent Inquiry** (`GET /v1/simulator/transactions/{idempotency_key}` or `GET /v1/charges?idempotency_key=...`).
5. **Resolution Branches:**
   - *Outcome Found - Succeeded:* Mark attempt `SUCCEEDED`, transition case to `RECOVERED`.
   - *Outcome Found - Failed:* Mark attempt `FAILED`, transition case to `FAILED` or `PENDING`.
   - *Outcome Not Found (Transaction never reached provider):* Mark attempt `ABORTED_UNPROCESSED`, allow safe retry.
6. **Safety Invariant:** A case in `UNCERTAIN` locks all automated outreach and retries until verified or resolved manually by a support agent.

---

### Scenario F: Database Failure During Workflow Execution

#### 1. Context and Problem
During an active recovery transaction, the PostgreSQL database becomes momentarily unavailable (e.g., connection pool exhaustion, deadlock, or restart).

#### 2. Detection Mechanism
- SQLAlchemy/Prisma catches `OperationalError`, `IntegrityError`, or `DatabaseConnectionTimeout`.

#### 3. Handling Workflow & Response
1. **ACID Transaction Boundaries:** All database mutations are wrapped in explicit database transactions:
   ```sql
   BEGIN TRANSACTION;
   -- 1. Mutate case state
   -- 2. Insert attempt record
   -- 3. Insert audit log
   COMMIT;
   ```
2. **Automatic Rollback:** If any error occurs prior to `COMMIT`, the entire transaction rolls back cleanly.
3. **Out-of-Process Side Effects Prevention (Two-Phase Planned Execution):**
   - The backend *never* calls external payment APIs inside an open database transaction lock.
   - **Phase 1 (DB Tx):** Case marked `PROCESSING`, planned attempt record created. Transaction COMMITTED.
   - **Phase 2 (HTTP Call):** External payment API invoked with unique `idempotency_key`.
   - **Phase 3 (DB Tx):** Case updated with final provider result (`RECOVERED` or `FAILED`). Transaction COMMITTED.
4. **Crash Recovery Reconciliation:** If the server crashes during Phase 2, a startup reconciliation daemon queries all cases stuck in `PROCESSING` for `> 10 minutes` and executes the verification protocol.

---

### Scenario G: Retry Limit Reached (Terminal Exhaustion)

#### 1. Context and Problem
A customer's card has failed 3 consecutive retry attempts over a 7-day period.

#### 2. Detection Mechanism
- `case.attempt_count == 3` and the 3rd attempt returns `FAILED`.

#### 3. Handling Workflow & Response
1. **Automated Suspension:** The orchestrator permanently halts automated recovery workflows for this case.
2. **State Transition:** Case transitions to `ESCALATED` (or `CLOSED_FAILED`).
3. **Escalation Notification:** Emits a high-priority dashboard alert and webhook to the merchant:
   ```json
   {
     "event": "RECOVERY_CASE_EXHAUSTED",
     "case_id": "case_live_99214a",
     "total_attempts": 3,
     "amount_cents": 12000,
     "recommended_merchant_action": "CANCEL_SUBSCRIPTION_OR_MANUAL_OUTREACH"
   }
   ```
4. **Financial Attribution:** The amount is permanently marked as unrecovered loss; `recovered_amount_cents = 0`.
5. **Audit Trail:** Emits `CASE_RETRIES_EXHAUSTED`.

---

## 3. Comprehensive Failure-Handling Matrix

| Failure Trigger | Detection Point | Automated System Response | State Transition | Audit Event Required | Final Recovery Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Duplicate Webhook** | Ingestion Filter (DB Unique Key) | Ignore payload, return HTTP 200 with existing ID | *No State Change* | `DUPLICATE_EVENT_IGNORED` | Idempotent response; preserve single case truth. |
| **AI LLM Timeout (>3s)** | AI Gateway Client | Abort LLM call, trigger deterministic rule fallback | `ANALYSING` → `RECOMMENDED` | `AI_TIMEOUT_FALLBACK_APPLIED` | Execute standard 24h retry fallback rule. |
| **AI Schema Malformed** | Zod / Pydantic Parser | Reject output, log raw text, trigger fallback | `ANALYSING` → `RECOMMENDED` | `AI_OUTPUT_PARSING_FAILED` | Fallback to hardcoded channel decision tree. |
| **Policy Rule Rejection** | Policy Engine Pre-Execution | Intercept action, block payment API dispatch | `RECOMMENDED` → `ESCALATED` | `POLICY_RULE_VIOLATED` | Alert human operator via UI review queue. |
| **Soft Gateway Decline** | Provider HTTP Response | Record attempt, increment counter, schedule cooldown | `PROCESSING` → `PENDING` | `RECOVERY_ATTEMPT_FAILED` | Wait for cooldown (24h-48h), retry if count < 3. |
| **Hard Gateway Decline** | Provider HTTP Response (e.g. stolen card) | Record attempt, flag card unusable | `PROCESSING` → `ESCALATED` | `HARD_DECLINE_NOTIFIED` | Halt payment retries; trigger card update email. |
| **Gateway 504 / Socket Drop** | Payment HTTP Client | Do not retry; lock case against actions | `PROCESSING` → `UNCERTAIN` | `OUTCOME_UNCERTAIN_LOGGED` | Async reconciliation worker queries charge status. |
| **DB Disconnect on Commit** | Database Driver Pool | Roll back transaction, retry DB write with backoff | *Preserves Prior DB State* | `DATABASE_TX_ROLLBACK` | Health check probe alerts operations team. |
| **Max Retry Limit (3/3)** | Workflow Orchestrator | Permanently stop automated retries | `PROCESSING` → `ESCALATED` | `CASE_RETRIES_EXHAUSTED` | Merchant manual review / cancel subscription. |
| **Customer Chargeback Flag**| Ingestion / Risk Engine | Immediately halt all recovery outreach | Any → `CANCELLED` | `CASE_CANCELLED_FRAUD_RISK` | Cease collection actions to avoid scheme fines. |

---

## 4. Disaster Recovery & Reconciliation Protocol

1. **Stale Case Sweeper (Cron Worker):**
   - Runs every 15 minutes.
   - Queries `SELECT * FROM recovery_cases WHERE state = 'PROCESSING' AND updated_at < NOW() - INTERVAL '15 minutes'`.
   - Any stale `PROCESSING` case is automatically transitioned to `UNCERTAIN` and queued for provider verification.
2. **Audit Immutability During Disasters:**
   - Audit logs are written synchronously in the same transaction as state changes. If the database crashes, neither the state change nor the audit record is committed—maintaining 100% relational integrity.
