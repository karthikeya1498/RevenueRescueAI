# Event-to-Case Engine Integration

**Phase**: 2.7 — Recovery Case Management Engine  
**Author**: Karthikeya  
**Status**: APPROVED & VERIFIED  

---

## 1. End-to-End Execution Flow

This integration connects the Phase 2.6 Event Ingestion Engine with the Phase 2.7 Case Management Engine:

```
[Gateway Webhook / Synthetic Ingest]
                │
                ▼
1. Authentication & HMAC Verification
                │
                ▼
2. Schema & Business Invariant Validation
                │
                ▼
3. Normalization to CanonicalEventDTO
                │
                ▼
4. Relational Deduplication on (provider, external_event_id)
                │
                ├── Duplicate? ──► Return DUPLICATE receipt (No case mutation)
                │
                ▼
5. EventToCaseEngine.process_event(canonical)
                │
                ├── Payment Succeeded? ──► Resolve matching active case to RECOVERED
                │
                ├── Existing Case Match? ──► Update metadata, increment failure count, re-prioritize
                │
                └── New Failure? ──► Calculate Priority (CasePrioritizer)
                                  ──► Classify Risk (CaseRiskClassifier)
                                  ──► Persist RecoveryCase in DETECTED state
                                  ──► Record CaseStateTransition & AuditEvent
                │
                ▼
6. Mark ProviderWebhookEvent.processed = True
                │
                ▼
7. Commit Database Transaction & Return Enriched EventIngestResponseDTO
```

---

## 2. Transaction Safety and Rollback Behavior

- **Single Unit of Work**: Downstream case creation occurs within the active database session of the event ingestion service.
- **Savepoints for Concurrency**: Case persistence utilizes database savepoints (`session.begin_nested()`). If a concurrent worker inserts the same `case_key` before commit, the `IntegrityError` is safely caught, the savepoint rolls back, and the engine automatically falls back to an existing case update.
- **Processing Status Invariant**: An event is marked `processed = True` only after case creation or update commits successfully to disk.
