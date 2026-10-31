# Case Read API Implementation — Phase 2.5

## 1. Overview and MVP Scope
Phase 2.5 introduces secure read operations for recovery cases. While payment ingestion and autonomous recovery executions are scheduled for subsequent phases (Phases 2.6 and 2.7), operator and auditor inspection requires querying recovery cases with fine-grained status filters, pagination, and linked customer context.

In accordance with Phase 1.3 contracts, mutating operations (`POST`, `PUT`, `DELETE` on cases) remain restricted. Only authorized read operations are exposed.

---

## 2. API Endpoints Specification

### 2.1 List Recovery Cases: `GET /api/v1/cases`
Provides a paginated, filterable stream of recovery cases.

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `state` | `string` | No | `null` | Filter by case state (case-insensitive: `DETECTED`, `IN_RECOVERY`, `RECOVERED`, etc.). |
| `customer_id` | `UUID` | No | `null` | Filter cases associated with a specific customer record. |
| `page` | `integer` | No | `1` | 1-based page number (minimum: 1). |
| `limit` | `integer` | No | `20` | Page size limit (minimum: 1, maximum: 100). |

**Response Schema (`PaginatedResponse[CaseSummaryItemDTO]`):**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "customer_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "trigger_transaction_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "state": "in_recovery",
      "currency": "USD",
      "at_risk_amount_minor": 15000,
      "recovered_amount_minor": 0,
      "priority_score": 75,
      "created_at": "2026-10-31T12:00:00Z",
      "updated_at": "2026-10-31T12:05:00Z",
      "customer": {
        "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "external_customer_id": "cust_stripe_101",
        "email": "customer@example.com",
        "name": "Jane Doe"
      },
      "trigger_transaction": {
        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "external_transaction_id": "txn_fail_101",
        "amount_minor": 15000,
        "currency": "USD",
        "status": "failed",
        "failure_code": "insufficient_funds",
        "occurred_at": "2026-10-31T11:59:00Z"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 20,
  "pages": 1
}
```

### 2.2 Retrieve Case Detail: `GET /api/v1/cases/{case_id}`
Returns complete diagnostic and lifecycle information for a single recovery case.

**Path Parameters:**
- `case_id` (`UUID`): Primary key identifier of the recovery case.

**Response Behavior:**
- **200 OK**: Returns `CaseDetailResponseDTO` containing case state, linked customer, trigger transaction, and historical attempt count.
- **404 Not Found**: Returns RFC-7807 structured error payload when `case_id` does not exist:
  ```json
  {
    "error_code": "RESOURCE_NOT_FOUND",
    "message": "Recovery case 550e8400-e29b-41d4-a716-000000000000 not found",
    "status_code": 404,
    "timestamp": "2026-10-31T16:35:00Z"
  }
  ```

---

## 3. Query Efficiency & N+1 Prevention
When querying collections of entities with associated relational records (e.g., `Customer` and `Transaction`), unoptimized ORM queries often execute 1 query for the parent table plus $N$ queries for each associated child row ($N+1$ problem).

In [`CaseRepository`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/repositories/case_repository.py), we explicitly employ SQLAlchemy's `joinedload`:
```python
query = (
    select(RecoveryCase)
    .options(
        joinedload(RecoveryCase.customer),
        joinedload(RecoveryCase.trigger_transaction),
        joinedload(RecoveryCase.attempts),
    )
    .order_by(RecoveryCase.created_at.desc())
)
```
This forces PostgreSQL to resolve the entire case graph in a single relational `LEFT OUTER JOIN`, reducing query execution latency to $O(1)$ database round-trips.
