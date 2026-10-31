# RevenueRescueAI — Financial Data Integrity Specification
## Phase 1.2: Monetary Representations, Attribution Safeguards, and Transaction Consistency

**Document Version:** 1.0.0  
**Status:** Approved Financial Architecture  
**Primary Authors:** Senior Financial Systems Engineer, Principal Database Architect  

---

## 1. Monetary Representation & Arithmetic Standards

Financial systems require absolute precision. A financial ledger cannot tolerate "close enough" decimal approximations. 

### 1.1 The Mathematical Danger of Binary Floating-Point (`float` / `double`)
Computers represent numbers using the IEEE 754 floating-point standard (binary base-2). Humans represent currency in decimal (base-10). Most common decimal currency fractions (such as 10 cents, 20 cents, or 70 cents) cannot be represented exactly in binary:
```python
>>> 0.10 + 0.20
0.30000000000000004
>>> (0.10 + 0.20) == 0.30
False
```
In high-volume recovery systems processing thousands of invoices:
- Accumulated micro-cents create unreconciled ledger discrepancies.
- Equality comparisons fail unexpectedly (`amount_recovered == invoice_amount` returns `False`).
- Tax and regulatory audits flag unauthorized rounding variances.

### 1.2 The Integer Minor Unit Standard
RevenueRescueAI mandates that **all monetary values are stored and calculated as 64-bit integers (`BIGINT`) representing minor currency units**:
- **United States Dollar (USD):** 1 dollar = 100 cents. $8,420.50 is stored as `842050`.
- **Euro (EUR):** 1 euro = 100 cents. €120.00 is stored as `12000`.
- **British Pound (GBP):** 1 pound = 100 pence. £50.25 is stored as `5025`.
- **Zero-Decimal Currencies (JPY, KRW):** Stored directly as whole units (¥1,000 is `1000`).

#### Database Check Constraint:
Every column storing monetary amounts enforces:
```sql
CONSTRAINT ck_transaction_amount_nonnegative CHECK (amount_minor >= 0)
```
Negative numbers cannot enter the database under any circumstance.

### 1.3 Multi-Currency Isolation & Arithmetic Safety
It is mathematically meaningless to add $100 USD to €100 EUR. To prevent cross-currency calculation bugs:
1. **Currencies are ISO-4217 Compliant:** Enforced by:
   ```sql
   CONSTRAINT ck_transaction_currency CHECK (length(currency) = 3 AND currency = upper(currency))
   ```
2. **Aggregations Must Group by Currency:** Financial metrics (such as total revenue at risk or total recovered revenue) must always aggregate with `GROUP BY currency`:
   ```sql
   SELECT currency, SUM(amount_minor) AS total_recovered 
   FROM recovery_evidence 
   WHERE attributable = TRUE 
   GROUP BY currency;
   ```
3. **Zero Implicit Conversion:** Automated exchange rate conversion across currencies is strictly prohibited in the core engine.

---

## 2. Recovery Attribution & Anti-Double-Counting Safeguards

One of the most dangerous bugs in revenue recovery software is **false recovery attribution** (taking credit for revenue that was not actually recovered by the system, or counting the same recovered dollar twice).

RevenueRescueAI enforces five strict attribution safeguards:

### Safeguard 1: Prevention of Duplicate Attribution (INV-007)
A provider payment event can only be claimed as evidence for recovery **exactly once**. This is enforced at the database layer via a unique constraint on `recovery_evidence`:
```sql
CONSTRAINT uq_recovery_evidence_provider_event UNIQUE (provider_event_id)
```
If an operator or automated script attempts to link an already-attributed payment event to a second recovery case, the database engine raises an immediate integrity violation.

### Safeguard 2: Unrelated Payment Protection
The system never assumes a successful payment belongs to a recovery case just because the customer is the same. The `OutcomeVerificationService` validates three hard matches before creating evidence:
1. **Customer Match:** `succeeded_event.customer_id == case.customer_id`.
2. **Invoice / Subscription Linkage:** `succeeded_event.invoice_id == failed_event.invoice_id` (or matching transaction metadata).
3. **Exact Amount Match:** `succeeded_event.amount_minor == failed_event.amount_minor`.

### Safeguard 3: Prohibition of Communication Attribution
Under business rule **BR-023**, sending an email or SMS notification (such as a card update request) **never directly recovers revenue**. The case remains in `ACTION_PENDING` until a verified, successful charge transaction is settled by the bank.

### Safeguard 4: Exclusion of Uncertain Results (INV-008)
When a payment provider returns an HTTP 504 Gateway Timeout or network drop, the outcome is classified as `UNCERTAIN`. Under Invariant INV-008:
- The case moves to `VERIFICATION_PENDING`.
- The case is **never marked recovered**.
- The amount is **never added to recovered revenue metrics** until the provider's status inquiry confirms the transaction settled successfully.

