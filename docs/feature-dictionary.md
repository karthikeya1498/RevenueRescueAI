# Phase 2.8 Feature Dictionary & Input Data Specifications

## 1. Scope & Privacy Mandates

This feature dictionary defines all observable data inputs evaluated by the **Recovery Intelligence Engine**.

### Mandatory Data Safety Constraints
- **Zero Raw Financial Credentials**: Primary Account Numbers (PAN), full card numbers, CVVs, PINs, banking passwords, and API auth tokens are **never** evaluated, passed, or stored.
- **Zero Demographic Inference**: Ethnicity, gender, religion, age, and location coordinates are **excluded** to prevent algorithmic bias in financial recovery.
- **Strictly Legitimate Signals**: Only operational transaction attributes, failure classifications, and historical customer reliability metrics are consumed.

---

## 2. Observable Feature Specifications

| Feature Name | Data Type | Source Entity & Field | Allowed Range / Domain | Purpose in Intelligence Engine |
| :--- | :--- | :--- | :--- | :--- |
| `amount_minor` | `Integer` | `Transaction.amount_minor` | $\ge 0$ (minor currency units) | Computes gross expected recovery and scales high-exposure risk penalties. |
| `currency` | `String (3)` | `Transaction.currency` | ISO-4217 uppercase (`USD`, `EUR`, `INR`) | Ensures currency context for human-readable audit explanations. |
| `failure_category` | `String` | Output of [`FailureAnalyzer`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/failure_analyzer.py) | 9 canonical categories | Primary driver of strategy eligibility and base recovery probability. |
| `is_retryable` | `Boolean` | Output of [`FailureAnalyzer`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/failure_analyzer.py) | `True` / `False` | Blocks payment retries on fatal errors (expired cards, fraud). |
| `prior_attempts` | `Integer` | Count of `RecoveryCase.attempts` | $0 \le n \le 20$ | Models retry fatigue; 4+ prior attempts disallows automated retries. |
| `customer_success_rate`| `Float` | `Customer.metadata_json["success_rate"]` | $[0.0, 1.0]$ | Adjusts probability baseline according to long-term customer payment reliability. |
| `has_alternate_method`| `Boolean` | `Customer.metadata_json["has_alternate_method"]` | `True` / `False` | Increases expected recovery utility for `UPDATE_PAYMENT_METHOD` / `CUSTOMER_REMINDER`. |
| `is_subscription` | `Boolean` | `RecoveryCase.metadata_json["is_subscription"]` | `True` / `False` | Captures subscriber retention urgency and recurring churn risk. |
| `unusual_velocity` | `Boolean` | `RecoveryCase.metadata_json["unusual_velocity"]` | `True` / `False` | Elevated velocity signal adds +25 to risk score, blocking automated action. |
| `customer_restricted` | `Boolean` | `Customer.status != ACTIVE` | `True` / `False` | Suspended or frozen accounts add +35 to risk score, forcing manual review. |
| `is_case_terminal` | `Boolean` | `RecoveryCase.state in (RECOVERED, STOPPED, CLOSED)` | `True` / `False` | Halts recovery immediately (`NO_ACTION`) with 0 expected value. |
