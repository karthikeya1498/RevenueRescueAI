# ADR-001: Architectural Style — Modular Monolith

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Principal Software Architect, Senior Full-Stack Engineer, AI Systems Architect  

---

## 1. Context
RevenueRescueAI requires strict financial data consistency, atomic state transitions, fast in-memory execution, and comprehensive audit logging across the failed-payment recovery lifecycle. The system is currently in its MVP phase, targeting both interview-grade architectural clarity and production reliability.

## 2. Problem
What high-level architectural style should govern the design and deployment of the application without introducing premature operational complexity?

## 3. Options Considered
1. **Ad-Hoc Monolith:** A single codebase without internal layer boundaries or strict module encapsulation.
2. **Modular Monolith:** A single deployable application partitioned into strictly decoupled internal modules with explicit public interfaces and layer dependency rules.
3. **Microservices Architecture:** 6–10 independent network services (Auth, Ingestion, Risk, Workflow, Policy, AI, Simulator, Audit) communicating via HTTP/gRPC.
4. **Pure Event-Driven Broker Architecture:** Services orchestrated via an external message broker (RabbitMQ / Apache Kafka).

## 4. Decision
We choose the **Modular Monolith** architectural style. The backend is deployed as a single Python ASGI process with strictly enforced internal packages (`api`, `core`, `models`, `policy`, `services`, `tools`, `workflows`, `evaluation`).

## 5. Reasons
- **Atomic ACID Guarantees:** Financial recovery requires updating case state, inserting attempt records, recording transitions, and logging audit events in a single atomic database transaction. Distributed transactions (2PC/Sagas) in microservices introduce extreme failure modes.
- **Zero Network Latency:** In-memory function calls execute in sub-milliseconds, whereas inter-service REST/gRPC adds latency and network serialization overhead.
- **Operational Simplicity:** Requires only one application container and one database container, keeping operating costs near zero and making local development effortless.
- **Defensibility:** FAANG engineering interviewers heavily penalize candidates who propose microservices for early-stage MVPs without traffic justification.

## 6. Trade-offs & Consequences
- **Positive:** Rapid development velocity, simple debugging with standard IDE breakpoints, atomic rollbacks on failure, fast test runs (57 tests in 7 seconds).
- **Negative:** Independent scaling of single modules (e.g., webhook ingestion) is not natively isolated at the OS process level.

## 7. Reconsideration Conditions
Re-evaluate microservice extraction only if inbound webhook traffic exceeds 10,000 requests per second or if distinct engineering teams (>25 engineers) require separate release cycles.
