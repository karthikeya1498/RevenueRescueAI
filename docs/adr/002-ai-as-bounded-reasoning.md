# ADR-002: Treat AI as bounded reasoning

## Context
LLM output is probabilistic and may be malformed or unsafe.

## Decision
AI proposes typed decisions; deterministic validation and policy approve or reject them.

## Alternatives Considered
Allowing the model to call providers directly was rejected because it weakens control, auditability, and provider independence.

## Consequences
The system needs schemas and adapters, but safety responsibilities remain testable.
