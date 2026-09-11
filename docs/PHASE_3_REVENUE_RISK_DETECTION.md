# Phase 3: Revenue Risk Detection

**Project:** RevenueRescue AI  
**Author:** Karthikeya  
**Status:** Implemented with deterministic rules  
**Rule version:** `phase3.v1`

## Purpose

Phase 3 detects revenue-at-risk transactions using persisted transaction facts and explicit rules. The detector is deterministic, provider-independent, and auditable. It does not use an LLM, send communications, invoke payment tools, or select a recovery action.

## Rules

| Transaction fact | Detection result | Severity | Reason code |
|---|---|---:|---|
| `failed` | At risk immediately | High | `payment_failed` |
| `pending` and older than 24 hours by default | At risk | Medium | `payment_pending_too_long` |
| `unknown` | At risk | Medium | `payment_status_unknown` |
| `succeeded` | Not at risk; success protected | None | `transaction_already_succeeded` |
| `created`, `authorized`, `cancelled`, or `refunded` | Not at risk | None | `transaction_not_at_risk` |
| Detected risk without a loaded customer | Still at risk, with context warning | Rule severity | `missing_customer_context` |

The pending threshold and detector rule version are configurable through `DetectorConfig`, while the default behavior remains deterministic and explicit.

## Result contract

`RiskDetectionResult` contains the transaction identifier, boolean risk flag, severity, ordered reason codes, evaluation timestamp, rule version, and recommended initial state. The recommended state is `detected` only when risk is present. It is a classification result, not an instruction to perform a recovery action.

## Persistence integration

`RiskCaseService.detect_and_create_case()` persists one `RecoveryCase` for a detected event. The stable key is derived from provider and external transaction identity. Repeated delivery of the same event returns the existing case with `created=False`, preventing duplicate cases without relying on AI judgment.

Each created case stores the rule version, severity, reason codes, and deterministic source marker in safe metadata. Later state transitions must use the Phase 2 transition service rather than direct mutation.

## Verification

Phase 3 tests cover failed payments, stale pending payments, unknown provider statuses, success protection, missing context, batch ordering, and duplicate-event idempotency. No external provider is contacted and no financial action is executed.
