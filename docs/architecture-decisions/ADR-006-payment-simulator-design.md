# ADR-006: Payment Simulator Design — Seeded Emulation & Controlled Faults

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Senior Fintech Engineer, QA Architect  

---

## 1. Context
Developing and validating recovery workflows against live payment processors introduces real gateway transaction fees, risks accidental double charges, and prevents deterministic testing of rare failure modes (e.g., 504 timeouts or delayed settlement).

## 2. Problem
How can the system emulate realistic payment provider behavior with reproducible outcomes and zero external dependencies?

## 3. Options Considered
1. **Live Payment Gateway (Stripe/Adyen Test Mode):** Connecting directly to public sandbox endpoints.
2. **Third-Party Mocking Servers (WireMock / Prism):** External HTTP mock containers.
3. **Dedicated In-Process Stateful Simulator Adapter (Seed 42):** A native Python adapter emulating card charges, soft/hard declines, gateway timeouts, idempotency caching, and verifiable evidence generation.

## 4. Decision
We choose a **Dedicated In-Process Stateful Simulator Adapter with Deterministic Pseudo-Random Seeding (Seed 42)**.

## 5. Reasons
- **100% Deterministic Reproducibility:** Fixed-seed pseudo-random generation guarantees that the 500-scenario evaluation engine yields identical metrics across different environments and git commits.
- **Controlled Fault Injection:** Allows systematic testing of transient timeouts (HTTP 504), rate limits (HTTP 429), stolen card locks, and delayed settlements that sandboxes cannot reliably trigger.
- **Zero Cost & Zero Network Flakiness:** Runs in-memory in microseconds without internet access or sandbox rate limits.
- **Strict Boundary Separation:** All synthetic entities are prefixed (`sim_`, `synthetic`), and live API keys are blocked by startup tripwires.

## 6. Trade-offs & Consequences
- **Positive:** Fast test suites, complete failure coverage, safe local development.
- **Negative:** Does not test live payment gateway network TLS handshakes or undocumented third-party sandbox quirks.

## 7. Reconsideration Conditions
Re-evaluate live gateway integration during a future pilot phase with an approved corporate sandbox account.
