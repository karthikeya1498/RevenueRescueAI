# Recovery Case API Reference

**Phase**: 2.7 — Recovery Case Management Engine  
**Author**: Karthikeya  
**Status**: APPROVED & VERIFIED  

---

## 1. Endpoints Summary

All routes are mounted under `/api/v1/cases` and require Bearer JWT authentication.

| Method | Endpoint | Authorized Roles | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/cases` | `OPERATOR`, `ADMIN`, `AUDITOR` | Paginated listing with filtering by state, customer, priority, risk, and search. |
| `GET` | `/api/v1/cases/{case_id}` | `OPERATOR`, `ADMIN`, `AUDITOR` | Deep detail representation with customer, transaction, and attempts. |
| `PATCH` | `/api/v1/cases/{case_id}` | `OPERATOR`, `ADMIN` | Update case operational priority and permitted metadata. |
| `POST` | `/api/v1/cases/{case_id}/transition` | `OPERATOR`, `ADMIN` | Execute and record an explicit finite-state machine transition. |
| `GET` | `/api/v1/cases/{case_id}/history` | `OPERATOR`, `ADMIN`, `AUDITOR` | Monotonic, chronological compliance audit event timeline. |
| `GET` | `/api/v1/cases/{case_id}/events` | `OPERATOR`, `ADMIN`, `AUDITOR` | Associated gateway and webhook receipts for the case. |

---

## 2. Request & Response Examples

### 2.1 List Cases (`GET /api/v1/cases`)
**Query Parameters**:
- `state`: e.g. `detected`, `context_ready`, `awaiting_decision`
- `priority_min`: e.g. `1`
- `priority_max`: e.g. `100`
- `risk_tier`: `high`, `medium`, `low`
- `search`: Substring search matching `case_key`, customer reference, or payment reference
- `page`: 1-indexed page number (default: 1)
- `size`: Items per page (default: 20, max: 100)

**Sample Response**:
```json
{
  "items": [
    {
      "id": "e81d7395-fc71-4648-93ee-a068019ab76a",
      "case_key": "CASE-TX-stripe-PAY-2001",
      "customer": {
        "id": "76d1e57c-fbf7-4c07-b2f5-aa7287713437",
        "external_customer_id": "CUST-1001",
        "display_name": "Customer CUST-1001",
        "status": "active"
      },
      "trigger_transaction": {
        "id": "97e6822c-a28a-4469-89a1-fbce70495393",
        "external_transaction_id": "PAY-2001",
        "amount_minor": 249900,
        "currency": "INR",
        "status": "failed",
        "occurred_at": "2026-10-31T17:00:00Z"
      },
      "state": "detected",
      "priority": 25,
      "attempts_count": 0,
      "opened_at": "2026-10-31T17:00:00Z",
      "last_state_changed_at": "2026-10-31T17:00:00Z"
    }
  ],
  "pagination": {
    "total": 1,
    "page": 1,
    "size": 20,
    "pages": 1,
    "has_more": false
  }
}
```

### 2.2 Patch Case (`PATCH /api/v1/cases/{case_id}`)
**Request Body**:
```json
{
  "priority": 30,
  "metadata": {
    "operator_notes": "Customer requested callback tomorrow"
  }
}
```
*Note*: Attempts to overwrite authoritative keys (`id`, `case_key`, `customer_id`, `trigger_transaction_id`, `amount_minor`, `currency`) are safely ignored by the service.

### 2.3 Transition State (`POST /api/v1/cases/{case_id}/transition`)
**Request Body**:
```json
{
  "to_state": "context_ready",
  "reason_code": "CONTEXT_ASSEMBLED",
  "actor_type": "operator",
  "correlation_id": "corr_ui_8f912c",
  "metadata": {
    "notes": "Verified billing history"
  }
}
```
