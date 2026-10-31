# RevenueRescueAI — Transaction Boundaries and Consistency Design

## 1. Executive Summary & The Dual-World Problem

In financial software engineering, one of the most dangerous rookie mistakes is assuming that an ACID database transaction can wrap an external payment API call.

```
       ❌ DANGEROUS ROOKIE DESIGN:
       BEGIN TRANSACTION;
         UPDATE cases SET state = 'PROCESSING';
         result = call_stripe_api();  <-- If this times out or server crashes here,
         UPDATE cases SET state = 'RECOVERED'; DB locks hang, or DB rolls back,
       COMMIT;                        BUT STRIPE CHARGED THE CARD!
```

If the database rolls back after an external payment gateway charges a customer's card, **the card was charged, but the database has no record of the charge.** The system might then retry the operation later, charging the customer twice!

RevenueRescueAI solves this with the **Two-Phase Planned Attempt Pattern with Idempotent External Settlement & Asynchronous Reconciliation**.

---

## 2. Transaction vs. Side-Effect Separation

The system divides all operations into two strict categories:
1. **Internal ACID Database Transactions:** Fast, synchronous, local relational mutations in PostgreSQL. Must complete in `< 20ms`.
2. **External Network Side Effects:** Outbound HTTP calls to LLM APIs, Payment Simulator endpoints, Stripe gateways, or email dispatchers. Prone to latency, packet loss, socket drops, and 504 timeouts.

### The Non-Negotiable Rule:
> **No database transaction shall ever remain open while awaiting an external network response.**

---

## 3. The Two-Phase Planned Attempt Pattern

To guarantee safety and prevent double-charging, recovery execution is partitioned into three distinct phases:

```
[ Phase 1: Pre-Execution Lock (DB Tx) ]
                   │
                   ▼ (DB Connection Closed)
[ Phase 2: External HTTP Side-Effect (Network Call) ]
                   │
                   ▼ (New DB Connection Acquired)
[ Phase 3: Post-Execution Settlement (DB Tx) ]
```

---

### Detailed Walkthrough of the Three Phases

#### Phase 1: Pre-Execution Lock (Synchronous ACID Transaction #1)
- **Database Connection Acquired.**
- **Transaction Starts:** `BEGIN TRANSACTION;`
- **Actions:**
  1. Acquire pessimistic row lock on recovery case:
     ```sql
     SELECT * FROM recovery_cases WHERE id = :case_id FOR UPDATE;
     ```
  2. Verify invariant preconditions:
     - `case.state == 'POLICY_APPROVED'`
     - `case.attempt_count < 2`
  3. Generate deterministic UUIDv5 idempotency key:
     `idempotency_key = uuid5("revrescue", case.id + "-" + (case.attempt_count + 1))`
  4. Create a "Planned" attempt record:
     ```sql
     INSERT INTO recovery_attempts (
         id, case_id, attempt_number, idempotency_key, status, initiated_at
     ) VALUES (
         gen_random_uuid(), :case_id, :next_attempt_num, :idempotency_key, 'IN_PROGRESS', NOW()
     );
     ```
  5. Transition case state:
     ```sql
     UPDATE recovery_cases 
     SET state = 'ACTION_EXECUTING', updated_at = NOW() 
     WHERE id = :case_id;
     ```
  6. Insert synchronous audit row:
     ```sql
     INSERT INTO audit_events (case_id, event_type, old_state, new_state)
     VALUES (:case_id, 'ATTEMPT_DISPATCH_PLANNED', 'POLICY_APPROVED', 'ACTION_EXECUTING');
     ```
- **Transaction Ends:** `COMMIT;`
- **State Guarantee:** The database now authoritatively reflects that an attempt is in-flight. No concurrent worker can touch this case.

---

#### Phase 2: External HTTP Side Effect (Outside DB Transaction)
- **Zero Database Locks Held.**
- Outbound HTTP POST to Payment Simulator / Stripe:
  ```http
  POST /v1/simulator/charges HTTP/1.1
  Host: api.revenuerescue.internal
  Idempotency-Key: idemp_case_99214a_att_1
  Content-Type: application/json

  {
    "amount_cents": 4500,
    "currency": "USD",
    "customer_token": "cust_live_4491"
  }
  ```
- **Possible Network Outcomes:**
  - **Outcome 2A (Clean Response):** Returns HTTP 200 with JSON payload (`{"status": "succeeded", "transaction_id": "tx_sim_8812"}`).
  - **Outcome 2B (Clean Decline):** Returns HTTP 200 with JSON decline (`{"status": "failed", "decline_code": "insufficient_funds"}`).
  - **Outcome 2C (Network Disconnect / 504 Timeout):** Socket hangs up or 15-second client timeout triggers.

---

