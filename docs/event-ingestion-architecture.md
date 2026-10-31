# Event Ingestion Architecture — Phase 2.6

## 1. Executive Summary & Architectural Role
Phase 2.6 introduces the core business event ingestion engine of **RevenueRescueAI**. While earlier phases established infrastructure, databases, authentication, and dashboard reporting, this phase provides the front-line ingress point where real or simulated revenue-risk events enter the system.

The ingestion engine is architected to guarantee:
1. **Zero Data Loss**: Every accepted revenue-risk event is durably recorded in PostgreSQL.
2. **Strict Financial Idempotency**: Duplicate payment failure notifications and network retry storms are recognized and suppressed before duplicate side effects or double-processing can occur.
3. **Payload Sanitization (PII Protection)**: Raw credentials, card numbers (PANs), and CVVs are scrubbed before storage.
4. **Canonical Uniformity**: Heterogeneous event formats (Stripe, Razorpay, direct API, simulator) are translated into a single canonical event model.

---

## 2. End-to-End Event Ingestion Flow

```mermaid
sequenceDiagram
    autonumber
    actor Source as Event Source (Gateway / Operator / Simulator)
    participant GW as FastAPI Router (api/routes/events.py)
    participant Sec as Security & HMAC Verification
    participant Norm as EventNormalizer (services/event_normalizer.py)
    participant Val as EventValidator (services/event_validator.py)
    participant Dedup as EventDeduplicator (services/event_deduplicator.py)
    participant Repo as WebhookEventRepository (repositories/webhook_events.py)
    participant DB as PostgreSQL (provider_webhook_events)

    Source->>GW: POST /api/v1/events OR /api/v1/webhooks/provider
    GW->>Sec: Verify Bearer JWT or HMAC-SHA256 signature
    alt Authentication / Signature Invalid
        Sec-->>Source: HTTP 401 Unauthorized
    else Valid Credentials
        GW->>Norm: Normalize payload to CanonicalEventDTO
        Norm->>Norm: Scrub PII/PAN, normalize timestamps & ISO currencies
        Norm-->>GW: CanonicalEventDTO
        GW->>Val: Validate canonical event rules
        alt Validation Failure
            Val-->>Source: HTTP 422 Unprocessable Entity
        else Validation Success
            GW->>Dedup: evaluate_and_record(canonical)
            Dedup->>Dedup: Compute SHA-256 fingerprint
            Dedup->>Repo: record(provider, external_id, payload_hash)
            Repo->>DB: Atomic INSERT under nested transaction savepoint
            alt Conflicting Duplicate (Different Payload)
                Repo-->>Dedup: conflict = True
                Dedup-->>Source: HTTP 409 Conflict
            else Exact Duplicate (Identical Payload)
                Repo-->>Dedup: duplicate = True
                Dedup-->>GW: Existing event reference
                GW-->>Source: HTTP 200 OK (DUPLICATE acknowledged)
            else Fresh Ingestion
                Repo-->>Dedup: duplicate = False, accepted = True
                Dedup-->>GW: New event record
                GW-->>Source: HTTP 201 Created (ACCEPTED)
            end
        end
    end
```

---

## 3. Component Responsibilities Matrix

| Component | Class / File | Primary Responsibility |
| :--- | :--- | :--- |
| **Ingestion Router** | [`events.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/api/routes/events.py) | Transport boundary; parses HTTP requests, extracts headers (`X-Signature-SHA256`, `X-Event-ID`), and serializes responses. |
| **Security Layer** | [`deps.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/api/deps.py) & `verify_webhook_hmac` | Authenticates callers via JWT Bearer claims or verifies raw body HMAC signatures. |
| **Normalizer** | [`event_normalizer.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/event_normalizer.py) | Converts heterogeneous gateway JSON into `CanonicalEventDTO`; strips PII/PAN. |
| **Validator** | [`event_validator.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/event_validator.py) | Enforces invariants (non-negative minor amounts, 3-letter currency, required fields). |
| **Deduplicator** | [`event_deduplicator.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/event_deduplicator.py) | Computes deterministic SHA-256 fingerprint; detects exact vs conflicting duplicates. |
| **Event Service** | [`event_service.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/services/event_service.py) | Application coordinator; manages transaction boundaries and query orchestration. |
| **Repository** | [`webhook_events.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/repositories/webhook_events.py) | Executes atomic SQL queries against `provider_webhook_events`. |

---

## 4. Downstream Integration Boundary (Hand-off to Phase 2.7)
In accordance with strict scope restrictions, the ingestion engine persists incoming events with `processed = False` and `ingestion_status = "ACCEPTED"`. It **does not** automatically trigger recovery case opening, AI decision trees, or payment retries in Phase 2.6.

In **Phase 2.7 (Recovery Case Management Engine)**, downstream worker modules will consume these validated events from `provider_webhook_events` and automatically transition them into active `RecoveryCase` workflows.
