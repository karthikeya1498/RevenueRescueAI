# Event Deduplication and Idempotency — Phase 2.6

## 1. Executive Summary & Financial Imperative
Payment gateways utilize at-least-once delivery guarantees for webhooks. In real-world production networks, network timeouts, partner retries, and concurrent worker threads routinely deliver the exact same event multiple times.

If duplicate payment failure events were processed independently:
- An operator might schedule duplicate payment retries.
- A customer might be charged twice.
- False alarms and skewed recovery metrics would corrupt executive dashboards.

RevenueRescueAI prevents duplicate event processing through a dual-layer idempotency defense combining **cryptographic payload fingerprinting** with **database-level unique constraints**.

---

## 2. Deduplication Identity & Scoping
Event uniqueness is evaluated strictly within a composite scope:
$$\text{Event Key} = (\text{provider}, \text{external\_event\_id})$$

External event IDs are **not** assumed to be globally unique across providers. For instance, Stripe event `evt_100` and Razorpay event `evt_100` are recognized as independent, non-colliding events.

---

## 3. Cryptographic Payload Fingerprinting
The deduplication component ([`EventDeduplicator`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/event_deduplicator.py)) serializes the canonical event's business attributes into a sorted JSON string and calculates its SHA-256 digest:

```python
fingerprint_data = {
    "event_type": event.event_type,
    "provider": event.provider.lower(),
    "customer_reference": event.customer_reference,
    "payment_reference": event.payment_reference,
    "amount_minor": event.amount_minor,
    "currency": event.currency.upper(),
    "failure_code": event.failure_code,
    ...
}
payload_hash = sha256(json.dumps(fingerprint_data, sort_keys=True)).hexdigest()
```

---

## 4. Duplicate Scenarios & System Behavior

### Scenario A: Exact Duplicate (Idempotent Retry)
- **Condition:** Same `(provider, external_event_id)` AND identical `payload_hash`.
- **System Action:**
  - Recognizes previous record in `provider_webhook_events`.
  - Avoids creating a duplicate database entry.
  - Skips downstream triggers.
  - Returns HTTP `200 OK` with:
    ```json
    {
      "accepted": true,
      "duplicate": true,
      "status": "DUPLICATE",
      "reason": "duplicate_event_suppressed"
    }
    ```

### Scenario B: Conflicting Duplicate (Payload Re-use Attack / Conflict)
- **Condition:** Same `(provider, external_event_id)` BUT differing `payload_hash`.
- **System Action:**
  - Detects that an existing event ID was re-used with contradictory financial amounts or customer details.
  - Rejects request with HTTP `409 Conflict`:
    ```json
    {
      "error_code": "CONFLICTING_DUPLICATE_EVENT",
      "message": "Event 'evt_100' from provider 'stripe' already exists with differing payload content."
    }
    ```
  - Original stored event record is **never** overwritten.

### Scenario C: Concurrent Duplicate Race Condition
- **Condition:** Two identical webhook delivery requests arrive simultaneously on different application threads.
- **System Action:**
  - Thread 1 and Thread 2 both check existence and initially find no record.
  - Thread 1 commits `INSERT INTO provider_webhook_events`.
  - Thread 2 attempts `INSERT`, triggering PostgreSQL database unique constraint `uq_provider_event`.
  - Thread 2 catches the database `IntegrityError` inside a nested transaction savepoint (`begin_nested()`), rolls back the inner savepoint, re-queries the row, and returns the idempotent duplicate verdict cleanly without crashing.
