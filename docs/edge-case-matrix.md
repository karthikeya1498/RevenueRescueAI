# RevenueRescueAI — Negative & Edge-Case Requirements Matrix

> **Document ID:** DOC-EDG-008  
> **Phase:** 0.2 (User Stories, Functional Requirements & Acceptance Criteria)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

Financial software engineering is defined by how it handles edge cases and anomalies. A naive system works when inputs are clean, networks are fast, and payments succeed on the first attempt; an enterprise-grade recovery engine remains secure, deterministic, and consistent when payloads are corrupted, networks time out, and duplicate requests arrive simultaneously.

This document establishes the Master Edge-Case Matrix for RevenueRescueAI, exhaustively detailing all twenty-four mandatory negative scenarios. For each edge case, it defines the triggering condition, expected system behavior, lifecycle disposition (Halt vs. Escalate vs. Reject), required audit event, and automated verification method.

---

## 2. Master Edge-Case Matrix (24 Critical Scenarios)

| # | Edge Case Scenario | Triggering Input Condition | Expected System Behavior | Lifecycle Disposition | Required Audit Event | Test Verification Method |
|---|---|---|---|:---:|---|---|
| **1** | **Missing Payment ID** | Webhook JSON lacks mandatory `payment_id` attribute. | Pydantic validation rejects payload immediately with HTTP 400 Bad Request; zero case creation. | **REJECT (Stop)** | `INGESTION_SCHEMA_ERROR` | Schema validation unit test firing payload with missing key. |
| **2** | **Invalid Amount (Non-numeric)** | Webhook `amount` field contains string `"forty-five"` or boolean `true`. | Validator rejects payload with HTTP 400 Bad Request; outputs structured typing error. | **REJECT (Stop)** | `INGESTION_SCHEMA_ERROR` | Type fuzzing test firing non-numeric amount values. |
| **3** | **Negative Amount** | Webhook contains negative value e.g., `amount: -4500`. | Validator catches negative constraint violation; rejects with HTTP 400 Bad Request. | **REJECT (Stop)** | `INGESTION_VALIDATION_ERROR` | Boundary test submitting negative and zero amount values. |
| **4** | **Unsupported Currency** | Webhook currency contains unsupported string e.g., `"XYZ"` or `"BITCOIN"`. | Currency validator checks ISO-4217 allow-list; rejects with HTTP 422 Unprocessable Entity. | **REJECT (Stop)** | `UNSUPPORTED_CURRENCY_REJECTED` | Parametric test passing invalid currency strings. |
| **5** | **Duplicate Event ID** | Identical `event_id` delivered twice by payment gateway due to network ACK delay. | Database unique index detects match; acknowledges with HTTP 200 `{ "status": "duplicate_acknowledged" }`; bypasses processing. | **ABSORB (Stop)** | `DUPLICATE_EVENT_ABSORBED` | Ingest identical event sequentially; assert single case created. |
| **6** | **Conflicting Payload on Same Event ID** | Inbound webhook has identical `event_id` as existing event, but `amount` differs. | Payload SHA-256 hash mismatch detected; rejects with HTTP 409 Conflict; raises tamper alert. | **REJECT & ALERT** | `EVENT_HASH_COLLISION_ALERT` | Submit event with matching ID but altered amount; assert HTTP 409. |
| **7** | **Payment Already Recovered** | Recovery retry triggered for an invoice whose authoritative status is already `PAID`. | Success Protection Gate intervenes; blocks retry immediately; closes case without tool dispatch. | **HALT (Terminal)** | `SUCCESS_PROTECTION_BLOCKED` | Attempt retry on case where invoice was settled out-of-band; assert block. |
| **8** | **Payment Outcome Unavailable** | Simulator returns HTTP 200 but payload lacks definitive transaction status field. | Outcome verifier flags status `UNCERTAIN`; transitions case to `VERIFICATION_PENDING`; schedules poll. | **UNCERTAIN (Hold)** | `VERIFICATION_STATUS_UNKNOWN` | Mock gateway returning empty status dictionary; assert hold state. |
| **9** | **Provider Network Timeout** | Outgoing retry call times out after 15s (socket hangup / HTTP 504). | Three-valued logic catches timeout; marks outcome `UNCERTAIN`; freezes automated retries; schedules poll. | **UNCERTAIN (Hold)** | `GATEWAY_TIMEOUT_PENDING` | Simulate socket timeout on provider adapter; assert no immediate retry. |
| **10** | **Provider Unexpected Error (500)** | Gateway simulator returns unhandled HTTP 500 Internal Server Error. | Engine catches 500; logs provider error; queues case for exponential backoff retry (Attempt 1 of 3). | **RETRY_SCHEDULED** | `PROVIDER_INTERNAL_ERROR` | Mock gateway returning HTTP 500; assert case transitions to scheduled retry. |
| **11** | **Concurrent Worker Execution** | Two background workers attempt to claim and process the same case simultaneously. | Row-level locking (`SELECT ... FOR UPDATE`) or optimistic lock version check aborts second worker. | **SERIALIZE / ROLLBACK** | `CONCURRENCY_LOCK_ACQUIRED` | Concurrency test spawning 2 threads updating same case; assert 1 succeeds. |
| **12** | **Retry Budget Exhausted** | Case reaches attempt 3 and subsequent payment attempt returns a soft decline. | Workflow increments counter to 3; evaluates stopping rule; permanently halts automated retries. | **HALT (Terminal)** | `RETRY_BUDGET_EXHAUSTED` | Execute 3 consecutive failed retries; assert case transitions to `HALTED`. |
| **13** | **Recovery Window Expired** | Case reaches day 15 (> 14 calendar days from initial failure timestamp). | Eligibility check flags window expiration; invalidates pending retries; transitions to `HALTED_EXPIRED`. | **HALT (Terminal)** | `RECOVERY_WINDOW_EXPIRED` | Advance virtual clock past 14 days; assert scheduled timer cancels. |
| **14** | **Invalid Customer Reference** | Inbound event specifies `customer_id` that cannot be resolved in customer database. | Ingestion instantiates temporary guest customer profile; flags case with `GUEST_REFERENCE_WARNING`. | **CONTINUE (Flagged)** | `UNRESOLVED_CUSTOMER_FLAGGED` | Ingest event with unmapped customer ID; assert guest profile created. |
| **15** | **Missing Eligibility Metadata** | Customer account record exists but lacks active/suspended status flag. | Eligibility engine treats missing data conservatively as `INELIGIBLE_MISSING_METADATA`; routes to review. | **ESCALATE (Review)** | `ELIGIBILITY_METADATA_MISSING` | Ingest case for customer with null status; assert routed to review. |
| **16** | **Invalid AI Model Response** | LLM output contains unparseable syntax or hallucinates non-existent action `CANCEL_DEBT`. | Pydantic schema validation rejects proposal; triggers immediate fallback to deterministic rule. | **FALLBACK (Continue)** | `MODEL_INVALID_OUTPUT_REJECTED` | Inject mock LLM response with unauthorized action name; assert fallback. |
| **17** | **AI Service Unavailable** | LLM API returns HTTP 429 Rate Limited or connection refused. | Catch block intercepts error; logs warning; applies deterministic fallback rule without crashing. | **FALLBACK (Continue)** | `MODEL_UNAVAILABLE_FALLBACK` | Mock LLM throwing connection refused; assert pipeline completes via fallback. |
| **18** | **Database Transaction Failure** | Database connection drops or transaction deadlocks during state update. | Database driver throws error; entire transaction rolls back cleanly; upstream returns HTTP 503. | **ROLLBACK (Retry)** | `DATABASE_TRANSACTION_ABORTED` | Inject database connection abort mid-action; assert zero partial state saved. |
| **19** | **Duplicate Audit Event ID** | System attempts to insert an audit event with an already-used UUID. | Database primary key unique constraint blocks insertion; generates fresh UUID and retries. | **RETRY KEY (Continue)**| `AUDIT_KEY_COLLISION_RESOLVED` | Test inserting two identical audit UUIDs; assert constraint enforcement. |
| **20** | **Inconsistent Currency or Amount** | Outgoing retry attempts to charge in EUR for a case registered in USD. | Policy Gate validates currency match invariant; rejects action with reason `CURRENCY_MISMATCH`. | **VETO (Halt)** | `CURRENCY_MISMATCH_VETO` | Attempt dispatch with mismatched currency parameter; assert policy veto. |
| **21** | **Unauthorized Tool Action** | Decision Engine proposes action not in allow-list (e.g., `TRIGGER_REFUND`). | Schema validator rejects action; Policy Gate emits `PolicyDecision: REJECTED`; halts action. | **VETO (Halt)** | `UNAUTHORIZED_TOOL_VETO` | Inject proposal with unauthorized action; assert zero tool dispatch. |
| **22** | **Attempt to Modify Business Rule** | API client attempts to alter maximum retry limit via unauthenticated query param. | Policy rules are hardcoded invariants in code; API rejects runtime alteration with HTTP 403. | **REJECT (Stop)** | `POLICY_TAMPERING_ATTEMPT` | Attempt `PATCH /api/v1/policy/max-retries`; assert HTTP 403 Forbidden. |
| **23** | **Customer Opt-Out Active** | Customer has `communication_opted_out: true` in profile. | Notification tool is suppressed; system permits only silent card retries if authorized. | **SUPPRESS (Continue)** | `COMMUNICATION_SUPPRESSED` | Attempt dispatching notification to opted-out customer; assert blocked. |
| **24** | **Case Already Closed** | Webhook or retry event arrives for a case already in terminal state `RECOVERED` or `CLOSED`. | State machine asserts current state is terminal; ignores action request; preserves closed state. | **IGNORE (Terminal)** | `CLOSED_CASE_MUTATION_BLOCKED` | Attempt dispatching retry against case in `RECOVERED` state; assert rejected. |

---

## 3. Detailed Edge-Case Behavior Specifications

### Scenario 1–4: Ingestion Boundary Failures (Bad Data)
When inputs fail perimeter validation (missing ID, bad amount, negative amount, bad currency):
- The Event Ingestion Service **must not create a partial case record in the database**.
- It returns an immediate HTTP 4xx response to the client.
- It records a structured security log event containing the client IP, invalid attribute name, and payload hash.

### Scenario 7–10: Distributed Transaction & Gateway Errors
When payment gateway communications fail or return ambiguous states:
- Under no circumstances does the system assume failure and re-attempt immediately.
- The outcome is isolated in state `VERIFICATION_PENDING`.
- Asynchronous reconciliation polls verify authoritative state before any secondary action can be queued.

### Scenario 16–17: Model & AI Infrastructure Failures
When AI intelligence components fail, hallucinate, or time out:
- The system treats AI as an optional optimization layer, not a single point of failure.
- The workflow gracefully falls back to deterministic rule-based logic (e.g., standard 48-hour backoff).
- System availability is preserved at 100%.