### Safeguard 5: Bounded 72-Hour Attribution Window
A successful payment can only be credited to an automated intervention if it settles within **72 hours** (`attribution_window_hours <= 72`) of the recovery attempt. Payments occurring after 72 hours are treated as organic customer renewals or manual out-of-band settlements, preventing inflated recovery metrics.

---

## 3. Transaction Consistency & Partial Failure Handling

### 3.1 Why External Provider Calls Cannot Participate in Database Transactions
A common novice mistake is attempting to wrap an external payment API call inside a database transaction:
```python
# ANTI-PATTERN: DO NOT DO THIS!
with db.begin():
    case.state = "ACTION_PENDING"
    # DANGEROUS: Holding a database connection while waiting 2-5 seconds for an external HTTP call!
    response = stripe_client.charge(amount=842000) 
    case.state = "RECOVERED"
```
**Why this breaks in production:**
1. **Connection Pool Exhaustion:** External HTTP calls take between 500ms and 5,000ms. Holding database connections open while waiting for external networks starves the pool, causing all other API requests to crash with timeouts.
2. **Database Deadlocks:** Holding row-level locks across external HTTP requests blocks other workers and causes cascading deadlocks.
3. **Uncertain State on Crash:** If the database crashes after the external charge succeeded, the database rolls back, but the cardholder was already charged! The system now has an unrecorded orphaned charge.

### 3.2 The Two-Phase Execution Pattern (Planned Attempt Pattern)
RevenueRescueAI decouples database transactions from external side effects using the **Planned Attempt Pattern**:

```
PHASE 1: Plan Attempt (Synchronous Database Transaction)
  1. BEGIN TRANSACTION;
  2. SELECT case FOR UPDATE;  -- Lock case row
  3. Validate retry budget (attempts < 2);
  4. Generate deterministic idempotency_key = "rec_att_<case_id>_<seq>";
  5. INSERT INTO recovery_attempts (status='STARTED', idempotency_key=...);
  6. UPDATE recovery_cases SET state = 'ACTION_PENDING', version = version + 1;
  7. INSERT INTO case_state_transitions (...);
  8. INSERT INTO audit_events (...);
  9. COMMIT;  -- Database lock released immediately!

PHASE 2: Dispatch External Side Effect (External Network Call)
  1. POST /charges (amount=842000, idempotency_key=...);
  2. Await response (with 3.0s timeout);

PHASE 3: Record Outcome (Second Database Transaction)
  1. BEGIN TRANSACTION;
  2. If Succeeded:
       INSERT INTO recovery_evidence (...);
       UPDATE recovery_attempts SET status='SUCCEEDED', provider_reference='ch_8F31';
       UPDATE recovery_cases SET state='RECOVERED', closed_at=NOW();
     If Soft Decline:
       UPDATE recovery_attempts SET status='FAILED';
       UPDATE recovery_cases SET state='RETRY_ELIGIBLE';
     If Timeout (504):
       UPDATE recovery_attempts SET status='UNCERTAIN';
       UPDATE recovery_cases SET state='VERIFICATION_PENDING';
  3. INSERT INTO case_state_transitions (...);
  4. INSERT INTO audit_events (...);
  5. COMMIT;
```
If the server crashes during Phase 2, the recovery attempt is safely recorded as `STARTED` with its `idempotency_key`. When the recovery daemon restarts, it sees the in-flight attempt, queries the provider using the idempotency key, and resolves the case without ever double-charging the customer!

---

## 4. Concurrency Control & Race Condition Defenses

When multiple webhooks, background schedulers, and human operators interact with the recovery queue simultaneously, race conditions must be prevented.

### 4.1 Layer 1: Optimistic Concurrency Control (Version Column)
Every `RecoveryCase` has a `version: int` column. Any update query verifies that the version has not changed since the case was read:
```sql
UPDATE recovery_cases 
SET state = 'RECOVERED', version = version + 1 
WHERE id = :case_id AND version = :expected_version;
```
If another process updated the case in the meantime, `rows_updated == 0`, and the application safely aborts the operation with an `OptimisticLockError`.

### 4.2 Layer 2: Pessimistic Row Locking (`SELECT FOR UPDATE`)
During critical decision and execution sequences, the service issues:
```sql
SELECT * FROM recovery_cases WHERE id = :case_id FOR UPDATE;
```
This forces concurrent transactions attempting to read the same case for mutation to block until the active transaction completes, guaranteeing that retry count checks evaluate true, committed numbers.

### 4.3 Layer 3: Database Uniqueness Boundaries
Even if application-level locks fail, database uniqueness constraints act as an unbreakable brick wall:
- `uq_attempt_idempotency_key` prevents two identical charges.
- `uq_attempt_case_sequence` prevents two attempts from claiming Attempt #1.
- `uq_provider_event` prevents the same webhook from being ingested twice.
