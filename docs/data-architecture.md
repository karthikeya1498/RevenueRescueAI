# RevenueRescueAI — Data and Financial Architecture
## Phase 1.1: Financial Data Precision, Persistence Boundaries, and Consistency

**Document Version:** 1.0.0  
**Status:** Approved Data Architecture  
**Primary Authors:** Principal Database Architect, Senior Fintech Engineer, Security Architect  

---

## 1. Executive Summary & Core Financial Philosophy

In financial software engineering, data architecture is not merely about storing tables; it is about guaranteeing **absolute mathematical precision, transaction consistency, and legal auditability**. 

A single rounding error, a race condition that double-charges a cardholder, or an unverifiable recovery claim can destroy customer trust and incur severe regulatory fines.

RevenueRescueAI establishes three inviolable data architecture tenets:
1. **Integer Minor Units Only:** Ordinary floating-point arithmetic is strictly prohibited across all data models, schemas, and calculations.
2. **ACID Transactional Boundaries:** State transitions, financial attempt records, and audit log entries must succeed or fail as a single atomic unit.
3. **Verified Attribution Ledger:** Revenue is never counted as "recovered" without immutable relational proof linked to a specific banking event.

---

## 2. Monetary Precision & Currency Representation

### 2.1 Why Floating-Point Math (`float` / `double`) is Unacceptable (Beginner Explanation)
Computers represent numbers in base-2 (binary). Most human currencies are base-10 (decimal). Just as $1/3$ cannot be represented cleanly in base-10 ($0.33333...$), fractions like $0.10$ or $0.20$ cannot be represented cleanly in binary floating-point.

In Python or JavaScript:
```python
>>> 0.1 + 0.2
0.30000000000000004  # Off by a fractional fraction!
>>> (0.1 + 0.2) == 0.3
False
```
In a financial recovery system handling thousands of transactions, these tiny micro-cents accumulate into material reconciliation discrepancies, audit failures, and broken ledger balances.

### 2.2 The Integer Minor Unit Standard
RevenueRescueAI represents every monetary value as a **64-bit integer minor unit** (`amount_minor`):
- **1 USD** ($1.00) is stored as `100` (cents).
- **$8,420.50 USD** is stored as `842050`.
- **Zero-decimal currencies** (e.g., Japanese Yen `JPY`) store the face value directly (e.g., ¥1,000 is stored as `1000`).

**Database Check Constraint:**
Every table storing monetary amounts enforces:
```sql
CheckConstraint("amount_minor >= 0", name="ck_transaction_amount_nonnegative")
```
Negative amounts are rejected at the database engine boundary.

### 2.3 ISO-4217 Currency Representation
Currencies are stored as uppercase, exact 3-character string codes adhering to the international ISO-4217 standard (`USD`, `EUR`, `GBP`, `CAD`, `AUD`):
```sql
CheckConstraint("length(currency) = 3 AND currency = upper(currency)", name="ck_transaction_currency")
```
Cross-currency arithmetic without explicit exchange-rate conversion is strictly prohibited.

---

## 3. Data Ownership & Domain Boundaries

To prevent tight coupling, every entity is owned by a single domain module. Other modules may read these records via repositories or service interfaces, but only the owner may issue mutations:

| Domain Entity | Owning Module | Allowed Writers | Read Consumers | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `Customer` | Ingestion / Account Domain | Ingestion Service | Workflow, Policy, UI | Master customer identity and account status |
| `Transaction` | Ingestion Domain | Ingestion Service | Risk Engine, Verification | Immutable record of provider payment events |
| `ProviderWebhookEvent` | Ingestion Engine | Webhook Receiver | Deduplication Engine | Idempotent receipt of external provider events |
| `RecoveryCase` | Recovery Workflow Engine | Workflow FSM | Policy, AI, Analytics, UI | Core recovery lifecycle state machine |
| `CaseStateTransition` | Recovery Workflow Engine | Workflow FSM | Audit, UI | Sequential history of case state changes |
| `RecoveryAttempt` | Tool Execution / Scheduler | Tool Executor | Policy, Audit, Simulator | Record of physical payment recovery operations |
| `AgentDecision` | AI & Policy Engine | Agent & Policy Gate | Workflow, Audit, UI | Proposed and validated AI action records |
| `AuditEvent` | Audit Service | Audit Service Only | Compliance, UI, Analytics | Immutable, append-only chronological event ledger |
| `RecoveryEvidence` | Verification Service | Verification Service | Analytics, Workflow, UI | Verified proof of recovery attribution (<72h) |

---

## 4. Transaction Boundaries & ACID Guarantees

In RevenueRescueAI, every state mutation is wrapped in an explicit ACID transaction boundary. We enforce:

