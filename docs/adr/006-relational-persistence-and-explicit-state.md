# ADR-006: Relational persistence with explicit recovery-case state

**Status:** Proposed for Phase 2 review  
**Author:** Karthikeya

## Context

RevenueRescue AI needs durable transactions, customers, recovery cases, attempts, decisions, and audit history. Later workflows must prevent duplicate actions, preserve uncertain outcomes, and resume safely after process restarts. Phase 1 intentionally left persistence unimplemented.

## Decision

Use SQLAlchemy 2.x typed ORM models with Alembic migrations. Use SQLite for local development and isolated tests, while keeping the schema compatible with PostgreSQL-style production deployment. Represent lifecycle state with an explicit `RecoveryCaseState` enum and route all state changes through a domain transition service. Store money as integer minor units with an ISO currency code, use UTC-aware timestamps, and enforce uniqueness and ordering at the database boundary.

## Alternatives considered

A document database was not selected because the core requirements are relational references, uniqueness, ordered attempts, transactional state changes, and append-only audit history. Storing state only in application flags was rejected because it cannot provide durable invariants or reliable recovery. Direct ORM access from API routes was rejected because it would scatter transaction and state rules across the application.

## Consequences

The project gains strong relational integrity, testable repositories, migration history, and a clear state-machine boundary. Phase 2 must add database dependencies, session management, migrations, and more extensive tests. SQLite and PostgreSQL behavior must be checked for constraint and transaction differences before any production-style deployment claim.