#### Phase 3: Post-Execution Settlement (Synchronous ACID Transaction #2)
- **New Database Connection Acquired.**
- **Transaction Starts:** `BEGIN TRANSACTION;`
- **Actions based on Phase 2 Outcome:**

##### If Clean Success (Outcome 2A):
1. Insert authoritative proof in `recovery_evidence`:
   ```sql
   INSERT INTO recovery_evidence (case_id, attempt_id, provider_transaction_id, verified_amount_cents, verified_at)
   VALUES (:case_id, :attempt_id, :tx_id, 4500, NOW());
   ```
2. Update attempt:
   ```sql
   UPDATE recovery_attempts 
   SET status = 'SUCCEEDED', finished_at = NOW(), raw_response_hash = :hash 
   WHERE id = :attempt_id;
   ```
3. Update case to terminal `RECOVERED`:
   ```sql
   UPDATE recovery_cases 
   SET state = 'RECOVERED', recovered_amount_cents = 4500, closed_at = NOW() 
   WHERE id = :case_id;
   ```
4. Insert audit record:
   ```sql
   INSERT INTO audit_events (case_id, event_type, old_state, new_state)
   VALUES (:case_id, 'RECOVERY_VERIFIED_SUCCESS', 'ACTION_EXECUTING', 'RECOVERED');
   ```

##### If Clean Decline (Outcome 2B):
1. Update attempt:
   ```sql
   UPDATE recovery_attempts 
   SET status = 'FAILED', failure_code = :decline_code, finished_at = NOW() 
   WHERE id = :attempt_id;
   ```
2. Increment attempt count and branch:
   - If retries remain: `state = 'RETRY_SCHEDULED'`, `next_retry_at = NOW() + 24 hours`.
   - If retries exhausted: `state = 'FAILED'`, `closed_at = NOW()`.
3. Insert audit record for failure.

##### If Network Timeout / Dropped Socket (Outcome 2C):
1. Update attempt:
   ```sql
   UPDATE recovery_attempts SET status = 'UNCERTAIN' WHERE id = :attempt_id;
   ```
2. Update case to `VERIFICATION_PENDING`:
   ```sql
   UPDATE recovery_cases SET state = 'VERIFICATION_PENDING' WHERE id = :case_id;
   ```
3. Insert audit record:
   ```sql
   INSERT INTO audit_events (case_id, event_type, old_state, new_state)
   VALUES (:case_id, 'TIMEOUT_OUTCOME_UNCERTAIN', 'ACTION_EXECUTING', 'VERIFICATION_PENDING');
   ```
- **Transaction Ends:** `COMMIT;`

---

## 4. Crash Recovery and Reconciliation Strategy

### What Happens if the Server Crashes During Phase 2?
If the RevenueRescueAI application server loses power or is killed (`SIGKILL`) precisely while waiting for Stripe's HTTP response:
1. When the server boots back up, the database still has:
   - `recovery_cases.state = 'ACTION_EXECUTING'`
   - `recovery_attempts.status = 'IN_PROGRESS'`
2. **The Stale Attempt Sweeper (Background Daemon):**
   - Every 5 minutes, a periodic job runs:
     ```sql
     SELECT id, case_id, idempotency_key 
     FROM recovery_attempts 
     WHERE status = 'IN_PROGRESS' AND initiated_at < NOW() - INTERVAL '5 minutes';
     ```
   - For every stale attempt found, the sweeper marks the case `VERIFICATION_PENDING` and triggers an idempotent inquiry against the payment gateway:
     ```http
     GET /v1/simulator/charges?idempotency_key=idemp_case_99214a_att_1
     ```
   - If the gateway processed the charge: The system records success and closes the case.
   - If the gateway has no record of the charge: The system safely marks the attempt abandoned and resets the case.

---

## 5. Audit Logging Consistency Guarantee

A recurring risk in enterprise systems is when audit logs are sent to an external logging aggregator (like Kafka or Datadog) asynchronously. If the application crashes before pushing to Kafka, the state change happened, but the audit trail was lost!

### RevenueRescueAI Solution:
**Co-located Relational Audit Trails:**
- The `audit_events` table resides inside the *same* PostgreSQL database as the business entities.
- Every state mutation and its corresponding audit log row are executed within the **exact same ACID database transaction**.
- **Guarantee:** It is physically impossible for a case to change states without generating an audit row. If the transaction commits, both exist; if the transaction rolls back, neither exists.

---

## 6. Minimal Architecture MVP Justification

To keep the system robust without introducing overwhelming infrastructure complexity for a student developer:
- **No Heavy Distributed Sagas or Kafka Queues:** An external Kafka or Temporal cluster is unnecessary and adds significant operational overhead.
- **Relational Polling via Indexes:** Using indexed timestamp columns (`next_retry_at`, `initiated_at`) and PostgreSQL row locks (`SELECT FOR UPDATE SKIP LOCKED`) provides bulletproof worker coordination and exactly-once execution guarantees using standard database features.
