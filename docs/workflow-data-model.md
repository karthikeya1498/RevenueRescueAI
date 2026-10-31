# RevenueRescueAI — Workflow Data Model Specification
## Phase 1.2: State Machine Persistence, Transition Integrity, and Lifecycle Tracing

**Document Version:** 1.0.0  
**Status:** Approved Workflow Architecture  
**Primary Authors:** Senior Backend Engineer, Principal Software Architect  

---

## 1. Executive Summary & State Storage Ownership

In complex financial workflows, inconsistent or duplicated state representation causes catastrophic errors. If one table says a case is `RECOVERED` while another table says it is `ACTION_PENDING`, the system cannot determine whether to charge the cardholder again.

RevenueRescueAI establishes a strict **Single Source of Truth** for workflow state:
1. **Current State Authority:** Stored exclusively in `recovery_cases.state`.
2. **Transition History Authority:** Stored sequentially in `case_state_transitions`.
3. **Execution Attempt Authority:** Stored in `recovery_attempts`.
4. **Audit History Authority:** Stored in `audit_events`.

---

## 2. Recovery Case State Machine

The case state machine defines nine explicit states, partitioned into three lifecycle tiers:

```
+-----------------------------------------------------------------------------------------------+
|                                    WORKFLOW STATE TAXONOMY                                    |
+-------------------+---------------------------------------------------------------------------+
| Active States     | `DETECTED`              -> Initial failure signal captured                |
|                   | `ANALYZING`             -> Diagnostics and context aggregation in progress|
|                   | `ACTION_SELECTED`       -> AI proposed decision approved by Policy Gate   |
|                   | `ACTION_PENDING`        -> Tool execution dispatched or retry scheduled   |
|                   | `VERIFICATION_PENDING`  -> Provider timeout (504) or awaiting settlement  |
+-------------------+---------------------------------------------------------------------------+
| Intermediary      | `RETRY_ELIGIBLE`        -> Soft decline; waiting for backoff retry        |
|                   | `ESCALATED`             -> Retry budget reached; awaiting human review    |
+-------------------+---------------------------------------------------------------------------+
| Terminal States   | `RECOVERED`             -> Legitimate recovery verified (<72h)            |
| (IMMUTABLE LOCK)  | `FAILED`                -> Permanent decline or non-retryable error       |
|                   | `TERMINATED`            -> Account closed, disputed, or manually halted   |
+-------------------+---------------------------------------------------------------------------+
```

---

## 3. State Transition Matrix & Validation Rules

A state transition is valid if and only if it appears in the **Permitted Transition Matrix**:

| Origin State (`from_state`) | Permitted Destination States (`to_state`) | Valid Trigger / Condition |
| :--- | :--- | :--- |
| `NULL` | `DETECTED` | New failed payment webhook received. |
| `DETECTED` | `ANALYZING`, `TERMINATED` | Case opened; or account frozen/disputed. |
| `ANALYZING` | `ACTION_SELECTED`, `ESCALATED`, `FAILED` | Diagnosis complete; or low confidence/policy failure. |
| `ACTION_SELECTED` | `ACTION_PENDING`, `ESCALATED` | Tool execution initiated. |
| `ACTION_PENDING` | `RECOVERED`, `RETRY_ELIGIBLE`, `VERIFICATION_PENDING`, `FAILED`, `ESCALATED` | Provider outcome received. |
| `VERIFICATION_PENDING` | `RECOVERED`, `RETRY_ELIGIBLE`, `FAILED`, `ESCALATED` | Status inquiry settled by provider. |
| `RETRY_ELIGIBLE` | `ACTION_SELECTED`, `ESCALATED` | Exponential backoff timer elapsed. |
| `ESCALATED` | `ACTION_SELECTED`, `TERMINATED` | Human operator manually overrides or closes. |
| **`RECOVERED`** | **NONE (TERMINAL)** | **IMMUTABLE LOCK (Invariant INV-004).** |
| **`FAILED`** | **NONE (TERMINAL)** | **IMMUTABLE LOCK (Invariant INV-004).** |
| **`TERMINATED`** | **NONE (TERMINAL)** | **IMMUTABLE LOCK (Invariant INV-004).** |

### Transition Validation Enforcement
When an invalid transition is attempted (e.g., trying to move from `RECOVERED` back to `DETECTED`):
1. The `TransitionService` checks the transition matrix in memory.
2. It raises `InvalidStateTransitionError("Cannot transition from RECOVERED to DETECTED")`.
3. The surrounding database transaction is rolled back immediately, leaving the database state pristine.

---

## 4. Retry Budget Tracking & Invariant Enforcement

To protect cardholders and merchants from card network fines (Visa/Mastercard rules prohibit excessive retries), the database enforces strict limits:

### 4.1 Bounded Retry Count (Invariant INV-002)
- **Maximum Retries:** Exactly **2 retries** per recovery case.
- **Tracking Formula:**
  ```sql
  SELECT count(*) FROM recovery_attempts 
  WHERE case_id = :case_id AND status != 'CANCELLED';
  ```
