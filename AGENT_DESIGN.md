# Agent Design (Future)

The future agent receives a typed observation containing a recovery case, transaction context, prior attempts, policy facts, and available capabilities. It returns a strict structured decision: action, rationale, confidence, required tool, and stop/escalation recommendation.

The agent may propose only enumerated capabilities. A validator rejects malformed or unsupported output. A deterministic policy gate checks retry limits, duplicate prevention, success protection, consent and escalation rules before any tool is invoked. Tools are narrow adapters, never arbitrary URL callers. Verification records confirmed, failed, or uncertain outcomes; uncertainty must not be converted into a duplicate action.

**Unimplemented in Phase 1:** observation assembly, LLM provider adapter, decision schema, tool registry, policy engine, workflow runner, and verification service.
