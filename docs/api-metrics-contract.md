# RevenueRescueAI — Dashboard API Metrics Contract
## Phase 1.3: Financial Metric Definitions, Formulas, Data Sources, and Invariants

**Document Version:** 1.0.0  
**Status:** Approved Metrics Contract  
**Primary Authors:** Senior Financial Systems Analyst, Senior Backend Architect  

---

## 1. Executive Summary & Authoritative Calculation Rule

In fintech software engineering, **the frontend must never independently compute financial KPIs** from partial or unpaginated API query results. 

If the frontend attempts to sum transaction arrays in JavaScript:
- It computes metrics over the currently loaded page (e.g., 20 items) rather than the entire database volume.
- JavaScript binary floating-point numbers introduce client-side rounding bugs.
- Different operator screens show conflicting totals.

**The Authoritative Metric Invariant:**
> **All financial metrics, recovery percentages, and case counts are computed authoritatively on the backend inside PostgreSQL/SQLAlchemy using exact integer minor units and returned through `/api/v1/dashboard/metrics`.**

---

## 2. Comprehensive Metric Definitions & Formulas

### 2.1 Metric: Recovered Revenue (`recovered_revenue_minor`)
- **Business Meaning:** Total volume of failed revenue that has been successfully won back and mathematically verified against payment provider evidence.
- **Authoritative Formula:**
  $$\text{Recovered Revenue} = \sum_{\text{evidence}} \text{amount\_minor} \quad \text{WHERE } \text{attributable} = \text{TRUE} \text{ AND } \text{currency} = C$$
- **Primary Data Source:** `recovery_evidence` table.
- **Handling of Pending / Uncertain Outcomes:** **Strictly Excluded.** If a case is in `ACTION_PENDING` or `VERIFICATION_PENDING`, its amount is **0% counted** towards recovered revenue.
- **Handling of Reminders:** Involuntary card update reminders have zero direct recovery value until a verified transaction settles.
- **Currency Treatment:** Grouped strictly by ISO-4217 currency. Cross-currency addition is forbidden.
- **Synthetic vs. Real:** Evaluation batch results are flagged `is_synthetic = TRUE` and stored in evaluation tables, completely isolated from operational recovered revenue.

---

### 2.2 Metric: At-Risk Revenue (`at_risk_revenue_minor`)
- **Business Meaning:** Total monetary volume of all payment failures currently open or resolved within the designated reporting window.
- **Authoritative Formula:**
  $$\text{At-Risk Revenue} = \sum_{\text{cases}} \text{trigger\_transaction.amount\_minor} \quad \text{WHERE } \text{currency} = C$$
- **Primary Data Source:** `transactions` table joined with `recovery_cases`.
- **Handling of Terminal States:** Cases in `RECOVERED`, `FAILED`, and `TERMINATED` remain part of the historical at-risk baseline for the period to calculate accurate recovery percentages.

---

### 2.3 Metric: Revenue Recovery Rate (`recovery_rate_pct`)
- **Business Meaning:** The proportion of at-risk monetary volume successfully won back.
- **Authoritative Formula:**
  $$\text{Revenue Recovery Rate (\%)} = \left( \frac{\text{Recovered Revenue Minor}}{\text{At-Risk Revenue Minor}} \right) \times 100$$
- **Precision & Formatting:** Formatted as a fixed 2-decimal percentage string (e.g., `"45.34%"`).
- **Zero-Division Safety:** If $\text{At-Risk Revenue} = 0$, the rate returns `"0.00%"` (zero-safe).

---

### 2.4 Metric: Case Recovery Rate (`case_recovery_rate_pct`)
- **Business Meaning:** The percentage of unique recovery cases successfully transitioned to `RECOVERED`.
- **Authoritative Formula:**
  $$\text{Case Recovery Rate (\%)} = \left( \frac{\text{Count of Cases WHERE state = 'RECOVERED'}}{\text{Total Cases WHERE state} \ne \text{'DETECTED'}} \right) \times 100$$
- **Benchmark Evaluation Result:** Across the approved 500-scenario evaluation batch (Seed 42), the case recovery rate is exactly **45.50%** (182 recovered cases out of 400 at-risk cases).

---

### 2.5 Metric: Safety Compliance Rate (`safety_rate_pct`)
- **Business Meaning:** The percentage of actions that strictly complied with safety policy invariants (INV-001 through INV-016) without any unauthorized execution.
- **Authoritative Formula:**
  $$\text{Safety Rate (\%)} = \left( \frac{\text{Total Validated or Legitimate Policy Vetoes}}{\text{Total Action Decisions}} \right) \times 100$$
- **Mandatory Target:** Must strictly equal **`100.00%`**. Any value below 100% indicates an invariant breach and halts the release pipeline.

---

## 3. JSON Contract Schema for `/api/v1/dashboard/metrics`

```json
{
  "currency": "USD",
  "time_range": "all_time",
  "at_risk_revenue_minor": 216320000,
  "recovered_revenue_minor": 98088700,
  "recovery_rate_pct": "45.34%",
  "case_recovery_rate_pct": "45.50%",
  "total_at_risk_cases": 400,
  "total_recovered_cases": 182,
  "escalated_cases": 90,
  "verification_pending_cases": 91,
  "stopped_cases": 46,
  "safety_rate_pct": "100.00%",
  "action_accuracy_pct": "20.00%",
  "generated_at": "2026-10-30T12:04:11.000Z"
}
```

### UI Formatting Rules:
- Currency minor units are formatted with the standard currency symbol: `98088700` minor units of `USD` $\to$ **`$980,887.00`** (or compact: **`$980.9k`** on KPI cards).
- All rates include the `%` suffix.
