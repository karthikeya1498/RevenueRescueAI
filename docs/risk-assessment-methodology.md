# Recovery Risk Assessment Methodology

## 1. Objective & Operational Role

The [`RiskAssessor`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/risk_assessor.py) evaluates exposure risk across every recovery incident. It calculates an integer risk score in $[0, 100]$ and assigns a **Risk Band** (`low`, `medium`, `high`) accompanied by an operational **Action Limit** (`automatic`, `human_approval`, `block`).

---

## 2. Risk Scoring Formula

$$\text{Risk Score} = \min\left(100, \sum \text{Risk Contributions}\right)$$

### Contribution Matrix

| Risk Dimension | Condition | Point Addition | Diagnostic Reason Code |
| :--- | :--- | :---: | :--- |
| **Security & Fraud Signal** | Failure category is `fraud_suspected` | **+60** | `provider_security_or_fraud_signal` |
| **Repeated Failures** | Prior attempts $\ge 4$<br/>Prior attempts $2 \le n < 4$ | **+35**<br/>**+20** | `repeated_failed_attempts`<br/>`elevated_attempt_count` |
| **Velocity Anomaly** | `unusual_velocity == True` | **+25** | `unusual_retry_velocity_detected` |
| **Customer Suspension** | Customer account status $\ne$ `ACTIVE` | **+35** | `customer_account_restricted_or_suspended` |
| **Financial Exposure** | Transaction Amount $\ge \$5,000$ (500,000 minor)<br/>Transaction Amount $\ge \$1,000$ (100,000 minor) | **+20**<br/>**+10** | `major_financial_exposure`<br/>`high_value_transaction` |
| **Subscriber Churn Risk**| Subscription payment with `expired_card` | **+15** | `recurring_subscriber_churn_risk` |

---

## 3. Risk Bands & Policy Action Limits

| Composite Score Range | Risk Band | Policy Action Limit | Operational Effect |
| :---: | :---: | :---: | :--- |
| **$0 \le \text{Score} \le 29$** | `low` | `automatic` | Automated low-cost retries and scheduled reminders permitted without operator sign-off. |
| **$30 \le \text{Score} \le 69$** | `medium` | `human_approval` | Automated intervention throttled; operator approval or policy validation required. |
| **$70 \le \text{Score} \le 100$** | `high` | `block` | Automated payment retries are strictly blocked. Incident routed to compliance / manual review. |
