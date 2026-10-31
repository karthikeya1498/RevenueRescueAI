# ADR-003: Backend Technology — Python 3.11+, FastAPI & Pydantic v2

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Principal Software Architect, Senior Backend Engineer  

---

## 1. Context
The backend service must ingest high-velocity webhooks, validate financial payloads, orchestrate complex state machines, integrate AI reasoning models, and enforce strict safety policies.

## 2. Problem
Which backend runtime and framework provides the optimal combination of type-safe validation, asynchronous throughput, AI ecosystem integration, and beginner readability?

## 3. Options Considered
1. **Java with Spring Boot:** Robust enterprise framework with mature dependency injection and transaction management.
2. **Node.js with NestJS:** TypeScript enterprise framework running on the V8 event loop.
3. **Python 3.11+ with FastAPI & Pydantic v2:** Modern asynchronous ASGI framework built on Rust-backed data validation and native type hints.
4. **Go (Golang):** High-concurrency compiled language with lightweight goroutines.

## 4. Decision
We choose **Python 3.11+ with FastAPI, Pydantic v2, and Uvicorn**.

## 5. Reasons
- **Pydantic v2 Data Safety:** Incoming webhooks and financial parameters are validated instantly by Pydantic's core engine, rejecting negative amounts and invalid schemas with HTTP 422 before reaching business logic.
- **AI/ML Native Ecosystem:** Integrates seamlessly with deterministic mathematical baseline algorithms and modern LLM SDKs without multi-language IPC or external wrappers.
- **Developer Accessibility:** Expressive, clean Python syntax allows novice developers to easily trace the recovery lifecycle from ingestion to audit logging.
- **Existing Repository Continuity:** Preserves the existing, verified test suite (57 passing tests) without rewriting working modules.

## 6. Trade-offs & Consequences
- **Positive:** Automatic OpenAPI documentation (`/docs`), fast asynchronous I/O, seamless integration with SQLAlchemy 2.0.
- **Negative:** Lower raw CPU compute performance compared to compiled Go/Rust (irrelevant for I/O-bound webhook and database operations).

## 7. Reconsideration Conditions
Re-evaluate if a standalone module requires sub-millisecond cryptographic hashing or high-frequency trading throughput.
