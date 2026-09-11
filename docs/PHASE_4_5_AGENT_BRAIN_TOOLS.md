# Phase 4–5: Agent Brain and Controlled Tools

**Project:** RevenueRescue AI  
**Author:** Karthikeya  
**Status:** Implemented foundation; policy and live financial execution remain future work

## Phase 4 agent brain

The agent brain is split into three boundaries:

| Boundary | Responsibility |
|---|---|
| `AgentObservation` | Sanitized, typed facts and caller-provided allowed actions |
| `ReasoningProvider` | Provider-neutral interface for one structured decision |
| `AgentBrain` | Provider invocation followed by deterministic validation |

The live adapter uses the OpenAI-compatible structured-output API with the currently supported `gpt-5-mini` model, strict JSON Schema output, and low reasoning effort. The adapter is lazy-loaded so unit tests do not require credentials or network access.

The provider can propose only an `ActionType` present in the observation allow-list. The validator rejects mismatched case IDs, unsupported actions, missing stop reasons, and invalid stop-reason combinations. Provider output is therefore treated as untrusted input rather than authority.

## Phase 5 controlled tools

The tool registry exposes only three explicitly registered tools:

| Tool | Behavior |
|---|---|
| `inspect_recovery_context` | Read-only inspection intent; no provider lookup in this increment |
| `draft_recovery_intent` | Authorization-gated, idempotency-keyed dry-run intent; no payment call |
| `escalate_recovery_case` | Dry-run operator escalation plan; no notification sent |

Tool inputs reject unknown fields through strict Pydantic models. Unknown tool names are rejected by the registry. `ToolContext` carries authorization, dry-run mode, and correlation identity. All current tools are dry-run safe and return typed `ToolOutput` values.

## Safety boundary

Phase 4 and Phase 5 do not include the deterministic policy engine, state-transition service, payment-provider adapters, customer messaging, credential loading, or autonomous execution. A future workflow must validate agent output through policy before invoking any side-effecting tool. Real tools should be added only behind explicit authorization, idempotency, timeout, verification, and audit requirements.

## Verification

The implementation includes tests for valid structured decisions, allow-list enforcement, stop-reason validation, unknown-tool rejection, authorization gating, dry-run behavior, idempotency propagation, and non-notifying escalation. The tests use fakes and do not call an external model or provider.
