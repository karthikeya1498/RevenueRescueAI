# Canonical Event Model — Phase 2.6

## 1. Purpose and Philosophy
In enterprise revenue recovery, payment failure notifications arrive in drastically different formats depending on the gateway. For example:
- Stripe nests data deeply inside `data.object` with epoch timestamps.
- Razorpay wraps transactions in `payload.payment.entity`.
- In-house billing engines send flat JSON payloads.

The **Canonical Event Model** (`CanonicalEventDTO`) establishes a single, strongly-typed internal representation. Downstream services (validation, deduplication, audit logging, and future recovery workflows) interact exclusively with this uniform model, completely decoupled from vendor-specific schemas.

---

## 2. Canonical Model Specification

| Field Name | Type | Nullable | Constraints & Rules | Description |
| :--- | :--- | :---: | :--- | :--- |
| `external_event_id` | `string` | No | Min 1, Max 200 chars. | Gateway event identifier (`evt_...`). |
| `event_type` | `string` | No | Must match `CanonicalEventType`. | Standardized business event category. |
| `provider` | `string` | No | Min 1, Max 64 chars, lowercase. | Origin source (e.g. `stripe`, `razorpay`, `synthetic`). |
| `occurred_at` | `datetime` | No | Timezone-aware UTC. | Exact time event occurred at source. |
| `customer_reference` | `string` | No | Min 1, Max 128 chars. | External customer or account reference. |
| `payment_reference` | `string` | Yes | Max 128 chars. Required for payment events. | Gateway transaction ID (`pi_...`, `pay_...`). |
| `subscription_reference`| `string`| Yes | Max 128 chars. | Recurring billing subscription ID. |
| `invoice_reference` | `string` | Yes | Max 128 chars. | Invoiced bill reference. |
| `checkout_session_id` | `string` | Yes | Max 128 chars. | Cart or checkout session identifier. |
| `amount_minor` | `int64` | No | $\ge 0$. Exact minor currency units. | Transaction amount in cents (no floats). |
| `currency` | `string` | No | 3 uppercase ASCII chars (`^[A-Z]{3}$`). | Standard ISO-4217 currency code. |
| `failure_code` | `string` | Yes | Normalized to `FailureCategory`. | Standardized failure category. |
| `failure_message` | `string` | Yes | Max 500 chars. PII-scrubbed. | Safe human-readable explanation. |
| `metadata` | `dict` | No | Clean JSON. PII/PAN redacted. | Non-sensitive diagnostic attributes. |

---

## 3. Approved Canonical Event Types

1. **`PAYMENT_FAILED`**: Direct one-off or checkout charge attempt failed (e.g., card declined, insufficient funds).
2. **`PAYMENT_SUCCEEDED`**: Direct charge settled successfully.
3. **`SUBSCRIPTION_PAYMENT_FAILED`**: Recurring billing cycle renewal attempt failed.
4. **`CHECKOUT_ABANDONED`**: Customer initiated a checkout session but exited before completing payment.
5. **`INVOICE_OVERDUE`**: Issued invoice passed its net terms due date without payment.

---

## 4. Standardized Failure Categories

Raw decline codes from disparate gateways are mapped into uniform enum categories:
- `insufficient_funds`: Balance shortage in account or credit limit reached.
- `card_expired`: Card expiry date has elapsed.
- `authentication_required`: 3D-Secure or multi-factor customer step-up required.
- `do_not_honor`: Card issuer general refusal.
- `generic_decline`: Unspecified bank decline.
- `processing_error`: Temporary gateway or switch network timeout.
- `fraud_suspected`: Bank or processor risk engine flagged transaction.
- `abandoned`: User-initiated abandonment.
- `overdue`: Time-elapsed payment failure.
- `unknown`: Unclassified decline reason.
