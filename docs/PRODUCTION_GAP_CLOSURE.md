# Production Gap Closure

**Author:** Karthikeya  
**Status:** Implemented prototype controls with explicit production boundaries

## What changed

RevenueRescue AI now includes a deterministic failure classifier, a versioned recovery-probability estimator, transparent risk scoring, expected-value ranking in integer minor units, and explainable next-best-action output. These controls sit before the existing policy layer. The LLM remains optional bounded reasoning and cannot bypass the allow-list, safety policy, or verification requirements.

Provider integration boundaries now include HMAC signature verification, event-id idempotency, payload hashing, and a durable schema for provider webhook receipts. Recovery attribution requires a verified provider event, a matching amount and currency, a distinct successful transaction, and a bounded attribution window. A generated intent or payment link is never treated as recovered revenue.

## Decision path

```text
Provider event
  -> signature verification
  -> event-id idempotency
  -> sanitized feature extraction
  -> failure classification
  -> recovery probability estimate
  -> 0-100 risk assessment
  -> expected value = probability x amount - cost
  -> next-best-action ranking
  -> deterministic policy gate
  -> auto / human approval / block
  -> controlled provider adapter
  -> verified webhook evidence
  -> attributed recovery or explicit non-recovery
```

## Current model boundary

`deterministic-logistic-v1` is an inspectable regression baseline, not a trained production model. It is intentionally versioned and exposes its features, coefficients, probabilities, and rationale. A production rollout should replace the estimator only after a documented, time-split experiment, calibration assessment, drift monitoring, and shadow-mode approval.

## Evaluation boundary

The existing 500-scenario report remains synthetic. Baseline comparison is now available for do-nothing, always-retry, rule-based, and oracle-upper-bound counterfactuals. These outputs must be labeled synthetic counterfactuals and must not be presented as live provider performance. Incremental recovery claims require randomized holdout assignment and verified provider events.

## Security boundary

Secrets are accepted only through environment configuration and are never included in payload-safe audit fields. Webhook signatures are verified before parsing or processing. Production deployment must add authentication, role-based authorization, rate limiting, encrypted transport, secret rotation, provider replay-window checks, database unique constraints, and a durable inbox/outbox worker.

## Human-in-the-loop policy

Low-risk actions can be policy-eligible for automatic execution. Medium-risk actions require operator approval. High-risk or suspicious cases are blocked and escalated. Low confidence, invalid model output, provider uncertainty, duplicate events, and missing evidence all produce safe non-action dispositions.

## Five dashboard questions

The operator experience must answer: how much is at risk; which cases are recoverable; what action is next; why was it selected; and what amount was actually recovered because of it. The first four are available in preview and trace outputs. The fifth is only true when `RecoveryEvidence.attributable` is backed by verified provider evidence.
