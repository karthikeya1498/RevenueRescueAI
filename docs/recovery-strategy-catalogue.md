# Approved Recovery Strategy Catalogue

## 1. Overview & Decision Framework

The [`StrategyCatalog`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/strategy_catalog.py) defines the structured catalogue of recovery interventions supported by **RevenueRescueAI**.

Strategies are ranked by **Expected Net Financial Recovery Value**:
$$\text{Expected Value} = \left(\text{Gross Transaction Amount} \times P(\text{Recovery})\right) - \text{Intervention Cost}$$

---

## 2. Strategy Catalogue Registry

| Strategy Key | Domain Action Type | Est. Cost (Minor Units) | Applicable Failure Categories | Preconditions | Rejection / Policy Blocking Conditions |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **`RETRY_LATER`** | `ActionType.RETRY_PAYMENT` | **2** ($0.02) | `insufficient_funds`, `provider_timeout`, `bank_decline`, `authentication_required` | Failure is retryable; Case not terminal. | $\bullet$ Failure not retryable.<br/>$\bullet$ Prior attempts $\ge 4$ (quota exhausted).<br/>$\bullet$ Risk band is `high`. |
| **`UPDATE_PAYMENT_METHOD`** | `ActionType.SEND_REMINDER` | **15** ($0.15) | `expired_card`, `invalid_payment_details`, `bank_decline` | Case not terminal. | Customer account restricted or closed. |
| **`CUSTOMER_REMINDER`** | `ActionType.SEND_REMINDER` | **15** ($0.15) | `abandoned_checkout`, `overdue_invoice`, `authentication_required` | Valid contact info exists on file. | Customer opted out or case terminal. |
| **`SUPPORT_ESCALATION`** | `ActionType.REQUEST_OPERATOR_REVIEW` | **250** ($2.50) | High exposure ($\ge \$1,000$), VIP account, consecutive declines | Case not terminal. | Low-value transaction (cost exceeds benefit). |
| **`MANUAL_REVIEW`** | `ActionType.REQUEST_OPERATOR_REVIEW` | **250** ($2.50) | `fraud_suspected`, `unknown_failure`, high velocity | Case not terminal. | Standard low-risk routine failure. |
| **`NO_ACTION`** | `ActionType.STOP` | **0** ($0.00) | Case already resolved (`RECOVERED`, `STOPPED`, `CLOSED`), restricted account | None (Terminal state handler). | None. Always permitted for terminal/ineligible cases. |

---

## 3. Financial Safety Invariants in Selection

1. **Terminal State Absolute Rule**: If a case is in a terminal state (`RECOVERED`, `STOPPED`, `CLOSED`), the [`StrategySelector`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/strategy_selector.py) **always** returns `NO_ACTION` with 100% confidence ($1.0000$) and 0 expected value.
2. **Exhausted Retries Rule**: Once an incident reaches 4 failed attempts, `RETRY_LATER` is forcibly marked `permitted = False`, preventing endless billing loops and card network non-compliance fines.
3. **High-Risk Block Rule**: Any incident scored $\ge 70$ (Risk Band `high`) is blocked from automated execution, requiring human compliance sign-off.
