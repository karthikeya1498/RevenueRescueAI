# ADR-004: Model explicit state and append-only audit events

## Context
Scattered flags cannot reliably represent uncertain external outcomes or explain history.

## Decision
Use explicit lifecycle states and append-only audit events for meaningful decisions and actions.

## Alternatives Considered
Deriving state from logs alone was rejected because it complicates queries, recovery, and invariants.

## Consequences
State transitions and audit schemas must be designed together in Phase 2.
