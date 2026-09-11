# Phase 6: Safety & Policy Layer

**Project:** RevenueRescue AI  
**Author:** Karthikeya  
**Policy version:** `phase6.v1`

## Purpose

The safety policy is a deterministic gate between agent proposals and controlled tools. It does not trust model confidence, execute actions, or contact providers. It evaluates the current case state, transaction status, prior attempts, idempotency history, and explicit policy configuration.

## Enforced invariants

| Invariant | Enforcement |
|---|---|
| Retry budget | Default maximum of two payment-retry attempts; exhausted budget escalates |
| Duplicate prevention | Reused idempotency keys are rejected |
| Success protection | A succeeded transaction produces a stop decision for any recovery action |
| Terminal protection | Recovered, stopped, and closed cases cannot receive actions |
| State gating | Payment retries are permitted only from `awaiting_decision` or `retry_eligible` |
| Uncertainty protection | An uncertain prior attempt routes to verification/escalation rather than an immediate retry |
| Explicit authority | Only configured `ActionType` values are permitted |
| Required idempotency | Payment retries without an idempotency key are rejected |

## Policy outcomes

The policy returns one of `allow`, `reject`, `stop`, or `escalate`, together with a stable reason code, policy version, and action flags. This output is suitable for audit events and evaluation without exposing raw provider data.

The policy deliberately separates rejection from stopping. Rejection means the proposal is invalid or not permitted. Stopping means the case must not continue, such as after a successful transaction or terminal case state. Escalation means the workflow needs operator review, such as after retry exhaustion or uncertainty.

## Scope boundary

This increment does not perform state transitions, create payment attempts, call payment providers, or send messages. The future workflow must persist the policy decision and audit event before invoking any side-effecting tool.
