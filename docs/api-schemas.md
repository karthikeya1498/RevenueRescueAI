# RevenueRescueAI — API Schemas & Data Contracts
## Phase 1.3: Request/Response Schemas, Reusable Components, and Pydantic v2 Definitions

**Document Version:** 1.0.0  
**Status:** Approved API Schemas  
**Primary Authors:** Senior Backend Architect, API Designer  

---

## 1. Schema Conventions & Validation Rules

All API data contracts in RevenueRescueAI are designed around **Pydantic v2 declarative schemas**:
1. **Forbidden Extra Attributes:** `model_config = ConfigDict(extra="forbid")` is enforced on all request bodies to reject unrecognized fields.
2. **Non-Negative Minor Units:** All monetary amounts enforce `Field(ge=0)`.
3. **ISO-4217 Currency Regex:** Currencies enforce `Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")`.
4. **Explicit UUID Strings:** Primary and foreign keys are validated as canonical RFC-4122 UUID strings.

---

## 2. Reusable Core Data Types

```python
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum

class ISO4217Currency(str):
    """3-letter uppercase ISO currency."""
    pass

class MoneyMinorUnits(BaseModel):
    """Authoritative financial amount pair."""
    model_config = ConfigDict(extra="forbid")
    amount_minor: int = Field(..., ge=0, description="Amount in minor units (e.g. cents)")
    currency: str = Field(..., min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

class PaginationMetadata(BaseModel):
    """Standard collection pagination envelope."""
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)
    offset: int = Field(..., ge=0)
    has_more: bool
```

---

## 3. Reusable Domain Component Schemas

### 3.1 Customer Reference Components
```python
class CustomerSummary(BaseModel):
    id: UUID
    external_id: str
    display_name: str | None
    status: str

class CustomerDetail(CustomerSummary):
    email: str | None
    created_at: datetime
    updated_at: datetime
```

### 3.2 Transaction Components
```python
class TransactionSummary(BaseModel):
    id: UUID
    external_id: str
    amount_minor: int
    currency: str
    status: str
    failure_code: str | None
    occurred_at: datetime

class TransactionDetail(TransactionSummary):
    customer_id: UUID
    failure_message_safe: str | None
    provider: str
    created_at: datetime
```

### 3.3 Recovery Case Components
```python
class CaseSummary(BaseModel):
    id: UUID
    case_key: str
    customer: CustomerSummary
    trigger_transaction: TransactionSummary
    state: str
    priority: int
    attempts_count: int
    opened_at: datetime
    last_state_changed_at: datetime

class CaseDetail(BaseModel):
    id: UUID
    case_key: str
    customer: CustomerDetail
    trigger_transaction: TransactionDetail
    state: str
    priority: int
    version: int
    attempts: list["AttemptSummary"]
    latest_decision: "DecisionSummary | None"
    opened_at: datetime
    last_state_changed_at: datetime
    closed_at: datetime | None
```

### 3.4 Recovery Attempt Components
```python
class AttemptSummary(BaseModel):
    id: UUID
    sequence_number: int = Field(..., ge=1, le=2)
    action_type: str
    status: str
    provider_reference: str | None
    started_at: datetime | None
    finished_at: datetime | None
```

### 3.5 AI Decision Components
```python
class DecisionSummary(BaseModel):
    action_type: str
    reason_code: str
    confidence: Decimal | None = Field(None, ge=Decimal("0.0"), le=Decimal("1.0"))
    rationale_safe: str | None
    validation_status: str
```

### 3.6 Audit Event Components
```python
class AuditEventRecord(BaseModel):
    sequence_number: int = Field(..., ge=1)
    event_type: str
    actor_type: str
    actor_id: str | None
    correlation_id: str
    event_time: datetime
    payload_safe: dict
```

### 3.7 Recovery Evidence Components
```python
class EvidenceRecord(BaseModel):
    id: UUID
    intervention_id: str
    provider_event_id: str
    failed_transaction_id: str
    successful_transaction_id: str
    amount_minor: int = Field(..., ge=0)
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    verified_at: datetime
    attribution_window_hours: int
    attribution_reason: str
    attributable: bool
```

---

## 4. Reusable Request Schemas

### 4.1 Decision Preview Request (`POST /api/v1/recovery/decision-preview`)
```python
class DecisionPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
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

### 4.2 Retry Action Request (`POST /api/v1/cases/{case_id}/actions/retry`)
```python
class ExecuteRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    justification: str = Field(..., min_length=5, max_length=500)
```

### 4.3 Stop Action Request (`POST /api/v1/cases/{case_id}/actions/stop`)
```python
class StopRecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stop_reason: str = Field(..., min_length=3, max_length=120)
    notes: str | None = Field(None, max_length=500)
```

### 4.4 Evidence Verification Request (`POST /api/v1/verification/verify-evidence`)
```python
class SubmitEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intervention_id: str = Field(..., min_length=1)
    provider_event_id: str = Field(..., min_length=1)
    failed_transaction_id: str = Field(..., min_length=1)
    successful_transaction_id: str = Field(..., min_length=1)
    amount_minor: int = Field(..., ge=0)
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
```
