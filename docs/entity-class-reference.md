# RevenueRescueAI — Entity Class Reference & Object-Relational Mappings

## 1. Executive Summary

In SQLAlchemy 2.0, entity classes define the Python-side object representations of relational database tables. 

All entity classes in **RevenueRescueAI** reside in [`backend/app/models/domain.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/models/domain.py) and inherit from `Base` (SQLAlchemy `DeclarativeBase`). They use **strict Python type annotations** (`Mapped[T]`) and `mapped_column()` for compile-time and runtime type safety.

---

## 2. Shared Persistence Mixins

To prevent repetitive code and guarantee architectural consistency across tables, all durable entities inherit from standard mixins defined in [`app/core/database.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/core/database.py):

### 2.1 `UUIDPrimaryKeyMixin`
```python
class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
```
- **Why UUIDs over auto-incrementing integers?**
  Auto-incrementing integers (`1, 2, 3...`) are predictable and vulnerable to enumeration attacks (IDOR). UUIDv4 random identifiers guarantee universal uniqueness across microservices, distributed workers, and client devices without database coordination.

### 2.2 `TimestampMixin`
```python
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
```
- **Timezone Awareness:** Enforces UTC timestamps (`DateTime(timezone=True)`). Server time zones can never distort audit logs or cooling-off windows.

---

## 3. Detailed Entity Class Catalogue

### 3.1 `Customer` (Customer Aggregate)
- **Table Name:** `customers`
- **Business Purpose:** Encapsulates the merchant's end-customer profile, billing status, and associated payment history.
- **Key Relationships:**
  - `transactions`: 1-to-Many relationship (`list[Transaction]`) with `back_populates="customer"`.
  - `recovery_cases`: 1-to-Many relationship (`list[RecoveryCase]`) with `back_populates="customer"`.
- **Deletion Safety:** Customer deletion is blocked if active transactions or recovery cases exist (`ondelete="RESTRICT"`).

### 3.2 `Transaction` (Payment Ledger Record)
- **Table Name:** `transactions`
- **Business Purpose:** Records an authoritative financial charge or failure at the gateway.
- **Key Attributes:**
  - `amount_minor`: 64-bit integer storing monetary value in cents (`CheckConstraint("amount_minor >= 0")`).
  - `currency`: 3-letter uppercase ISO currency code (`CheckConstraint("length(currency) = 3 AND currency = upper(currency)")`).
  - `status`: Strongly-typed enum member (`TransactionStatus`).
- **Key Relationships:**
  - `customer`: Many-to-1 relationship with `Customer`.
  - `recovery_cases`: 1-to-Many relationship with `RecoveryCase` (as `trigger_transaction`).

### 3.3 `RecoveryCase` (Central Aggregate Root)
- **Table Name:** `recovery_cases`
- **Business Purpose:** Central coordinator for an episode of at-risk revenue. Protects invariants across attempts and decisions.
- **Key Attributes:**
  - `case_key`: Deterministic business key (e.g., `case_live_99214a`).
  - `state`: Current 14-state FSM status (`RecoveryCaseState`).
  - `version`: Optimistic locking integer incremented on every state transition to prevent race conditions.
- **Key Child Relationships (Owned Aggregate Boundary):**
  - `attempts`: 1-to-Many (`list[RecoveryAttempt]`, `cascade="all, delete-orphan"`).
  - `decisions`: 1-to-Many (`list[AgentDecision]`, `cascade="all, delete-orphan"`).
  - `audit_events`: 1-to-Many (`list[AuditEvent]`, `cascade="all, delete-orphan"`).
  - `transitions`: 1-to-Many (`list[CaseStateTransition]`, `cascade="all, delete-orphan"`).

### 3.4 `RecoveryAttempt` (Execution Unit)
- **Table Name:** `recovery_attempts`
- **Business Purpose:** Represents a concrete execution attempt (virtual card charge, reminder email).
- **Key Attributes:**
  - `sequence_number`: Monotonic index within the case (`1, 2, ...`).
  - `idempotency_key`: Unique string key (`uq_attempt_idempotency_key`) preventing duplicate gateway charges.
  - `status`: Current execution state (`RecoveryAttemptStatus`).
- **Key Relationships:**
  - `case`: Many-to-1 relationship with `RecoveryCase`.
  - `decision`: 1-to-1 optional relationship with `AgentDecision` (`uselist=False`).

### 3.5 `AgentDecision` (Reasoning Artifact)
- **Table Name:** `agent_decisions`
- **Business Purpose:** Preserves the AI recommendation rationale and Policy Gate validation status.
- **Key Attributes:**
  - `confidence`: Decimal score between 0.000 and 1.000 (`ck_decision_confidence`).
  - `raw_response_hash`: SHA-256 fingerprint of the LLM output for auditability.
  - `validation_status`: Policy evaluation verdict (`DecisionValidationStatus`).

### 3.6 `AuditEvent` (Immutable Audit Log)
- **Table Name:** `audit_events`
- **Business Purpose:** Immutable relational audit log capturing who, what, when, and why an action occurred.
- **Key Attributes:**
  - `sequence_number`: Monotonic counter per case (`uq_audit_case_sequence`).
  - `correlation_id`: Distributed trace identifier.
  - `payload_safe`: Redacted JSON context.

### 3.7 `CaseStateTransition` (State Machine History)
- **Table Name:** `case_state_transitions`
- **Business Purpose:** Tracks historical lifecycle movements (`from_state` -> `to_state`).
- **Key Attributes:**
  - `sequence_number`: Monotonic transition order per case (`uq_transition_case_sequence`).

### 3.8 `ProviderWebhookEvent` (Idempotency Receipt)
- **Table Name:** `provider_webhook_events`
- **Business Purpose:** Deduplication buffer for raw incoming gateway webhook notifications.
- **Key Attributes:**
  - `external_event_id`: Gateway event ID (`uq_provider_event (provider, external_event_id)`).
  - `payload_hash`: SHA-256 hash of raw bytes.
  - `signature_verified`: Boolean indicating HMAC authenticity.

### 3.9 `RecoveryEvidence` (Authoritative Settlement Proof)
- **Table Name:** `recovery_evidence`
- **Business Purpose:** Immutable proof linking a gateway settlement to an intervention within the 72h window.
- **Key Attributes:**
  - `amount_minor`: Integer cents (`CheckConstraint("amount_minor >= 0")`).
  - `attribution_window_hours`: Max allowed settlement window (default 72).
  - `attributable`: Boolean verification verdict.

---

## 4. Relationship Deletion Rules (Cascade vs. Restrict)

| Parent Entity | Child Entity | Foreign Key On-Delete | Rationale |
| :--- | :--- | :---: | :--- |
| `Customer` | `Transaction` | `RESTRICT` | A customer cannot be deleted while financial transactions exist. |
| `Customer` | `RecoveryCase` | `RESTRICT` | A customer cannot be deleted while active recovery cases exist. |
| `Transaction`| `RecoveryCase` | `RESTRICT` | The trigger transaction for a case must never be deleted. |
| `RecoveryCase`| `RecoveryAttempt` | `CASCADE` | Attempts belong exclusively to their case aggregate. |
| `RecoveryCase`| `AgentDecision` | `CASCADE` | Decisions belong exclusively to their case aggregate. |
| `RecoveryCase`| `AuditEvent` | `CASCADE` | Clean cascade deletion during testing teardown; production revokes delete grants. |
| `RecoveryAttempt`| `AgentDecision` | `SET NULL` | If an attempt is cancelled or purged, the historical decision record is preserved. |