- **Database Boundary Constraint:**
  ```sql
  CONSTRAINT ck_attempt_sequence_budget CHECK (sequence_number >= 1 AND sequence_number <= 2)
  ```
If an attempt with `sequence_number = 3` is inserted, the database engine raises an immediate check constraint violation.
- **Policy Gate Rule:** When `attempt_count >= 2`, the Policy Gate vetoes any further `RETRY_NOW` or `SCHEDULE_RETRY` actions and forces a transition to `ESCALATED`.

---

## 5. Uncertain Outcomes & Resilient Crash Recovery

When an external provider call times out (HTTP 504) or the application crashes mid-call, the recovery engine handles the state deterministically:

### 5.1 Representation of Uncertain Outcomes (Invariant INV-008)
- `recovery_attempts.status` is set to `UNCERTAIN`.
- `recovery_cases.state` transitions to `VERIFICATION_PENDING`.
- An audit event is written: `event_type = "OUTCOME_UNCERTAIN_TIMEOUT"`.
- The system is barred from retrying the payment immediately.

### 5.2 Resuming Interrupted Execution
If the application crashes and restarts:
1. The background recovery worker queries for cases in `ACTION_PENDING` or `VERIFICATION_PENDING`.
2. It inspects the associated `recovery_attempts` record for the unique `idempotency_key`.
3. It issues a status inquiry to the payment provider:
   ```http
   GET /v1/charges?idempotency_key=rec_att_f7a28190_seq1
   ```
4. If the provider confirms the charge succeeded, the worker creates `RecoveryEvidence` and moves the case to `RECOVERED`.
5. If the provider confirms the charge failed, the worker moves the case to `RETRY_ELIGIBLE` (if retry budget remains) or `ESCALATED`.

---

## 6. End-to-End Concrete Lifecycle Example

The following walkthrough traces how a single failed payment of **$8,420.00 USD** for synthetic customer **Northstar Labs** travels through the complete data model:

```
[ EVENT ARRIVAL ]
1. Inbound Webhook: Provider delivers payment_intent.payment_failed for $8,420.00 USD (amount_minor: 842000).
   • Record created in provider_webhook_events (id: evt_001, external_event_id: 'evt_sim_99812').
   • Transaction recorded: transactions (id: txn_001, status: 'failed', failure_code: 'insufficient_funds').

[ CASE CREATION ]
2. Recovery Case Initialized:
   • INSERT INTO recovery_cases (id: case_001, customer_id: cus_001, trigger_transaction_id: txn_001,
                                 case_key: 'case_sim_8F31A_01', state: 'DETECTED', version: 1);
   • Transition recorded: case_state_transitions (case_id: case_001, from_state: NULL, to_state: 'DETECTED', seq: 1).
   • Audit logged: audit_events (case_id: case_001, event_type: 'CASE_DETECTED', seq: 1).

[ DIAGNOSIS & REASONING ]
3. AI Advisor & Policy Evaluation:
   • Case state moves: DETECTED -> ANALYZING (seq: 2).
   • Diagnosis: insufficient_funds -> SOFT_DECLINE.
   • AI recommends: RETRY_NOW (confidence: 0.94).
   • INSERT INTO agent_decisions (id: dec_001, action_type: 'retry_now', validation_status: 'VALIDATED').
   • Case state moves: ANALYZING -> ACTION_SELECTED (seq: 3).

[ EXECUTION ATTEMPT 1 ]
4. Recovery Attempt Dispatched:
   • Case state moves: ACTION_SELECTED -> ACTION_PENDING (seq: 4).
   • INSERT INTO recovery_attempts (id: att_001, case_id: case_001, sequence_number: 1,
                                    idempotency_key: 'rec_att_case001_seq1', status: 'STARTED');
   • Provider responds: HTTP 200 OK (status: 'succeeded', charge_id: 'ch_sim_8F31_01').
   • UPDATE recovery_attempts SET status = 'SUCCEEDED', provider_reference = 'ch_sim_8F31_01';

[ OUTCOME VERIFICATION & CLOSURE ]
5. Evidence Verification & State Lock:
   • OutcomeVerificationService confirms: amount_minor matches 842000, customer matches, elapsed time: 4 seconds (<72h).
   • INSERT INTO recovery_evidence (intervention_id: att_001, provider_event_id: 'evt_sim_99815',
                                   amount_minor: 842000, currency: 'USD', attributable: TRUE);
   • UPDATE recovery_cases SET state = 'RECOVERED', closed_at = NOW(), version = version + 1;
   • Transition recorded: case_state_transitions (from: 'ACTION_PENDING', to: 'RECOVERED', seq: 5).
   • Audit logged: audit_events (event_type: 'CASE_RECOVERED', seq: 5).

[ LIFECYCLE RESULT ]
Case is permanently locked. Recovered revenue metrics updated by $8,420.00. Zero duplicate attempts possible.
```
