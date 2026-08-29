# Data Model (Concept)

| Entity | Purpose | Key relationships |
|---|---|---|
| Transaction | Monetary event and provider reference | Belongs to Customer; can open RecoveryCase |
| Customer | Merchant-facing customer identity and contact context | Owns Transactions and cases |
| RecoveryCase | Explicit lifecycle container for one risk episode | References Transaction; has Attempts and AuditEvents |
| RecoveryAttempt | One bounded recovery execution and outcome | Belongs to RecoveryCase; references AgentDecision |
| AgentDecision | Immutable proposed reasoning and selected action | Belongs to an Attempt; always policy-validated |
| AuditEvent | Append-only trace of meaningful changes | Belongs to a case and carries correlation metadata |

Phase 2 will define identifiers, timestamps, money representation, enums, uniqueness, and state transitions. Phase 1 creates no persistence models.
