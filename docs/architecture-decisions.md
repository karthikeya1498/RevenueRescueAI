# RevenueRescueAI — Consolidated Architecture Decisions and Pending Proposals

## 1. Executive Summary

This document serves as the master index of all architectural decisions governing **RevenueRescueAI**. It synthesizes previously approved Architecture Decision Records (ADRs from Phase 1.1 through 1.3) and presents new workflow and transaction consistency decisions formulated during **Phase 1.4**, clearly identified by approval status.

---

## 2. Approved Architecture Decisions (Baseline Index)

| ADR ID | Decision Title | Status | Primary Rationale & Architectural Rule |
| :--- | :--- | :---: | :--- |
| **ADR-001** | Modular Monolith Architecture | **APPROVED** | Simplifies deployment and guarantees local ACID transactional boundaries without distributed saga overhead. |
| **ADR-002** | Python FastAPI Backend | **APPROVED** | Modern async performance, native Pydantic schema validation, and seamless integration with AI/ML libraries. |
| **ADR-003** | PostgreSQL for Relational Persistence | **APPROVED** | ACID compliance, row-level locking (`FOR UPDATE`), and robust relational constraints essential for financial data. |
| **ADR-004** | AI Advisory Separation (Untrusted Proposer) | **APPROVED** | AI models propose strategies only; they have zero autonomous tool execution or balance mutation permissions. |
| **ADR-005** | Deterministic Policy Gate (Absolute Veto) | **APPROVED** | Non-negotiable, hardcoded business rule engine that inspects every AI proposal before tool invocation. |
| **ADR-006** | Local Payment Simulator for MVP | **APPROVED** | Eliminates external banking sandbox dependencies and enables 100% deterministic, repeatable test scenarios. |
| **ADR-007** | Strict Minor Currency Integer Units | **APPROVED** | All monetary amounts stored and computed as 64-bit integers (`cents`); floating-point types strictly prohibited. |
| **ADR-008** | Append-Only Co-Located Relational Audit Ledger | **APPROVED** | Every state transition and attempt writes an immutable row to `audit_events` in the same ACID transaction. |
| **ADR-009** | 14-State Explicit Finite State Machine | **APPROVED** | Unambiguous case lifecycle preventing illegal transitions, race conditions, or unverified recovery declarations. |
| **ADR-010** | REST API with OpenAPI 3.1.0 Contract | **APPROVED** | Standardized, strongly typed HTTP endpoints with uniform error structures and correlation ID propagation. |

---

## 3. New Proposed Architecture Decisions (Formulated in Phase 1.4)

The following four architecture decisions were established during Phase 1.4 validation and workflow design. They are **CURRENTLY PENDING FORMAL USER APPROVAL** before application implementation begins in Phase 2.

---

### ADR-011: Two-Phase Planned Attempt Pattern for External Settlement
- **Status:** `PENDING APPROVAL`
- **Context:** Wrapping an external HTTP payment call in an active database transaction risks long-lived row locks and data divergence if the database connection drops after a successful gateway charge.
- **Decision:** Partition recovery execution into three sequential phases:
  1. *Phase 1 (DB Tx):* Lock row with `SELECT FOR UPDATE`, insert planned attempt with `IN_PROGRESS`, set state to `ACTION_EXECUTING`, and commit transaction.
  2. *Phase 2 (HTTP Call):* Dispatch idempotent payment request outside database transactions.
  3. *Phase 3 (DB Tx):* Open new transaction to commit final status (`RECOVERED`, `RETRY_SCHEDULED`, or `VERIFICATION_PENDING`).
- **Consequences:** Eliminates database connection holding during network I/O; prevents unrecorded charges.

---

### ADR-012: The `VERIFICATION_PENDING` (UNCERTAIN) State for Gateway Timeouts
- **Status:** `PENDING APPROVAL`
- **Context:** When an outbound HTTP call to a payment gateway returns HTTP 504 Gateway Timeout or terminates unexpectedly, the system cannot know if the charge succeeded or failed. Blindly retrying can double-charge the customer; assuming failure loses recovered revenue.
- **Decision:** Transition the case to a dedicated `VERIFICATION_PENDING` state and schedule an asynchronous reconciliation job via `VerificationReconciliationWorker` using the idempotent transaction key. Prohibit automated retries or user outreach while in this state.
- **Consequences:** Eliminates double-charge risk; requires an asynchronous reconciliation daemon.

---

### ADR-013: Differentiated Retry Cooldown Policy
- **Status:** `PENDING APPROVAL`
- **Context:** Different payment failure root causes require different recovery delays. Retrying an "insufficient funds" decline after 4 hours is almost certain to fail again, while a network drop can be retried much sooner.
- **Decision:** Standardize automated cooldowns:
  - `TRANSIENT_NETWORK_DROP` / Gateway 504: **4-hour cooldown**.
  - `INSUFFICIENT_FUNDS` (Soft Decline): **24-hour cooldown** (scheduled for next local business morning 09:00 AM).
  - `EXPIRED_CARD`: Halt automatic retries; dispatch card-update notification email.
- **Consequences:** Maximizes recovery success probability per retry attempt while strictly preserving the maximum 2-retry invariant.

---

### ADR-014: Stale Attempt Sweeper via Relational Polling
- **Status:** `PENDING APPROVAL`
- **Context:** If an application worker crashes during Phase 2 of payment execution, a recovery case might remain stuck in `ACTION_EXECUTING` indefinitely.
- **Decision:** Implement a lightweight periodic background worker that queries `recovery_attempts WHERE status = 'IN_PROGRESS' AND initiated_at < NOW() - INTERVAL '5 minutes'`. Any stale attempts are automatically transitioned to `VERIFICATION_PENDING` and queued for provider ledger reconciliation.
- **Consequences:** Guarantees self-healing crash resilience without requiring heavy distributed orchestration frameworks like Temporal or Celery.

---

## 4. Architectural Decision Status Summary

```
Total Decisions Documented:  14
├── Approved Baseline ADRs:  10 (ADR-001 through ADR-010)
└── Pending User Approval:    4 (ADR-011 through ADR-014)
```

No implementation code will be written for ADR-011 through ADR-014 until the user formally approves Phase 1.4.
