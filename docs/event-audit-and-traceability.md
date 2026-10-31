# Event Audit and Traceability — Phase 2.6

## 1. Overview & Audit Invariants
Financial regulatory compliance and incident analysis require comprehensive traceability for every payment event that enters RevenueRescueAI. From the instant a webhook hits the ingress controller, its lifecycle is stamped with an immutable correlation ID and logged in structured audit trails.

### Core Traceability Rules:
1. **Correlation Preservation**: Incoming headers (`X-Correlation-ID` or `X-Request-ID`) are propagated across all service and repository calls. If omitted, a cryptographic correlation ID (`corr_<hex>`) is automatically minted.
2. **Deterministic Fingerprints**: Every event record stores its SHA-256 `payload_hash` allowing auditors to mathematically prove that stored payloads match original ingress receipts.
3. **No Credential Logging**: Audit logs strictly exclude authorization headers, JWT tokens, bank credentials, and cardholder PANs.

---

## 2. Event Audit Trail Structure

When an event is ingested, the system generates structured JSON audit logs and persists operational receipts:

```json
{
  "timestamp": "2026-10-31T16:55:00.120Z",
  "level": "INFO",
  "logger": "revenuerescue.events",
  "message": "Event ingested: id=a5e9f8c1-1122-3344-5566-778899aabbcc, ext_id=evt_custom_001, type=PAYMENT_FAILED, duplicate=false, corr=corr_a1b2c3d4e5f6",
  "context": {
    "provider": "synthetic",
    "customer_reference": "cus_acme_corp",
    "amount_minor": 850000,
    "currency": "USD",
    "ingestion_status": "ACCEPTED",
    "signature_verified": true
  }
}
```

---

## 3. End-to-End Traceability Path
A developer or compliance officer can trace any event using either:
1. **External Event ID** (e.g. `evt_sim_99812` from gateway logs) $\to$ Query `GET /api/v1/events/{external_event_id}`.
2. **Correlation ID** (e.g. `corr_a1b2c3d4e5f6` from client response) $\to$ Search application logs or query `AuditEvent` records.
3. **Internal UUID** $\to$ Direct primary key lookup on `provider_webhook_events`.