### 4.1 Atomicity of Side Effects
A state transition must never occur without its corresponding audit event and attempt record:
```
BEGIN TRANSACTION;
  1. UPDATE recovery_cases SET state = 'ACTION_PENDING', version = version + 1 WHERE id = :id;
  2. INSERT INTO recovery_attempts (case_id, sequence_number, idempotency_key, status) VALUES (...);
  3. INSERT INTO case_state_transitions (case_id, from_state, to_state, sequence_number) VALUES (...);
  4. INSERT INTO audit_events (case_id, sequence_number, event_type, correlation_id) VALUES (...);
COMMIT;
```
If the database connection drops or a constraint fails at Step 4, the entire transaction rolls back. The case state remains completely unchanged. There are **zero partial updates**.

### 4.2 Referential Integrity & Cascade Rules
- **Customers and Transactions cannot be deleted** while recovery cases exist (`ondelete="RESTRICT"`). This prevents accidental data loss if an operator cleans up accounts.
- **Children of RecoveryCase cascade on test cleanup** (`ondelete="CASCADE"` for attempts, decisions, transitions, and audit events), ensuring clean lifecycle isolation in automated test fixtures.

---

## 5. Concurrency Control & Race Condition Prevention

In high-volume recovery, two webhooks or an automated scheduler and a human operator could attempt to act on the same case simultaneously. RevenueRescueAI prevents race conditions via three layers of defense:

### 5.1 Optimistic Locking via Version Number
The `RecoveryCase` table maintains a `version: Mapped[int]` column:
```python
# When updating a case:
stmt = (
    update(RecoveryCase)
    .where(RecoveryCase.id == case_id, RecoveryCase.version == current_version)
    .values(state=new_state, version=current_version + 1)
)
```
If another process updated the case in the millisecond between reading and writing, `rows_affected == 0`, and the application raises an `OptimisticLockError`, safely aborting the conflicting update.

### 5.2 Pessimistic Row Locking (`SELECT FOR UPDATE`)
When executing a financial side effect (e.g., charging a card), the workflow engine issues a row-level lock on the `RecoveryCase`:
```sql
SELECT * FROM recovery_cases WHERE id = :case_id FOR UPDATE;
```
This forces concurrent worker threads to wait until the first transaction completes, guaranteeing that retry limits and budget checks are evaluated against the true real-time state.

---

## 6. Idempotency Architecture (INV-006)

Financial systems must guarantee that repeating an operation produces the identical result without repeating the side effect.

### 6.1 Webhook Ingestion Idempotency
Provider webhooks are protected by a unique composite constraint on `provider_webhook_events`:
```sql
UniqueConstraint("provider", "external_event_id", name="uq_provider_event")
```
If Stripe or the simulator delivers the same event twice, the second `INSERT` raises an integrity error; the detector catches it and returns the cached HTTP 200 response without triggering a duplicate workflow.

### 6.2 Recovery Attempt Idempotency
Every charge executed against a provider carries a deterministic `idempotency_key`:
```python
idempotency_key = f"rec_attempt_{case_id}_{sequence_number}"
```
Enforced in the database by:
```sql
UniqueConstraint("idempotency_key", name="uq_attempt_idempotency_key")
```
It is physically impossible for the database to register two recovery attempts with the same idempotency key.

---

## 7. Immutable Audit Ledger (INV-005)

The `audit_events` and `case_state_transitions` tables are **strictly append-only**:
- **Zero UPDATE or DELETE:** The application code contains zero SQL `UPDATE` or `DELETE` statements targeting audit tables.
- **Monotonic Sequence Numbers:** Every event for a case is assigned a strictly increasing integer sequence number (`1, 2, 3, ...`) enforced by:
```sql
UniqueConstraint("case_id", "sequence_number", name="uq_audit_case_sequence")
```
If an attempt is made to insert an out-of-order audit event, the unique constraint rejects the transaction.
- **Correlation IDs:** Every log entry carries an end-to-end `correlation_id` (UUIDv4) passed from the original inbound webhook through the API, policy, tool, and database layers, allowing complete distributed tracing.

---

## 8. Outcome Verification & Attribution Architecture (INV-007)

Revenue is never recorded as "recovered" based on optimistic expectations. The `RecoveryEvidence` table enforces verifiable attribution:

1. **Exact Failed Transaction Linkage:** Must point to the specific `failed_transaction_id`.
2. **Matching Provider Success:** Must capture the `successful_transaction_id` and provider reference.
3. **Exact Minor Unit Match:** The recovered `amount_minor` must match the original failed `amount_minor`.
4. **Attribution Window Constraint:** The recovered payment must have settled within **72 hours** (`attribution_window_hours <= 72`) of the recovery intervention.
5. **Single Attribution Rule:** A single provider event can only be attributed once:
```sql
UniqueConstraint("provider_event_id", name="uq_recovery_evidence_provider_event")
```
