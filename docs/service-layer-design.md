# RevenueRescueAI — Service Layer Design & Transaction Boundaries
## Phase 2.3: Application Services, Transaction Semantics, and Error Propagation

**Document Version:** 1.0.0  
**Status:** Approved Architectural Standard  
**Author:** Senior Backend Architect, API Engineer  

---

## 1. Role and Boundaries of the Service Layer

The **Service Layer** ([`app/services/`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services)) encapsulates application logic, transaction demarcation, and cross-repository coordination.

```text
                  ┌────────────────────────────────────────┐
                  │            API CONTROLLER              │
                  └───────────────────┬────────────────────┘
                                      │ Inbound Request DTO
                                      ▼
                  ┌────────────────────────────────────────┐
                  │            APPLICATION SERVICE         │
                  │  - Validates Domain Invariants         │
                  │  - Coordinates Multiple Repositories   │
                  │  - Demarcates Atomic Transactions      │
                  │  - Raises Domain Exceptions            │
                  └──────┬─────────────────────────┬───────┘
                         │                         │
            Persists     │                         │ Transforms
                         ▼                         ▼
                  ┌──────────────┐          ┌──────────────┐
                  │ REPOSITORIES │          │   MAPPERS    │
                  └──────────────┘          └──────────────┘
```

### Strict Service Layer Invariants:
1. **Zero HTTP Coupling:** Services never accept `Request`, `Response`, `HTTPException`, or `Header` parameters. This allows services to be driven identically by REST APIs, background workers, CLI tools, or automated tests.
2. **DTO Boundaries:** Services accept and return validated DTOs or primitive values, shielding controllers from internal database models.
3. **Explicit Transactions:** Mutations invoke `self.session.commit()`. Read queries avoid unnecessary write locks or flush cascades.
4. **Domain Exception Handling:** Services communicate failures by raising typed domain exceptions defined in [`app/core/errors.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/core/errors.py) (e.g., `EntityNotFoundException`, `DuplicateEntityException`, `InvalidStateTransitionException`).

---

## 2. Implemented Core Services

### 2.1 CustomerService ([`app/services/customer_service.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/customer_service.py))
- `create_customer(dto: CustomerCreateDTO) -> CustomerResponseDTO`: Checks provider/external ID uniqueness, persists customer entity, commits transaction.
- `get_customer(customer_id: UUID) -> CustomerResponseDTO`: Retrieves customer by primary key or raises `EntityNotFoundException`.
- `get_by_external_id(provider: str, external_id: str) -> CustomerResponseDTO`: Provider lookup.
- `list_customers(status, page, size) -> PaginatedResponse[CustomerResponseDTO]`: Executes paginated retrieval with count query.
- `update_customer(customer_id: UUID, dto: CustomerUpdateDTO) -> CustomerResponseDTO`: Performs targeted profile and status mutations.

### 2.2 TransactionService ([`app/services/transaction_service.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/transaction_service.py))
- `record_transaction(dto: TransactionCreateDTO) -> TransactionResponseDTO`: Validates customer existence, ensures payment idempotency, saves transaction record with integer minor amount.
- `get_transaction(transaction_id: UUID) -> TransactionResponseDTO`: Primary key retrieval.
- `get_by_external_id(provider, external_id) -> TransactionResponseDTO`: Gateway reference lookup.
- `list_transactions_for_customer(customer_id, status, page, size) -> PaginatedResponse[TransactionResponseDTO]`: Paginated payment history for a customer.

### 2.3 RecoveryCaseService ([`app/services/recovery_case_service.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/recovery_case_service.py))
- `create_case(dto: RecoveryCaseCreateDTO) -> RecoveryCaseResponseDTO`: Validates customer and transaction existence, verifies 1:1 trigger transaction uniqueness, assigns initial `DETECTED` state, and writes initial `CASE_OPENED` audit event within one atomic transaction.
- `get_case(case_id: UUID) -> RecoveryCaseResponseDTO`: Retrieves case by UUID.
- `get_by_case_key(case_key: str) -> RecoveryCaseResponseDTO`: Retrieves case by canonical business key.
- `list_cases(state, customer_id, page, size) -> PaginatedResponse[RecoveryCaseSummaryDTO]`: Paginated case list for dashboards.
- `transition_state(case_id: UUID, transition: CaseStateTransitionDTO) -> RecoveryCaseResponseDTO`: Enforces legal FSM transitions, verifies terminal state immutability, increments case version, writes transition record, and appends a `STATE_TRANSITION` audit log.

### 2.4 AuditService ([`app/services/audit_service.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/audit_service.py))
- `record_event(dto: AuditEventCreateDTO) -> AuditEventResponseDTO`: Computes the next monotonic sequence number for a case and commits an append-only audit record.
- `get_audit_trail_for_case(case_id: UUID) -> list[AuditEventResponseDTO]`: Retrieves full audit history ordered by sequence number.
- `get_events_by_correlation_id(correlation_id: str) -> list[AuditEventResponseDTO]`: Tracing query retrieving all events associated with a correlation ID.

---

## 3. Transaction Management Strategy

### 3.1 Database Consistency vs. External Payment Gateway Operations
A foundational principle in fintech and financial software engineering:
> **A local database transaction rollback CANNOT undo a real-world payment gateway API call.**

When an external payment charge or refund is submitted to Stripe or Razorpay, that financial action occurs on external bank rails. If a subsequent local database error occurs, executing `session.rollback()` merely rolls back the local database state; it does not reverse the bank charge.

Therefore, our transaction design mandates:
1. **Idempotency Keys First:** Every recovery attempt generates and stores a unique idempotency key before attempting external provider dispatch.
2. **Authoritative Provider Verification:** No recovery is deemed complete until an external webhook or verified provider settlement event is ingested and recorded in `recovery_evidence`.
3. **Two-Phase Bounded Operations:**
   - Phase 1: Local state updated to `ACTION_PENDING`. Transaction committed.
   - External provider called with idempotency key.
   - Phase 2: Provider outcome verified. Local state updated to `VERIFICATION_PENDING` or `RECOVERED`. Transaction committed.

---

## 4. Scope Boundaries for Phase 2.3

In accordance with Phase 2.3 instructions:
- **IN SCOPE:** Core architecture, DTOs, mappers, CRUD service operations, finite state transitions, transaction management, validation, and exception handling.
- **DEFERRED TO FUTURE PHASES:**
  - AI recommendation generation with LLMs.
  - Live payment gateway execution and simulator dispatcher.
  - Recovery policy evaluation and rule engines.
  - Automated retry sequencing and scheduler triggers.
  - Attributed recovery revenue metric rollups.
