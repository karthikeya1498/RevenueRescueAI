# Development Event Simulator — Phase 2.6

## 1. Purpose and Operational Guidelines
The **Event Simulator** provides authorized developers, QA engineers, and automated testing pipelines with a safe, controlled mechanism to inject revenue-risk events into RevenueRescueAI without connecting live third-party payment gateways.

### Safety Invariants:
1. **Explicit Source Labeling**: All simulator-generated events are tagged with provider `"synthetic"` and external event IDs prefixed with `evt_sim_`. They are never mislabeled as production bank events.
2. **Deterministic Behavior**: Identical simulator inputs produce predictable, repeatable outcomes.
3. **No Fabricated Revenue**: Simulator failures are recorded truthfully as at-risk revenue. The simulator **never** claims or generates unverified recovered revenue.
4. **Role Protection**: Ingestion through `/api/v1/events/simulate-failure` requires authenticated JWT credentials with `ROLE_OPERATOR` or `ROLE_ADMIN`.

---

## 2. Simulator Endpoint Reference

### Endpoint: `POST /api/v1/events/simulate-failure`

**Authentication:** Bearer Token (`ROLE_OPERATOR`, `ROLE_ADMIN`).

**Request Payload:**
```json
{
  "customer_id": "cus_sim_9A12F",
  "amount_minor": 842000,
  "currency": "USD",
  "failure_code": "insufficient_funds",
  "failure_message": "Card has insufficient funds.",
  "metadata": {
    "scenario": "subscription_renewal_failure",
    "tier": "enterprise"
  }
}
```

**Response (HTTP 201 Created):**
```json
{
  "accepted": true,
  "duplicate": false,
  "event_id": "8c31fe90-4455-6677-8899-aabbccddeeff",
  "external_event_id": "evt_sim_9a8b7c6d5e",
  "event_type": "PAYMENT_FAILED",
  "status": "ACCEPTED",
  "reason": "accepted",
  "correlation_id": "corr_778899aabb",
  "occurred_at": "2026-10-31T16:55:00Z"
}
```

---

## 3. Supported Simulation Scenarios

| Scenario # | Scenario Name | Recommended `failure_code` | Expected Downstream Behavior |
| :---: | :--- | :--- | :--- |
| **01** | Insufficient Funds | `insufficient_funds` | High-urgency recovery risk, candidate for smart billing retry. |
| **02** | Card Expired | `card_expired` | Non-retryable card decline; candidate for customer payment update outreach. |
| **03** | 3D-Secure Required | `authentication_required` | Requires interactive cardholder verification. |
| **04** | Do Not Honor | `do_not_honor` | Bank policy refusal; requires customer bank inquiry. |
| **05** | Network / Timeout | `processing_error` | Temporary network error; high recovery retry probability. |
