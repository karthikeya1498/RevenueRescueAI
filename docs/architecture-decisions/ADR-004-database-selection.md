# ADR-004: Database Selection — PostgreSQL 16 & SQLite Dual-Dialect

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Principal Database Architect, Senior Fintech Engineer  

---

## 1. Context
Financial recovery systems demand strict ACID guarantees, relational referential integrity, optimistic and pessimistic row-level locking, and append-only audit log persistence.

## 2. Problem
Which persistence technology guarantees mathematical precision, zero data loss, and seamless local developer experience?

## 3. Options Considered
1. **MongoDB:** Document-oriented NoSQL database.
2. **PostgreSQL 16 Engine with SQLite Dual-Dialect (via SQLAlchemy 2.0):** Relational ACID engine in production containers, with SQLite for zero-dependency local unit testing.
3. **MySQL 8:** Relational database with InnoDB engine.
4. **DynamoDB:** Cloud-native distributed key-value store.

## 4. Decision
We choose **PostgreSQL 16 as the production/staging database**, paired with an **SQLite 3 dual-dialect configuration for local test isolation**, orchestrated via **SQLAlchemy 2.0**.

## 5. Reasons
- **ACID & Referential Integrity:** Relational foreign keys with `ondelete="RESTRICT"` prevent orphaned financial records. A customer cannot be deleted while an active recovery case or transaction exists.
- **Strict Check Constraints:** Native check constraints (`amount_minor >= 0`, `length(currency) == 3`) reject corrupt data at the storage layer.
- **Concurrency Protection:** PostgreSQL provides `SELECT FOR UPDATE` and unique constraints (`uq_attempt_idempotency_key`) to eliminate race conditions and double charges.
- **Fast Test Execution:** Developers can run the entire 57-test suite against SQLite in under 8 seconds with zero external container dependencies, while Docker Compose provisions full PostgreSQL 16 for staging.

## 6. Trade-offs & Consequences
- **Positive:** Complete transactional safety, zero data drift, easy relational joins between cases, attempts, and evidence.
- **Negative:** Schema migrations require explicit Alembic version scripts (already implemented in `backend/migrations`).

## 7. Reconsideration Conditions
Re-evaluate if historical audit logs exceed 100 terabytes, at which point an append-only analytical data warehouse (e.g., ClickHouse or Snowflake) can be introduced for cold audit archiving.
