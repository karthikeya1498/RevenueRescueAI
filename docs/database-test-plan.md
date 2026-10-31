# RevenueRescueAI — Database Architecture Test Plan
## Phase 1.2: Data Integrity, Relational Invariants, and Concurrency Test Specifications

**Document Version:** 1.0.0  
**Status:** Approved Test Specification (Design Only)  
**Primary Authors:** QA Architect, Senior Database Architect, Backend Test Engineer  

---

## 1. Test Strategy & Scope Overview

This test plan defines the formal test suite designed to validate the database schema, relational constraints, financial math, workflow invariants, and concurrency safeguards before application deployment.

### Test Categories:
- **Category 1 (ET):** Entity & Schema Constraints
- **Category 2 (RT):** Relationships & Referential Integrity
- **Category 3 (FT):** Financial Math & Attribution Safeguards
- **Category 4 (IT):** Idempotency & Concurrency Defenses
- **Category 5 (WT):** Workflow FSM State Transitions
- **Category 6 (AT):** Audit Ledger Integrity & Immutability
- **Category 7 (EV):** 500-Scenario Evaluation Reproducibility

---

## 2. Comprehensive Test Matrix

### 2.1 Category 1: Entity & Schema Constraint Tests

| Test ID | Scenario | Input / Action | Expected Result | Expected Database Effect | Failure Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ET-01** | Non-Negative Amount | Attempt to insert `Transaction` with `amount_minor = -500`. | Insertion rejected with DB check constraint error. | Zero rows inserted. Transaction rolls back. | Row inserted with negative amount. |
| **ET-02** | Zero Amount Allowed | Insert `Transaction` with `amount_minor = 0` (card authorization verification). | Insertion succeeds. | Row committed in `transactions`. | DB rejects zero amount. |
| **ET-03** | Currency Code Format | Insert `Transaction` with `currency = 'usd'` (lowercase) or `'US'` (2 chars). | Rejected by `ck_transaction_currency`. | Rollback; error raised. | Lowercase or invalid length currency accepted. |
| **ET-04** | Valid Currency | Insert `Transaction` with `currency = 'USD'`. | Insertion succeeds. | Row committed. | Valid ISO code rejected. |
| **ET-05** | Mandatory Trigger Txn | Attempt to insert `RecoveryCase` with `trigger_transaction_id = NULL`. | Rejected by NOT NULL constraint. | Zero rows inserted. | Case created without trigger transaction. |
| **ET-06** | Confidence Range | Insert `AgentDecision` with `confidence = 1.05` or `-0.1`. | Rejected by `ck_decision_confidence`. | Rollback; error raised. | Confidence outside $[0, 1]$ accepted. |

---

### 2.2 Category 2: Relationship & Referential Integrity Tests

| Test ID | Scenario | Input / Action | Expected Result | Expected Database Effect | Failure Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RT-01** | Missing Foreign Key | Insert `Transaction` with non-existent `customer_id`. | Rejected with Foreign Key Violation. | Rollback. | Orphan transaction created. |
| **RT-02** | Customer Deletion Restrict | Attempt `DELETE FROM customers WHERE id = :id` when cases exist. | Rejected with `ON DELETE RESTRICT` error. | Customer row remains untouched. | Customer deleted, orphaning recovery cases. |
| **RT-03** | Trigger Txn Restrict | Attempt `DELETE FROM transactions` for an active recovery case. | Rejected with `ON DELETE RESTRICT` error. | Transaction row remains untouched. | Trigger transaction deleted from under active case. |
| **RT-04** | Unique Provider Event | Ingest webhook with duplicate `(provider, external_event_id)`. | Rejected by `uq_provider_event`. | Second row rejected; deduplicator returns HTTP 200.| Duplicate webhook row created. |
| **RT-05** | Unique Case Key | Create second `RecoveryCase` with identical `case_key`. | Rejected by `uq_recovery_case_key`. | Rollback. | Duplicate active cases for same trigger transaction. |

---

### 2.3 Category 3: Financial Math & Attribution Safeguards

