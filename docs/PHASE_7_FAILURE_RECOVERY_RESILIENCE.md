# Phase 7: Failure Recovery & Resilience

**Project:** RevenueRescue AI  
**Author:** Karthikeya  
**Status:** Implemented as a safe classification and execution-boundary foundation

## Design principle

Revenue recovery must never convert an unknown provider outcome into an assumed failure or success. The resilience layer classifies failures, preserves uncertainty, and returns a bounded next disposition. It does not blindly repeat a side-effecting operation.

## Failure handling

| Failure | Classification | Disposition |
|---|---|---|
| Timeout | `timeout` | Bounded retry schedule while budget remains |
| Connection/transient API error | `transient_api` | Bounded retry schedule while budget remains |
| Provider validation error | `permanent_api` | Escalate |
| Invalid agent output | `invalid_agent_output` | Escalate; do not execute |
| Uncertain provider outcome | `uncertain_outcome` | Verify before another action |
| Duplicate request | `duplicate_request` | Stop because idempotency protection already suppressed it |
| Retry budget exhausted | Existing failure kind | Escalate |
| Unexpected exception | `unknown` | Bounded retry schedule while budget remains |

## Backoff

The default retry schedule uses bounded exponential backoff. With a 30-second base delay, the first retry is scheduled after 30 seconds, the next after 60 seconds, and the delay is capped by the configured maximum. The schedule is deterministic for a given attempt number and evaluation time.

## Resilient executor

`ResilientExecutor` wraps one already-authorized callable, applies a timeout, and translates timeout and API exceptions into `FailureClassification`. It deliberately performs **one call only**. A later retry requires a fresh policy evaluation, a new idempotency key, and a persisted attempt record.

## Resume envelope

`ResumeEnvelope` carries only a case identifier, optional attempt identifier, workflow phase, idempotency key, correlation identifier, timestamp, and safe payload fields. It contains no credentials or raw provider response. This provides a durable checkpoint boundary for resuming after process restart.

## Verification requirement

An uncertain outcome must move the case to verification or escalation. The system must query authoritative provider state or require operator review before creating another financial attempt. The resilience layer therefore returns `VERIFY`, not `RETRY`, for uncertainty.
