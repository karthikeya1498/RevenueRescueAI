# RevenueRescueAI — Database Indexing Strategy
## Phase 1.2: Query Access Patterns, Index Justifications, and Write-Cost Analysis

**Document Version:** 1.0.0  
**Status:** Approved Indexing Architecture  
**Primary Authors:** Principal Database Architect, Senior Performance Engineer  

---

## 1. Indexing Principles & Trade-off Philosophy

Indexes in relational databases speed up `SELECT` queries by maintaining balanced tree (B-Tree) search structures. However, **every additional index incurs a write penalty on `INSERT` and `UPDATE` operations**, because the database engine must synchronously update both the underlying table row and all attached index trees.

RevenueRescueAI establishes three indexing principles:
1. **Never Index Without a Justified Query Pattern:** Every index must directly support a real operational API endpoint, background worker query, or dashboard view.
2. **Prefer Composite Indexes for Multi-Column Filtering:** Filter combinations like `(state, last_state_changed_at)` are indexed together rather than indexing columns separately.
3. **Protect Write Throughput:** For high-velocity append-only tables (like `audit_events`), indexes are restricted to primary lookup paths to maintain $<10$ms insertion speeds.

---

## 2. Core Query Access Patterns & Index Matrix

The following table evaluates the 11 essential database access patterns across the recovery lifecycle:

| Query Pattern ID | Business Operation & Target Table | Filter / Sort Criteria | Proposed Index Specification | Index Type | Write Overhead | MVP Necessity |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **QP-01** | **Payment Ingress Lookup**<br>`transactions` | Lookup by external gateway transaction ID | `uq_transaction_provider_external`<br>`(provider, external_transaction_id)` | Unique Composite B-Tree | Minimal (enforces idempotency) | **MANDATORY** |
| **QP-02** | **Live Recovery Queue**<br>`recovery_cases` | Filter by active states (`detected`, `action_pending`), sort by last update | `ix_recovery_case_state_changed`<br>`(state, last_state_changed_at)` | Composite B-Tree | Low | **MANDATORY** |
| **QP-03** | **Case Detail Inspection**<br>`recovery_cases` | Lookup case by UUID primary key | `pk_recovery_cases`<br>`(id)` | Unique Primary Key | Zero (automatic) | **MANDATORY** |
| **QP-04** | **Case Attempt History**<br>`recovery_attempts` | Fetch attempts for a case in sequence order | `ix_attempt_case_sequence`<br>`(case_id, sequence_number)` | Unique Composite B-Tree | Low | **MANDATORY** |
| **QP-05** | **Agent Journey Audit Trail**<br>`audit_events` | Fetch audit logs for a case ordered by sequence | `ix_audit_case_sequence`<br>`(case_id, sequence_number)` | Unique Composite B-Tree | Low | **MANDATORY** |
| **QP-06** | **Customer Case Lookup**<br>`recovery_cases` | Find all cases belonging to a customer | `ix_recovery_case_customer`<br>`(customer_id)` | Single-Column B-Tree | Low | **MANDATORY** |
| **QP-07** | **Webhook Idempotency Filter**<br>`provider_webhook_events` | Check if webhook event was already ingested | `uq_provider_event`<br>`(provider, external_event_id)` | Unique Composite B-Tree | Minimal (enforces deduplication)| **MANDATORY** |
| **QP-08** | **Recovered Revenue KPI**<br>`recovery_evidence` | Sum confirmed recovered amounts over date window | `ix_recovery_evidence_verified_amount`<br>`(attributable, verified_at, amount_minor)`| Composite Covering Index | Low | **MANDATORY** |
| **QP-09** | **Unprocessed Webhook Poll**<br>`provider_webhook_events` | Daemon finding unprocessed webhook events | `ix_webhook_unprocessed`<br>`(processed) WHERE processed = FALSE` | Partial B-Tree Index | Negligible | Optional (Defer)|
| **QP-10** | **Pending Verification Sweep**<br>`recovery_cases` | Daemon finding cases in `verification_pending` | Handled by `ix_recovery_case_state_changed` | Composite (Covered by QP-02) | None (reused) | **MANDATORY** |
| **QP-11** | **Evaluation Benchmark Results**<br>`evaluation_results` | Fetch all scenario results for an evaluation run | `ix_eval_results_run`<br>`(evaluation_run_id)` | Single-Column B-Tree | Minimal | **MANDATORY** |

---

## 3. In-Depth Justifications for Critical Indexes

### 3.1 Composite Index: `ix_recovery_case_state_changed (state, last_state_changed_at)`
- **Query Supported:**
  ```sql
  SELECT * FROM recovery_cases 
  WHERE state = 'action_pending' 
  ORDER BY last_state_changed_at DESC 
  LIMIT 50;
  ```
- **Why It Is Critical:** The frontend Command Center and Recovery Queue query this view constantly. Without this composite index, PostgreSQL must execute a full-table sequential scan, reading every row and sorting in memory. With this index, the query performs an index seek directly to the matching state, returning rows in pre-sorted order in $<2$ms.

### 3.2 Covering Index for Financial Analytics: `(attributable, verified_at, amount_minor)`
- **Query Supported:**
  ```sql
  SELECT SUM(amount_minor) FROM recovery_evidence 
  WHERE attributable = TRUE AND verified_at >= :start_date;
  ```
- **Why It Is Critical:** This is an **Index-Only Scan (Covering Index)**. Because `amount_minor` is included in the index leaf pages, PostgreSQL can calculate the sum directly from the index tree without fetching the actual table heap pages from disk, providing sub-millisecond dashboard KPI card rendering.

### 3.3 Unique Composite Key: `uq_attempt_idempotency_key (idempotency_key)`
- **Query Supported:**
  ```sql
  INSERT INTO recovery_attempts (idempotency_key, ...) VALUES (...);
  ```
- **Why It Is Critical:** Enforces **Invariant INV-006 (Strict Idempotency)**. It prevents two concurrent workers from executing duplicate charges against the payment provider.

---

## 4. Index Maintenance & Performance Monitoring

1. **Zero Redundant Indexes:** Single-column indexes on `case_id` are avoided where a composite index on `(case_id, sequence_number)` already exists (PostgreSQL can use the left prefix of composite indexes for `case_id` lookups).
2. **Partial Indexes for Flags:** For boolean flags that are predominantly true (such as `processed`), we use partial indexes (`WHERE processed = FALSE`) to keep the index size tiny (<1MB).
3. **Query Optimization Standard:** All queries executed by backend routes must demonstrate index usage via `EXPLAIN (ANALYZE, BUFFERS)` during Phase 1.3 contract testing.
