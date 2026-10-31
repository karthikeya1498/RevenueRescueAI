# Event-to-Case Mapping Specification

**Phase**: 2.7 — Recovery Case Management Engine  
**Author**: Karthikeya  
**Status**: APPROVED & VERIFIED  

---

## 1. Mapping Matrix

| Ingested Canonical Event | Eligibility | Target Operation | Required References | Outcome Status |
| :--- | :--- | :--- | :--- | :--- |
| `PAYMENT_FAILED` | Case Creation / Update | Creates new case in `DETECTED` or updates active case | `customer_reference`, `payment_reference`, `failure_code`, `amount_minor` | `CASE_CREATED` / `CASE_UPDATED` |
| `SUBSCRIPTION_PAYMENT_FAILED` | Case Creation / Update | Creates new case qualified by billing period or updates active case | `customer_reference`, `subscription_reference`, `failure_code`, `amount_minor` | `CASE_CREATED` / `CASE_UPDATED` |
| `CHECKOUT_ABANDONED` | Case Creation | Creates new case in `DETECTED` | `customer_reference`, `checkout_session_id`, `amount_minor` | `CASE_CREATED` |
| `INVOICE_OVERDUE` | Case Creation / Update | Creates new case in `DETECTED` or updates active case | `customer_reference`, `invoice_reference`, `amount_minor` | `CASE_CREATED` / `CASE_UPDATED` |
| `PAYMENT_SUCCEEDED` | Case Resolution | Resolves matching active case to `RECOVERED` with `closed_at` | `customer_reference`, `payment_reference`, `amount_minor` | `CASE_RESOLVED` / `IGNORED` |
| `PAYMENT_REFUNDED` | Audit / Future Adjustment | Logged; does not open new recovery case | `payment_reference`, `amount_minor` | `IGNORED` |
| Other Event Types | Non-eligible | Ingested into receipts table; does not touch cases | `external_event_id` | `IGNORED` |

---

## 2. Event-Specific Matching Rules

### 2.1 Standard One-Time Payment Failure (`PAYMENT_FAILED`)
- **Key Strategy**: `CASE-TX-{provider}-{payment_reference}`
- **Matching Invariant**: Multiple failure retries for the same payment transaction update the existing case rather than opening duplicate cases.
- **Exposure**: Authoritative exposure is taken from `amount_minor` (in minor currency units, e.g. paise / cents).

### 2.2 Recurring Subscription Failure (`SUBSCRIPTION_PAYMENT_FAILED`)
- **Key Strategy**: `CASE-SUB-{subscription_reference}-{billing_period}`
- **Matching Invariant**: Unrelated monthly billing cycles for the same customer generate distinct recovery cases. For example:
  - October 2026: `CASE-SUB-sub_premium-202610`
  - November 2026: `CASE-SUB-sub_premium-202611`
- **Exposure**: Evaluated as high churn risk in `CaseRiskClassifier`.

### 2.3 Abandoned Checkout Session (`CHECKOUT_ABANDONED`)
- **Key Strategy**: `CASE-CHK-{checkout_session_id}`
- **Matching Invariant**: One case per abandoned checkout session with identifiable cart exposure.

### 2.4 Overdue B2B Invoice (`INVOICE_OVERDUE`)
- **Key Strategy**: `CASE-INV-{invoice_reference}`
- **Matching Invariant**: One recovery case per invoice receivable.

### 2.5 Successful Payment Resolution (`PAYMENT_SUCCEEDED`)
- **Matching Criteria**: Matches open case where `case_key == CASE-TX-{provider}-{payment_reference}` or `trigger_transaction.external_transaction_id == payment_reference`.
- **Precondition**: Matching case must occupy a non-terminal state (`state not in {RECOVERED, STOPPED, CLOSED}`).
- **Outcome**: Transitions case to `RECOVERED`, stamps `closed_at = utc_now()`, updates transaction to `SUCCEEDED`, and logs `CASE_RECOVERED` audit event.
