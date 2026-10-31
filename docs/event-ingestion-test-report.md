# Event Ingestion Test Report — Phase 2.6

## 1. Test Execution Summary

- **Test Suite:** [`backend/tests/test_event_ingestion.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_event_ingestion.py)
- **Framework:** `pytest` 9.1.1, Python 3.14.4
- **Date Executed:** 2026-10-31
- **Target Suite Outcome:** **15 PASSED (100%)** in 10.30s
- **Full Backend Suite Outcome:** **125 PASSED (100%)** in 56.33s
- **Failed / Skipped:** **0**

---

## 2. Granular Test Case Matrix

| Category | Test Function Name | Scenarios Verified | Result |
| :--- | :--- | :--- | :---: |
| **Normalization** | `test_normalization_stripe_webhook` | Translates Stripe `data.object` payload, extracts amount in minor units, converts epoch to UTC. | **PASSED** |
| **Normalization** | `test_normalization_razorpay_webhook`| Translates Razorpay `payload.payment.entity`, maps Indian Rupee `INR`, normalizes contact to customer ref. | **PASSED** |
| **Normalization** | `test_normalization_sanitizes_pii` | Scrubs PANs, card numbers, CVVs, and tokens from metadata dictionaries and notes. | **PASSED** |
| **Validation** | `test_validation_all_supported_event_types` | Validates all 5 approved canonical event types with their respective required fields. | **PASSED** |
| **Validation** | `test_validation_rejects_unsupported_type` | Rejects unrecognized event types with `UnsupportedEventTypeException` (HTTP 400). | **PASSED** |
| **Validation** | `test_validation_rejects_missing_payment_reference_on_payment_failed` | Rejects `PAYMENT_FAILED` missing transaction/payment reference with HTTP 422. | **PASSED** |
| **Validation** | `test_validation_rejects_negative_amount` | Rejects negative amounts (`amount_minor < 0`) at schema boundary. | **PASSED** |
| **Validation** | `test_validation_rejects_future_clock_skew` | Rejects timestamps more than 15 minutes in the future to prevent replay/drift attacks. | **PASSED** |
| **Deduplication** | `test_deduplication_exact_duplicate` | Resubmitting exact same event returns HTTP 200 with `duplicate: true`, suppressing side effects. | **PASSED** |
| **Deduplication** | `test_deduplication_conflicting_duplicate_raises_409` | Reusing external event ID with differing amounts/payloads raises HTTP 409 Conflict. | **PASSED** |
| **Deduplication** | `test_different_providers_same_external_id_are_distinct`| Proves composite key `(provider, external_event_id)` allows Stripe and Razorpay to use identical IDs without collision. | **PASSED** |
| **API Ingress** | `test_api_events_post_canonical` | Exercises `POST /api/v1/events` endpoint with Bearer authentication and correlation headers. | **PASSED** |
| **Security** | `test_api_webhook_with_hmac_verification` | Verifies cryptographic HMAC-SHA256 signature check; accepts valid digests, rejects tampered payloads with HTTP 401. | **PASSED** |
| **Simulator** | `test_api_simulate_failure_endpoint` | Triggers `POST /api/v1/events/simulate-failure`, verifying synthetic tags and HTTP 201 response. | **PASSED** |
| **Retrieval** | `test_api_list_events_and_detail` | Exercises `GET /api/v1/events` (pagination, filters) and `GET /api/v1/events/{id}` (detail, 404 on missing). | **PASSED** |

---

## 3. Concurrency & Reliability Assessment
- **Nested Savepoint Isolation:** Uses SQLAlchemy `begin_nested()` to gracefully trap database unique constraint violations (`uq_provider_event`).
- **Thread Safety:** Verified under multi-threaded connection pooling (`StaticPool` with `check_same_thread=False`).
