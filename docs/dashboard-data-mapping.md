# Dashboard Data Mapping — Phase 2.5

## 1. Overview
This document specifies the exact mapping between frontend dashboard UI components and backend REST API response fields. In accordance with financial safety rules, frontend components never compute, extrapolate, or guess financial values. Every displayed metric traces directly to an authoritative backend integer field.

---

## 2. Component to API Field Mapping Table

| Dashboard Component | UI Display Field | Backend API Endpoint | JSON Response Field | Type & Units | Transformation / Formatting Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **KPI Card 1** | Revenue at Risk | `GET /api/v1/dashboard/metrics` | `total_at_risk_amount_minor` | `int64` (cents) | Divide by 100, format with currency symbol (`$X,XXX.XX`). |
| **KPI Card 2** | Recovered Revenue | `GET /api/v1/dashboard/metrics` | `recovered_amount_minor` | `int64` (cents) | Divide by 100, format with emerald currency color. |
| **KPI Card 3** | In-Recovery Revenue | `GET /api/v1/dashboard/metrics` | `in_recovery_amount_minor` | `int64` (cents) | Divide by 100, format with amber in-progress accent. |
| **KPI Card 4** | Recovery Rate | `GET /api/v1/dashboard/metrics` | `recovery_rate_pct` | `float` (%) | Format as percentage string: `XX.X%` (0.0% when total at risk is 0). |
| **KPI Card 5** | Active Recovery Cases | `GET /api/v1/dashboard/metrics` | `active_cases_count` | `int` | Raw integer display of cases in active processing states. |
| **KPI Card 6** | Recovered Cases | `GET /api/v1/dashboard/metrics` | `recovered_cases_count` | `int` | Raw integer count of successfully resolved cases. |
| **Chart Panel** | Revenue Trend Line | `GET /api/v1/dashboard/trend?days=30` | `points[].date`, `points[].recovered_amount_minor` | `string` (date), `int64` | X-axis: ISO date string. Y-axis: recovered minor / 100. |
| **Workflow Status**| State Distribution Bars | `GET /api/v1/dashboard/workflow-status` | `DETECTED`, `IN_RECOVERY`, `RECOVERED`, etc. | `int` (counts) | Horizontal distribution bar with corresponding state badge colors. |
| **Recovery Table** | Case ID & Customer | `GET /api/v1/cases?page=1&limit=20` | `items[].id`, `items[].customer.email` | `UUID`, `string` | Monospace short UUID with linked customer email. |
| **Recovery Table** | At-Risk Amount | `GET /api/v1/cases?page=1&limit=20` | `items[].at_risk_amount_minor` | `int64` (cents) | Formatted as `$XX.XX`. |
| **Recovery Table** | State Badge | `GET /api/v1/cases?page=1&limit=20` | `items[].state` | `string` | Colored pill badge reflecting FSM state. |

---

## 3. Empty State Presentation Benchmark
When `total_cases_count === 0`:
- **UI Render**: Displays a dedicated empty-state card:
  > *"No recovery data available yet. Recovery cases will appear when approved payment events are processed."*
- **Integrity Guarantee**: Charts render a flat baseline at 0 with a clear informational caption. No synthetic simulated sinusoidal curves or random mock financial metrics are shown.
