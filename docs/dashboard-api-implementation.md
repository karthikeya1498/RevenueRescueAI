# Dashboard API Implementation — Phase 2.5

## 1. Executive Summary & Purpose
The Dashboard API layer provides the core financial intelligence and operational visibility for RevenueRescueAI. Designed according to the Phase 0 and Phase 1.3 architectural standards, the dashboard endpoints summarize payment failures, actively managed recovery cases, and verified recovered revenue.

Authoritative calculations are kept 100% on the backend. The frontend acts solely as a renderer, preventing data skew, client-side math errors, and fraudulent or misleading metric fabrication.

---

## 2. Implemented Dashboard Endpoints

### 2.1 GET `/api/v1/dashboard/metrics` (Alias: `/api/v1/dashboard/summary`)
Returns aggregated key performance indicators (KPIs) calculated directly from database records.

**Request Headers:**
```http
GET /api/v1/dashboard/metrics HTTP/1.1
Host: localhost:8000
Authorization: Bearer <valid_jwt_token>
Accept: application/json
```

**JSON Response Schema (`DashboardMetricsResponseDTO`):**
```json
{
  "total_at_risk_amount_minor": 1500000,
  "recovered_amount_minor": 900000,
  "in_recovery_amount_minor": 450000,
  "unrecoverable_amount_minor": 150000,
  "recovery_rate_pct": 60.0,
  "active_cases_count": 3,
  "recovered_cases_count": 6,
  "failed_cases_count": 1,
  "total_cases_count": 10,
  "currency": "USD"
}
```

### 2.2 GET `/api/v1/dashboard/trend` (Alias: `/api/v1/dashboard/revenue-trends`)
Returns daily time-series data for charting recovered vs at-risk revenue over a selectable window (default: 30 days).

**Query Parameters:**
- `days` (integer, optional, default: 30, max: 90): Number of preceding calendar days to evaluate.

**JSON Response Schema (`RevenueTrendResponseDTO`):**
```json
{
  "currency": "USD",
  "points": [
    {
      "date": "2026-10-30",
      "at_risk_amount_minor": 150000,
      "recovered_amount_minor": 100000
    },
    {
      "date": "2026-10-31",
      "at_risk_amount_minor": 85000,
      "recovered_amount_minor": 60000
    }
  ]
}
```

### 2.3 GET `/api/v1/dashboard/workflow-status`
Returns the operational distribution of recovery cases across the system's Finite State Machine (FSM) states.

**JSON Response Schema (`WorkflowStatusDistributionDTO`):**
```json
{
  "DETECTED": 1,
  "ANALYZING": 0,
  "ACTION_PENDING": 2,
  "RETRY_SCHEDULED": 0,
  "IN_RECOVERY": 2,
  "VERIFICATION_PENDING": 0,
  "RECOVERED": 6,
  "FAILED": 1,
  "DISMISSED": 0
}
```

---

## 3. Financial Integrity and Metric Calculation Rules
In adherence to the **Phase 0 Safety Invariants**, the calculation logic implemented in [`DashboardService`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/dashboard_service.py) enforces the following rules:

1. **Integer Minor Units:** All monetary values are summed as 64-bit integers (`BIGINT` in PostgreSQL, `int` in Python/Pydantic) representing minor units (cents). Floating-point arithmetic is forbidden in currency totals.
2. **Strict Verification Criterion:** Revenue is counted as `recovered_amount_minor` **only** if the corresponding `RecoveryCase` has transitioned to `RecoveryCaseState.RECOVERED` with an authoritative payment confirmation. In-flight retries or pending recovery actions are categorized strictly as `in_recovery_amount_minor`.
3. **Zero-Division Protection:** Recovery rate percentage is calculated as:
   $$\text{Recovery Rate (\%)} = \begin{cases} 0.0 & \text{if } \text{total\_at\_risk\_minor} = 0 \\ \text{round}\left(\frac{\text{recovered\_minor}}{\text{total\_at\_risk\_minor}} \times 100, 2\right) & \text{otherwise} \end{cases}$$
4. **Authoritative Empty State Handling:** When a fresh organization has zero transactions or recovery cases:
   - `total_at_risk_amount_minor = 0`
   - `recovered_amount_minor = 0`
   - `recovery_rate_pct = 0.0`
   - `total_cases_count = 0`
   No fictitious "placeholder" numbers or synthetic mock gains are fabricated.

---

## 4. Query Performance and Aggregations
To ensure high scalability and avoid pulling massive row sets into memory:
- Aggregates are computed at the database level using `func.sum()` and `func.count()` grouped by `RecoveryCase.state`.
- Indexed state columns (`idx_cases_state_created`) allow PostgreSQL to scan index structures rapidly even with hundreds of thousands of historical recovery cases.
