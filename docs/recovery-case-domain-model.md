# Recovery Case Domain Model

**Phase**: 2.7 — Recovery Case Management Engine  
**Author**: Karthikeya  
**Status**: APPROVED & VERIFIED  

---

## 1. Domain Entities and Schema Attributes

### 1.1 `RecoveryCase` (Aggregate Root)

The `RecoveryCase` entity represents an active or resolved revenue risk workflow.

| Column | Type | Nullable | Constraints & Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | Primary Key (`UUIDPrimaryKeyMixin`). |
| `customer_id` | `UUID` | No | Foreign Key -> `customers.id` (`ondelete="RESTRICT"`). |
| `trigger_transaction_id` | `UUID` | No | Foreign Key -> `transactions.id` (`ondelete="RESTRICT"`). |
| `case_key` | `VARCHAR(200)` | No | Unique Business Key (`uq_recovery_case_key`). |
| `state` | `VARCHAR(32)` | No | Current FSM State (`RecoveryCaseState`). Default: `DETECTED`. |
| `priority` | `INTEGER` | No | Operational Queue Priority `[1, 1000]`. Lower integer = higher urgency. |
| `opened_at` | `TIMESTAMP` | No | Opening UTC timestamp. |
| `last_state_changed_at`| `TIMESTAMP` | No | Timestamp of latest state mutation. |
| `closed_at` | `TIMESTAMP` | Yes | Closure UTC timestamp if case reached a terminal state. |
| `version` | `INTEGER` | No | Optimistic locking version. Starts at 1. |
| `metadata` | `JSON` | No | Context attributes: `risk_tier`, `failure_count`, diagnostic codes. |

### 1.2 `CaseStateTransition`

Immutable relational log of every finite state transition undergone by a case.

| Column | Type | Nullable | Constraints & Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | Primary Key. |
| `case_id` | `UUID` | No | Foreign Key -> `recovery_cases.id` (`ondelete="CASCADE"`). |
| `from_state` | `VARCHAR(32)` | Yes | Originating state (null for initial creation). |
| `to_state` | `VARCHAR(32)` | No | Destination state (`RecoveryCaseState`). |
| `reason_code` | `VARCHAR(120)` | No | Machine-readable justification (e.g. `AUTOMATIC_EVENT_INGESTION`). |
| `actor_type` | `VARCHAR(32)` | No | Actor class (`SYSTEM`, `OPERATOR`, `PROVIDER`, `AGENT`). |
| `correlation_id` | `VARCHAR(200)` | No | Distributed tracing correlation identifier. |
| `occurred_at` | `TIMESTAMP` | No | Transition timestamp in UTC. |
| `sequence_number` | `INTEGER` | No | Strict monotonic sequence within case (`uq_transition_case_sequence`). |
| `metadata` | `JSON` | No | Contextual diagnostic payload. |

### 1.3 `AuditEvent`

Compliance-grade, append-only audit trail capturing lifecycle events, priority updates, and operator modifications.

| Column | Type | Nullable | Constraints & Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | Primary Key. |
| `case_id` | `UUID` | No | Foreign Key -> `recovery_cases.id` (`ondelete="CASCADE"`). |
| `event_type` | `VARCHAR(120)` | No | Event type (`CASE_OPENED`, `CASE_UPDATED`, `CASE_RECOVERED`, etc.). |
| `from_state` | `VARCHAR(32)` | Yes | Prior case state if applicable. |
| `to_state` | `VARCHAR(32)` | Yes | New case state if applicable. |
| `actor_type` | `VARCHAR(32)` | No | Category of triggering actor. |
| `actor_id` | `VARCHAR(200)` | Yes | Actor user ID or service identifier. |
| `correlation_id` | `VARCHAR(200)` | No | Tracing correlation ID. |
| `event_time` | `TIMESTAMP` | No | Event timestamp in UTC. |
| `payload_safe` | `JSON` | No | Sanitized, non-sensitive audit event parameters. |
| `sequence_number` | `INTEGER` | No | Monotonic sequence number per case. |

---

## 2. Financial Integrity Guarantees

1. **Integer Minor Units**: All authoritative monetary values are expressed strictly as integers representing minor currency units (e.g., 249900 = ₹2,499.00 / $2,499.00). Floating-point arithmetic is strictly prohibited.
2. **Explicit Currency Association**: Every amount is associated with an exact uppercase 3-letter ISO 4217 currency code.
3. **No Fabricated Recoveries**: Revenue is counted as recovered only when verified by a matching `PAYMENT_SUCCEEDED` event transitioning a case to `RECOVERED` or via attributable `RecoveryEvidence`.
