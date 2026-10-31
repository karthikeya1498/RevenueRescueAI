# Event Normalization Engine — Phase 2.6

## 1. Overview
The **Event Normalizer** ([`EventNormalizer`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/event_normalizer.py)) isolates upstream gateway heterogeneity. It consumes provider-specific JSON structures and produces standard `CanonicalEventDTO` instances.

---

## 2. Normalization Mapping Table

| Normalized Field | Stripe Extraction | Razorpay Extraction | Simulator Extraction | Direct Ingestion |
| :--- | :--- | :--- | :--- | :--- |
| `external_event_id` | `raw["id"]` or header | Header or `raw["id"]` | Generated `evt_sim_<hex>` | `raw["event_id"]` |
| `event_type` | `raw["type"]` $\to$ mapped | `raw["event"]` $\to$ mapped | `PAYMENT_FAILED` | `raw["event_type"]` $\to$ mapped |
| `provider` | `"stripe"` | `"razorpay"` | `"synthetic"` | `raw["provider"]` |
| `occurred_at` | `raw["created"]` (epoch $\to$ UTC) | `raw["created_at"]` (epoch $\to$ UTC) | `utc_now()` | `raw["occurred_at"]` (ISO $\to$ UTC) |
| `customer_reference`| `data.object.customer` | `payload.payment.entity.contact/email`| `raw["customer_id"]` | `raw["customer_reference"]` |
| `payment_reference` | `data.object.id` | `payload.payment.entity.id` | Generated `txn_sim_<hex>`| `raw["payment_reference"]` |
| `amount_minor` | `data.object.amount` | `payload.payment.entity.amount` | `raw["amount_minor"]` | `raw["amount_minor"]` |
| `currency` | `data.object.currency.upper()`| `payload.payment.entity.currency.upper()`| `raw["currency"].upper()` | `raw["currency"].upper()` |
| `failure_code` | `last_payment_error.code` | `payload.payment.entity.error_code` | `raw["failure_code"]` | `raw["failure_code"]` |
| `failure_message` | `last_payment_error.message`| `payload.payment.entity.error_description`| `raw["failure_message"]` | `raw["failure_message"]` |

---

## 3. Strict Financial Rules
1. **No Floating-Point Math:** Amounts remain in integer minor units (e.g. cents) throughout all extraction, normalization, and persistence steps.
2. **No Implicit Currency Conversions:** Currencies are normalized to uppercase 3-letter codes (`usd` $\to$ `USD`), but monetary values are never converted between currencies without an authorized foreign-exchange rate engine.
3. **No Synthetic ID Injection:** If customer or transaction references are missing in real provider webhooks, the system records them as `"cust_unknown"` or `"txn_unknown"` rather than fabricating fictitious identifiers.

---

## 4. PII and Cardholder Data Scrubbing
In compliance with PCI-DSS guidelines, `EventNormalizer.sanitize_metadata()` strips all sensitive card details before metadata is stored:
- Any dictionary key matching `card_number`, `cvv`, `cvc`, `pin`, `password`, `secret`, `api_key`, or `token` is replaced with `"[REDACTED]"`.
- Regular expression scans detect 13-to-19 digit card primary account numbers (PANs) embedded in free-form notes and mask them as `"[REDACTED_PAN]"`.
