# Architecture Explanation and Mock Panel

**Author:** Karthikeya

## 90-second architecture explanation

RevenueRescue AI is organized as a layered control system. Deterministic risk detection turns payment events into typed risk signals. The context layer assembles transaction, customer, and prior-attempt facts. The Agent Brain accepts a strict observation contract and returns a strict structured decision; it cannot execute a tool directly. The tool layer exposes only explicitly registered operations. The safety and policy layer enforces retries, idempotency, terminal-state protection, success protection, and escalation. The resilience layer converts timeouts, API failures, invalid agent outputs, and unknown outcomes into typed dispositions. The evaluation layer runs reproducible simulations and separates recovery from action quality and safety. The Phase 9 frontend exposes the same journey to operators through metrics, queues, and trace drawers. The review-response layer adds an inspectable probability estimator, failure classifier, risk score, expected-value ranking, signed webhook verification, event-id idempotency, and verified recovery attribution.

The important architectural choice is the separation between probabilistic reasoning and deterministic authority. AI can help choose among permitted strategies, but policy decides whether a strategy is allowed, and resilience decides how to proceed when the world is uncertain.

The executable dry-run vertical slice now demonstrates one complete case: detected → context collected → bounded agent decision → deterministic policy → controlled tool intent → verification pending → audit trail. It stops before provider side effects and does not label an intent as recovered.

## Panel questions and prepared answers

| Question | Prepared answer |
|---|---|
| Why use AI at all? | AI is useful for contextual prioritization and bounded strategy selection. It is not the authority for side effects. Structured outputs and policy validation constrain its role. |
| What prevents duplicate charges? | Idempotency keys, duplicate-attempt detection, terminal-state protection, uncertain-outcome handling, and the prohibition on blind retries. Production would add provider-side reconciliation and durable inbox/outbox semantics. |
| What happens when the model returns invalid JSON? | The provider adapter validates a strict schema. Invalid output becomes a typed failure and is routed to a safe stop or escalation path; it is never executed as a best-effort action. |
| How do you measure quality? | Revenue recovery and case recovery are measured separately from action accuracy, safety rate, failures, escalations, verification routes, stops, and rejections. |
| Is the 45.34% recovery rate real? | No. It is a deterministic synthetic regression baseline from 500 scenarios. It demonstrates that the simulator and metrics are reproducible, not that production revenue would improve by that amount. |
| Why is action accuracy only 20%? | The scenario matrix intentionally includes conservative, incorrect, and policy-blocked proposals. Exposing the low action-accuracy baseline is more honest and more useful than presenting recovery revenue alone. |
| What is the biggest production gap? | Real provider reconciliation and authorization. The current system stops before payment execution and customer communication. Production would require approved integrations, identity controls, durable audit retention, data governance, and staged rollout. |
| How is the system observable? | Every HTTP response carries an `x-request-id`; structured access events include request ID, method, path, status, and latency. Agent traces include each decision stage, reason, confidence, policy result, and provider disposition. |
| Why not let the agent call tools directly? | Direct tool access collapses reasoning and authority into one probabilistic step. The registry, contracts, policy gate, and resilience envelope create explicit control points that can be tested independently. |
| What would you build next? | Phase 11 submission is followed by production-grade authentication, provider reconciliation, durable event processing, real API-backed dashboard data, and a shadow-mode pilot with human approval. |
| What changed after the review? | The repository now exposes decision-preview and strategy-comparison APIs, classifies provider failures, estimates action probabilities, ranks expected value after costs, verifies signed provider events, suppresses duplicate events, persists evidence, and counts recovery only when evidence is verified and attributable. |
| Is the probability model production ML? | No. `deterministic-logistic-v1` is an inspectable regression baseline with explicit coefficients. It is a safe replacement point for a calibrated model after governed training, time-split evaluation, calibration, drift monitoring, and shadow-mode approval. |

## Demonstration fallback

If the live frontend fails during the panel, use the checked-in `artifacts/evaluation_report_500.json`, the trace screenshots recorded during Phase 9 browser verification, and the test output showing the deterministic behavior. Do not improvise production claims to compensate for a demo failure.
