# Event Ingestion API Contracts — Phase 2.6

## 1. Overview
The Event Ingestion API layer provides secure endpoints for accepting, simulating, and querying revenue-risk events. All responses adhere to the standard JSON envelopes and RFC-7807 problem details established in Phase 1.3.

---

## 2. API Endpoints Specification

### 2.1 POST `/api/v1/events` — Ingest Canonical Event
Accepts structured revenue-risk events from authorized internal systems, partner integrations, or ingestion workers.

**Authentication:** Bearer JWT (`ROLE_OPERATOR`, `ROLE_ADMIN`, `ROLE_INGESTOR`).

**Request Headers:**
```http
POST /api/v1/events HTTP/1.1
Host: localhost:8000
Authorization: Bearer <jwt_access_token>
Content-Type: application/json
X-Correlation-ID: corr_a1b2c3d4e5f6
```

**Request Body (JSON):**
```json
{
  "event_id": "evt_custom_001",
  "event_type": "PAYMENT_FAILED",
  "provider": "synthetic",
  "occurred_at": "2026-10-31T12:00:00Z",
  "customer_reference": "cus_acme_corp",
  "payment_reference": "txn_fail_901",
  "amount_minor": 850000,
  "currency": "USD",
  "failure_code": "insufficient_funds",
  "failure_message": "Account has insufficient funds.",
  "metadata": {
    "subscription_tier": "enterprise",
    "region": "us-east-1"
  }
}
```

**Responses:**
- **201 Created (Fresh Event):**
  ```json
  {
    "accepted": true,
    "duplicate": false,
    "event_id": "a5e9f8c1-1122-3344-5566-778899aabbcc",
    "external_event_id": "evt_custom_001",
    "event_type": "PAYMENT_FAILED",
    "status": "ACCEPTED",
    "reason": "accepted",
    "correlation_id": "corr_a1b2c3d4e5f6",
    "occurred_at": "2026-10-31T12:00:00Z"
  }
  ```
- **200 OK (Duplicate Event):**
  ```json
  {
    "accepted": true,
    "duplicate": true,
    "event_id": "a5e9f8c1-1122-3344-5566-778899aabbcc",
    "external_event_id": "evt_custom_001",
    "event_type": "PAYMENT_FAILED",
    "status": "DUPLICATE",
    "reason": "duplicate_event_suppressed",
    "correlation_id": "corr_a1b2c3d4e5f6",
    "occurred_at": "2026-10-31T12:00:00Z"
  }
  ```

---

### 2.2 POST `/api/v1/webhooks/provider` — Gateway Webhook Ingress
Receives raw webhooks from external payment processors (e.g., Stripe, Razorpay) with HMAC-SHA256 signature verification.

**Headers:**
- `X-Signature-SHA256` (or `Stripe-Signature` / `X-Razorpay-Signature`): Required if `WEBHOOK_SIGNING_SECRET` is configured.
- `X-Event-ID`: Provider's unique event string.

**Responses:**
- **200 OK:** Payload validated, normalized, and persisted (or exact duplicate recognized).
- **401 Unauthorized:** Invalid or missing HMAC signature (`INVALID_SIGNATURE`).
- **409 Conflict:** Event ID re-submitted with conflicting payload content.

---

### 2.3 POST `/api/v1/events/simulate-failure` — Synthetic Event Simulator
Generates a deterministic synthetic payment failure for testing, staging, and demo environments.

**Authentication:** Bearer JWT (`ROLE_OPERATOR`, `ROLE_ADMIN`).

**Request Body:**
```json
{
  "customer_id": "cus_sim_9A12F",
  "amount_minor": 842000,
  "currency": "USD",
  "failure_code": "insufficient_funds",
  "failure_message": "Card has insufficient funds.",
  "metadata": {
    "simulation_run": "demo_batch_1"
  }
}
```

**Response (201 Created):**
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

### 2.4 GET `/api/v1/events` — List Ingested Events
Provides a paginated, filterable collection of recorded events.

**Query Parameters:**
- `provider` (string, optional): Filter by source (e.g. `stripe`, `synthetic`).
- `event_type` (string, optional): Filter by canonical type (`PAYMENT_FAILED`, etc.).
- `status` (string, optional): Filter by ingestion status (`ACCEPTED`, `DUPLICATE`).
- `processed` (boolean, optional): Filter by downstream processing flag (`true`/`false`).
- `page` (integer, default: 1): Page number (min: 1).
- `limit` (integer, default: 20, max: 100): Items per page.

---

### 2.5 GET `/api/v1/events/{event_id}` — Get Event Details
Returns full details of an ingested event by internal UUID or external event ID.