| Test ID | Scenario | Input / Action | Expected Result | Expected Database Effect | Failure Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FT-01** | Exact Amount Matching | Match provider success ($8,420.00) against failed transaction ($8,420.00). | Attribution verified. | Row inserted in `recovery_evidence` (`attributable = TRUE`). | Exact amount match rejected. |
| **FT-02** | Mismatched Amount | Match provider success ($50.00) against failed transaction ($8,420.00). | Attribution denied. | `attributable = FALSE`; case moves to `ESCALATED`. | Unrelated partial amount declared full recovery. |
| **FT-03** | Window Expiration (>72h)| Match provider success settling 80 hours after recovery action. | Attribution denied under BR-023. | `attributable = FALSE`; reason: `WINDOW_EXPIRED`. | Payment >72h credited to recovery agent. |
| **FT-04** | Duplicate Attribution | Attempt to link same `provider_event_id` to two recovery cases. | Second insertion rejected by `uq_recovery_evidence_provider_event`. | Second insert rolls back. | Same dollar counted twice in revenue metrics. |
| **FT-05** | Multi-Currency Add | Query summing `amount_minor` across mixed USD and EUR records. | Query enforces `GROUP BY currency`. | Two separate totals returned. | Currencies summed into single meaningless number. |

---

### 2.4 Category 4: Idempotency & Concurrency Defenses

| Test ID | Scenario | Input / Action | Expected Result | Expected Database Effect | Failure Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **IT-01** | Duplicate Idempotency Key| Dispatch attempt with identical `idempotency_key`. | Rejected by `uq_attempt_idempotency_key`. | Second attempt rejected. | Customer charged twice. |
| **IT-02** | Concurrent Case Update | Two worker threads update same `RecoveryCase` simultaneously. | First succeeds; second receives `OptimisticLockError`. | Exactly one state transition recorded. | Lost update or race condition. |
| **IT-03** | In-Flight Recovery Crash | Application crashes after attempt `STARTED`; resumes. | Worker queries provider using cached `idempotency_key`. | Attempt resolved to `SUCCEEDED` without new charge. | Worker initiates second blind charge. |

---

### 2.5 Category 5: Workflow State Machine Tests

| Test ID | Scenario | Input / Action | Expected Result | Expected Database Effect | Failure Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **WT-01** | Valid Transition | Transition case from `DETECTED` $\to$ `ANALYZING`. | Transition accepted. | Case state updated; transition and audit row written. | Valid transition rejected. |
| **WT-02** | Terminal State Lock | Transition case from `RECOVERED` $\to$ `DETECTED`. | Rejected by Invariant INV-004. | Rollback; `InvalidStateTransitionError`. | Closed case reopened. |
| **WT-03** | Max Retry Budget | Attempt to insert 3rd attempt (`sequence_number = 3`). | Rejected by `ck_attempt_sequence_budget`. | Rollback; error raised. | 3rd retry attempt allowed. |
| **WT-04** | Uncertain Result / 504 | Simulator returns 504 timeout on retry. | Case transitions to `VERIFICATION_PENDING`. | Attempt marked `UNCERTAIN`; case locked from retry. | Blind immediate retry executed. |

---

### 2.6 Category 6: Audit Ledger Tests

| Test ID | Scenario | Input / Action | Expected Result | Expected Database Effect | Failure Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **AT-01** | Monotonic Sequence | Insert audit records with sequences `1`, `2`, `3`. | All succeed in order. | Sequenced audit rows committed. | Gaps or out-of-order sequences allowed. |
| **AT-02** | Duplicate Sequence | Attempt to insert two audit events with `(case_id, sequence = 1)`. | Rejected by `uq_audit_case_sequence`. | Rollback. | Duplicate sequence numbers allowed. |
| **AT-03** | Audit Immutability | Execute SQL `UPDATE audit_events SET payload_safe = '{}'`. | Prohibited by permissions / trigger. | Zero rows modified. | Historical audit log altered. |
| **AT-04** | Sensitive Data Leak | Check `payload_safe` across all audit events for 16-digit card PANs. | Zero PANs detected. | Clean compliance scan. | Credit card numbers found in audit payloads. |

---

### 2.7 Category 7: 500-Scenario Evaluation Tests

| Test ID | Scenario | Input / Action | Expected Result | Expected Database Effect | Failure Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EV-01** | Seed Reproducibility | Run 500-scenario batch twice using fixed `seed = 42`. | Identical outcomes generated. | Both runs produce exact same metrics ($980,887 recovered). | Metrics differ across runs. |
| **EV-02** | Metric Calculation | Batch evaluation completes. | Metrics computed correctly (recovery rate: 45.34%). | Zero floating-point rounding errors in summary. | Incorrect KPI calculations. |
