# Database Review and Rewrite Report

**Author:** Karthikeya  
**Scope:** persistence, migrations, transaction boundaries, idempotency, lifecycle state, and workflow durability

## Findings from code tracing

The original database layer had a valid schema foundation but was not fully operational. The application model exports omitted the newly added webhook and evidence models, so Alembic metadata could not see every mapped table. SQLite foreign keys were not explicitly enabled. The webhook endpoint used an in-memory idempotency ledger, which is lost on restart and cannot coordinate multiple workers. Lifecycle sequence numbers were derived from row counts and were not durable. The vertical workflow wrote state transitions but did not persist the agent decision and recovery attempt that caused them. The request-scoped database dependency closed sessions but did not roll back failed requests.

## Rewrite applied

The model export surface now includes every mapped model. SQLite connections enable `PRAGMA foreign_keys=ON` so local tests enforce production-like referential integrity. The database dependency rolls back failed requests before closing sessions. Provider webhook receipts are persisted with a unique `(provider, external_event_id)` constraint, payload hashes, signature state, processing state, and safe payload fields. Concurrent duplicate delivery is handled through a savepoint and the database uniqueness boundary.

Lifecycle transitions now carry a durable per-case sequence number with a unique `(case_id, sequence_number)` constraint. Migration `0003_transition_sequence` backfills existing rows deterministically and works through SQLite batch alteration. The transition service allocates the next sequence from the persisted maximum, validates the state graph, increments the case version, updates timestamps, and writes the transition and audit records together in the caller's transaction.

The vertical workflow now persists the validated agent decision, creates an idempotent planned recovery attempt, links the decision to that attempt, and leaves the case in verification-pending state until provider evidence is processed. A dry-run intent is never marked as succeeded or recovered.

## Transaction contract

A service call performs changes in one session transaction. The API dependency rolls back on unhandled errors. The webhook endpoint commits a verified event receipt only after the event has passed signature and payload validation. Downstream processing should mark the receipt processed in the same transaction as its resulting state and audit changes. External provider calls must be surrounded by an idempotency key and an uncertain-outcome disposition; they must never be retried blindly.

## Verification

The database rewrite was verified with 57 backend tests, Ruff, a fresh Alembic upgrade from an empty SQLite database through `0003_transition_sequence`, metadata registration tests, foreign-key enforcement tests, durable idempotency tests, negative-money constraint tests, terminal transition tests, and persisted decision-to-attempt linkage tests.

## Remaining deployment requirement

A production deployment must use PostgreSQL or another transactional database, run migrations before application startup, configure connection pooling and timeouts, monitor migration state, and use a durable worker for provider-event processing. The local SQLite path is now safe for development and regression tests but is not a substitute for a multi-worker production database.
