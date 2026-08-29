# ADR-005: Keep providers behind adapters

## Context
LLM and payment vendors change, and the system must be testable without live providers.

## Decision
Expose provider-neutral interfaces and isolate vendor-specific adapters behind them.

## Alternatives Considered
Embedding one vendor SDK throughout services was rejected due to lock-in and difficult tests.

## Consequences
Adapters add a small abstraction cost but enable substitution, fakes, and controlled credentials.
