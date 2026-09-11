# Changelog

## 0.6.0 — Phase 9 dashboard and frontend command center

Added the visual command center, recovery queue, Evaluation Lab, transaction-level agent traces, structured trace drawer, responsive navigation, inspected 500-scenario report metrics, and production frontend styling.

## 0.5.0 — Phase 8 evaluation engine

Added deterministic batch simulations, reproducible scenario generation, policy and resilience outcome simulation, recovered-revenue metrics, case recovery rates, action accuracy, safety rates, failure and escalation counts, verification reporting, JSON report generation, and an evaluation CLI.

## 0.4.0 — Phase 6 safety and Phase 7 resilience

Added deterministic retry limits, terminal-state and success protection, duplicate idempotency prevention, uncertainty escalation, timeout and API-failure classification, bounded exponential backoff, one-shot resilient execution, and safe resume envelopes. No blind side-effect retries were added.

## 0.3.0 — Phase 4–5 agent brain and controlled tools

Added provider-independent structured agent decisions, strict allow-list validation, an OpenAI-compatible JSON-schema adapter using `gpt-5-mini`, a controlled tool registry, dry-run recovery-intent and escalation tools, and boundary tests. No live financial execution or customer notification was added.

## 0.2.0 — Phase 3 deterministic revenue-risk detection

Added deterministic transaction-risk classification, explicit risk reason codes and severity, stale-pending detection, success protection, missing-context reporting, idempotent recovery-case creation, and automated Phase 3 tests. No AI reasoning or financial action was added.

## 0.1.0 — Phase 1 foundation

Added repository structure, FastAPI health service, typed configuration, logging baseline, React/Vite/TypeScript shell, tests, environment hygiene, architecture documentation, future-state contracts, and five ADRs. No recovery behavior was implemented.
