# ADR-001: Incremental phase-based architecture

## Context
Agentic financial workflows have high coupling and safety risk.

## Decision
Build in explicit phases, with a reviewed gate before each phase.

## Alternatives Considered
A single end-to-end prototype would demonstrate more behavior quickly but would hide unsafe coupling and make verification ambiguous.

## Consequences
Progress is slower initially, but every milestone is runnable, explainable, and easier to review.
