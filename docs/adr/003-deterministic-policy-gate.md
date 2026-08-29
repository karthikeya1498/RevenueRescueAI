# ADR-003: Use a deterministic policy gate

## Context
Retry limits, duplicate prevention, arithmetic, and stop conditions require repeatable behavior.

## Decision
Place a deterministic policy gate between reasoning and every customer or financial side effect.

## Alternatives Considered
Prompt-only policy was rejected because prompts cannot guarantee enforcement.

## Consequences
Policies become explicit, testable modules and may reject otherwise plausible agent proposals.
