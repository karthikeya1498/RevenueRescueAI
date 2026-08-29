# API Design

The API uses JSON, explicit Pydantic schemas, resource-oriented paths, and a future `/api/v1` version prefix. Invalid input should return a stable error envelope with `code`, `message`, `details`, and `correlation_id`; internal details and secrets must not leak.

`GET /health` is the Phase 1 exception and remains unversioned, cheap, deterministic, and provider-free. Future categories include risk events, recovery cases, attempts, audit traces, evaluations, and operator controls. Mutating endpoints will define idempotency keys, authorization, and replay semantics before implementation.
