# RevenueRescueAI — Database Migration Architecture & Revision Log

## 1. Executive Summary

In professional backend engineering, database schemas are never altered through manual ad-hoc SQL statements executed directly against production databases. Every schema evolution must be version-controlled, reproducible, peer-reviewed, and testable.

RevenueRescueAI uses **Alembic** (the standard migration framework for SQLAlchemy) to manage all Data Definition Language (DDL) operations.

---

## 2. Migration Execution Architecture

```
[ Developer / CI Pipeline ] ──► python -m alembic upgrade head
                                         │
                                         ▼
                               [ alembic.ini ]
                                         │
                                         ▼
                          [ backend/migrations/env.py ]
                                         │
                         ┌───────────────┴───────────────┐
                         ▼                               ▼
                 [ SQLite Dialect ]             [ PostgreSQL Dialect ]
              Non-transactional DDL             ACID Transactional DDL
              Table batch alterations           Native ALTER TABLE statements
```

---

## 3. Chronological Migration Revision History

| Revision ID | Description & Applied Schema Changes | Down Revision | Tables / Columns Altered |
| :--- | :--- | :--- | :--- |
| **`0001_phase2_core_data`** | Initial Phase 2 core data and state tables. | `None` (Base) | Creates `customers`, `transactions`, `recovery_cases`, `recovery_attempts`, `agent_decisions`, `audit_events`, `case_state_transitions`. |
| **`0002_verified_recovery_intelligence`** | Adds verified provider event and recovery evidence tables. | `0001_phase2_core_data` | Creates `provider_webhook_events` (for HMAC replay safety) and `recovery_evidence` (for 72h settlement proof). |
| **`0003_transition_sequence`** | Adds monotonic sequence numbers to state transitions. | `0002_verified_recovery_intelligence` | Adds column `sequence_number` to `case_state_transitions` and creates `UNIQUE(case_id, sequence_number)`. |

---

## 4. Detailed Migration Specifications

### Migration 1: `0001_phase2_core_data.py`
- **File:** [`backend/migrations/versions/0001_phase2_core_data.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/migrations/versions/0001_phase2_core_data.py)
- **Key Operations:**
  - Instantiates enum types (`customer_status`, `transaction_status`, `recovery_case_state`, `recovery_attempt_status`, `action_type`, `decision_validation_status`, `actor_type`).
  - Sets up foreign keys with `RESTRICT` on root entities and `CASCADE` on child entities.
  - Adds check constraint `amount_minor >= 0` on `transactions`.
  - Creates compound indexes on `(status, occurred_at)` and `(state, last_state_changed_at)`.

### Migration 2: `0002_verified_recovery_intelligence.py`
- **File:** [`backend/migrations/versions/0002_verified_recovery_intelligence.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/migrations/versions/0002_verified_recovery_intelligence.py)
- **Key Operations:**
  - Creates `provider_webhook_events` with unique constraint `(provider, external_event_id)` to reject replayed webhooks.
  - Creates `recovery_evidence` with unique constraint on `provider_event_id` and check constraint enforcing non-negative minor units.
  - Creates index on `failed_transaction_id` for fast settlement matching.

### Migration 3: `0003_transition_sequence.py`
- **File:** [`backend/migrations/versions/0003_transition_sequence.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/migrations/versions/0003_transition_sequence.py)
- **Key Operations:**
  - Uses `op.batch_alter_table` to remain 100% compatible with SQLite's table-rebuilding limitations.
  - Populates existing rows with sequential numbers.
  - Enforces `NOT NULL` and `UniqueConstraint("case_id", "sequence_number")`.

---

## 5. Standard Migration CLI Commands

```powershell
# Check current migration revision in active database
python -m alembic current

# View complete revision history
python -m alembic history --verbose

# Apply all pending migrations to the latest revision (head)
python -m alembic upgrade head

# Roll back the single most recent migration
python -m alembic downgrade -1

# Create a new version-controlled migration script
python -m alembic revision -m "add_new_column_or_table"
```
