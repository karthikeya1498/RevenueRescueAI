# RevenueRescueAI — DTO and Schema Catalogue
## Phase 2.3: Data Transfer Objects, Validation Rules, and Contract Envelopes

**Document Version:** 1.0.0  
**Status:** Approved Specification  
**Author:** Senior Backend Architect, API Engineer  

---

## 1. DTO Design Philosophy

In RevenueRescueAI, Data Transfer Objects (DTOs) define the authoritative boundary contract between external callers and internal application logic.

### Core Rules:
1. **Pydantic v2 Declarative Schemas:** All DTOs inherit from `pydantic.BaseModel`.
2. **Forbidden Extra Attributes:** All request DTOs configure `model_config = ConfigDict(extra="forbid")` to strictly reject unexpected or malicious injected fields.
3. **Lossless Financial Amounts:** All money fields are named with `_minor` suffixes (e.g. `amount_minor`) and typed as `int` with non-negative constraints `Field(ge=0)`. Floating-point representations (`float`, `double`) are strictly prohibited to prevent IEEE-754 precision drift.
4. **ISO-4217 Currencies:** All currency codes are enforced via regex pattern `^[A-Z]{3}$` (3-letter uppercase).
5. **Decoupled Persistence:** Entities are never returned directly from controllers. Response DTOs control exactly which fields clients can view.

---

## 2. Request DTO Catalogue

### 2.1 Customer Schemas ([`app/schemas/customers.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/customers.py))

#### `CustomerCreateDTO`
Used to register an active customer profile.
```python
class CustomerCreateDTO(BaseModel):
    provider: str = Field(default="synthetic", min_length=1, max_length=64)
    external_customer_id: str = Field(..., min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str | None = Field(default=None, max_length=200)
    status: CustomerStatus = Field(default=CustomerStatus.ACTIVE)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

#### `CustomerUpdateDTO`
Used to modify mutable customer profile attributes.
```python
class CustomerUpdateDTO(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    status: CustomerStatus | None = None
    metadata: dict[str, Any] | None = None
```

### 2.2 Transaction Schemas ([`app/schemas/transactions.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/transactions.py))

#### `TransactionCreateDTO`
Records an ingested payment event.
```python
class TransactionCreateDTO(BaseModel):
    customer_id: UUID
    provider: str = Field(default="synthetic", min_length=1, max_length=64)
    external_transaction_id: str = Field(..., min_length=1, max_length=128)
    amount_minor: int = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    status: TransactionStatus
    failure_code: str | None = Field(default=None, max_length=100)
    failure_message_safe: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### 2.3 Recovery Case Schemas ([`app/schemas/recovery_cases.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/recovery_cases.py))

#### `RecoveryCaseCreateDTO`
```python
class RecoveryCaseCreateDTO(BaseModel):
    customer_id: UUID
    trigger_transaction_id: UUID
    case_key: str | None = Field(default=None, min_length=1, max_length=200)
    priority: int = Field(default=100, ge=1, le=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

#### `CaseStateTransitionDTO`
Requests an explicit state machine transition with audit tracing.
```python
class CaseStateTransitionDTO(BaseModel):
    to_state: RecoveryCaseState
    reason_code: str = Field(..., min_length=3, max_length=120)
    actor_type: ActorType = Field(default=ActorType.OPERATOR)
    correlation_id: str = Field(..., min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

#### `ExecuteRetryRequestDTO` & `StopRecoveryRequestDTO`
```python
class ExecuteRetryRequestDTO(BaseModel):
    justification: str = Field(..., min_length=5, max_length=500)

class StopRecoveryRequestDTO(BaseModel):
    stop_reason: str = Field(..., min_length=3, max_length=120)
    notes: str | None = Field(default=None, max_length=500)
```

### 2.4 Evidence & Intelligence Schemas

#### `RecoveryEvidenceCreateDTO` ([`app/schemas/recovery_evidence.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/recovery_evidence.py))
```python
class RecoveryEvidenceCreateDTO(BaseModel):
    intervention_id: str = Field(..., min_length=1, max_length=200)
    provider_event_id: str = Field(..., min_length=1, max_length=200)
    failed_transaction_id: str = Field(..., min_length=1, max_length=200)
    successful_transaction_id: str = Field(..., min_length=1, max_length=200)
    amount_minor: int = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    verified_at: datetime | None = None
    attribution_window_hours: int = Field(default=72, ge=1, le=720)
    attribution_reason: str = Field(..., min_length=1, max_length=200)
    attributable: bool = Field(default=False)
    evidence: dict[str, Any] = Field(default_factory=dict)
```

#### `DecisionPreviewRequestDTO` ([`app/schemas/agent_decisions.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/agent_decisions.py))
```python
class DecisionPreviewRequestDTO(BaseModel):
    amount_minor: int = Field(..., ge=0)
    currency: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    failure_code: str | None = Field(None, max_length=100)
    failure_message: str | None = Field(None, max_length=500)
    prior_attempts: int = Field(default=0, ge=0, le=20)
    customer_success_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    alternate_method_available: bool = True
    unusual_velocity: bool = False
    customer_restricted: bool = False
```

---

## 3. Response DTO Catalogue

All response DTOs enable `model_config = ConfigDict(from_attributes=True)` to allow seamless instantiation from SQLAlchemy domain models.

### 3.1 Summaries vs. Detailed Responses
- **Summary DTOs** (`CustomerSummaryDTO`, `TransactionSummaryDTO`, `RecoveryCaseSummaryDTO`, `RecoveryAttemptSummaryDTO`): Compact representations optimized for list views, table rows, and embedded relationships without inflating payload sizes.
- **Detailed Response DTOs** (`CustomerResponseDTO`, `TransactionResponseDTO`, `RecoveryCaseResponseDTO`, `RecoveryAttemptResponseDTO`, `AgentDecisionResponseDTO`, `AuditEventResponseDTO`, `RecoveryEvidenceResponseDTO`): Complete records containing audit timestamps, optimistic locking versions, and safe metadata dictionaries.

### 3.2 Common Envelopes ([`app/schemas/common.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/common.py))

#### `PaginatedResponse[T]`
```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    pagination: PaginationMetadata

class PaginationMetadata(BaseModel):
    total: int
    page: int
    size: int
    pages: int
    has_more: bool
```

#### `StatusResponseDTO`
```python
class StatusResponseDTO(BaseModel):
    success: bool
    message: str
```
