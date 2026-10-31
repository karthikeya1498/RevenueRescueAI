# Payment Failure Analysis Methodology

## 1. Overview & Objective

Payment gateways and card networks return hundreds of provider-specific decline codes (e.g., Stripe `card_declined:insufficient_funds`, Razorpay `BAD_REQUEST_ERROR:payment_failed`, Adyen `104:ScheduleAccountClosed`).

The [`FailureAnalyzer`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/failure_analyzer.py) maps heterogeneous provider diagnostics into **nine canonical failure categories**. Each category determines whether an incident is intrinsically retryable, assigns a baseline confidence score, and compiles verified supporting evidence.

---

## 2. Canonical Failure Categories

| Canonical Category | Inherent Retryability | Base Confidence | Characteristic Keywords | Diagnostic Rationale |
| :--- | :---: | :---: | :--- | :--- |
| `insufficient_funds` | **True** | `0.9500` | `insufficient`, `funds`, `balance`, `not_enough_funds` | Customer account temporarily lacks required balance. High recovery potential after scheduled cooling period. |
| `expired_card` | **False** | `0.9500` | `expired`, `card_expired`, `card_has_expired` | Card expiration date has passed. Retrying identical credentials will fail deterministically. |
| `authentication_required` | **True** | `0.9000` | `3ds`, `3d_secure`, `auth_required`, `challenge_required` | Cardholder must complete Strong Customer Authentication (SCA) or OTP step-up challenge. |
| `bank_decline` | **True** | `0.8500` | `do_not_honor`, `bank_decline`, `issuer_declined`, `generic_decline` | Bank or card issuer declined authorization. Secondary payment method preferred over blind retries. |
| `provider_timeout` | **True** | `0.9000` | `network_timeout`, `gateway_timeout`, `processor_down` | Transient network or processor infrastructure timeout. Safe for scheduled exponential retry. |
| `fraud_suspected` | **False** | `0.9500` | `fraud`, `stolen_card`, `lost_card`, `pickup_card`, `high_risk` | High-risk signal flagged by provider or risk engine. Automated retries strictly prohibited. |
| `invalid_payment_details` | **False** | `0.9500` | `invalid_cvv`, `invalid_number`, `invalid_expiry`, `bad_details` | Malformed or invalid payment credentials. Requires customer data re-entry. |
| `abandoned_checkout` | **False** | `0.9500` | Triggered by `checkout.abandoned` event | User exited payment funnel before completing transaction. Best recovered via customer reminder. |
| `overdue_invoice` | **False** | `0.9500` | Triggered by `invoice.overdue` event | Outstanding B2B invoice past terms. Suitable for reminder or support escalation. |
| `unknown_failure` | **False** | `0.5500` | Fallback when code/message cannot be matched | Insufficient evidence. Routed to manual review rather than guessing. |

---

## 3. Evidence Extraction & Safety Guarantees

For every analysis, [`FailureAnalyzer`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/failure_analyzer.py) compiles a [`FailureAnalysisResult`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/intelligence/failure_analyzer.py):
1. **Sanitization**: Masks any accidentally ingested cardholder or credentials in logs.
2. **Rule Versioning**: Tags output with `analysis_version = "failure-rules-v1"`.
3. **Traceability**: Retains raw gateway error codes for auditor verification without mutating source transaction data.
