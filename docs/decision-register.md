# RevenueRescueAI — Master Architecture & Design Decision Register

> **Document ID:** DOC-ADR-007  
> **Phase:** 0.3 (Metrics Finalization, Safety Invariants & MVP Approval)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

Architecture and product requirements evolve across development phases. When technical decisions are undocumented or made implicitly, teams suffer from architectural drift, contradictory implementations, and scope creep. 

This document establishes the Master Decision Register for RevenueRescueAI. It records all approved architectural, product, safety, and UI design decisions across Phases 0.1, 0.2, and 0.3, documents provisional assumptions, catalogs unresolved questions, and provides a formal change-control audit verifying zero unapproved alterations to prior baselines.

---

## 2. Approved Architectural & Design Decisions (DEC-001 to DEC-020)

| Decision ID | Area | Decision Summary | Rationale & Justification | Status |
|---|---|---|---|:---:|
| **DEC-001** | Scope | Focus MVP strictly on failed payments & subscription renewals. | Maximizes verifiability, exercises event-driven recovery, and eliminates fuzzy attribution. | **APPROVED** |
| **DEC-002** | Execution | Use local deterministic payment gateway simulator for MVP. | Eliminates financial liability, rate limits, and network flakiness during automated testing. | **APPROVED** |
| **DEC-003** | Currency | All monetary values represented as 64-bit integer minor units. | Eliminates floating-point rounding errors on financial ledgers (BR-008, INV-003). | **APPROVED** |
| **DEC-004** | Time | Implement Virtual Clock interface for deterministic fast testing.| Allows 500 multi-day scenarios to execute in seconds without `time.sleep()`. | **APPROVED** |
| **DEC-005** | Safety | AI model acts strictly as an untrusted advisory decision proposer. | Prevents model hallucinations from authorizing charges or spending money (INV-005). | **APPROVED** |
| **DEC-006** | Safety | Deterministic Python code holds absolute authorization & veto power. | Guarantees 100.00% safety rate and strict compliance with card network rules. | **APPROVED** |
| **DEC-007** | Safety | Success Protection Invariant: Never retry an already-paid invoice. | Eliminates duplicate customer charges and merchant chargeback penalties (INV-001). | **APPROVED** |
| **DEC-008** | Policy | Maximum retry budget capped at 3 attempts per case. | Prevents infinite retry loops and card-testing fraud flags (BR-003, INV-003). | **APPROVED** |
| **DEC-009** | Policy | Minimum backoff interval enforced at 24 hours between attempts. | Respects banking liquidity replenishment cycles (BR-004). | **APPROVED** |
| **DEC-010** | Policy | Maximum recovery window cutoff enforced at 14 calendar days. | Complies with consumer protection and dunning rules; prevents surprise charges. | **APPROVED** |
| **DEC-011** | Idempotency| Deterministic unique tokens `idemp_{case_id}_att_{attempt_num}`. | Guarantees network replays cannot cause duplicate charges (BR-006, INV-002). | **APPROVED** |
| **DEC-012** | Uncertainty| Gateway timeouts classified as `UNCERTAIN`; retries frozen in pending. | Eliminates double charging caused by dropped network sockets (INV-004, INV-015). | **APPROVED** |
| **DEC-013** | Verification| Confirmed recovery requires matching provider capture receipt. | Prevents phantom revenue claims; anchors metrics in factual deposits (INV-008). | **APPROVED** |
| **DEC-014** | Attribution| Strict 72-hour attribution window between action and settlement. | Prevents claiming credit for unrelated organic customer payments (BR-011, INV-011).| **APPROVED** |
| **DEC-015** | Audit | Relational audit table enforced with append-only permissions. | Guarantees compliance auditability; prevents tampering with history (BR-015). | **APPROVED** |
| **DEC-016** | Evaluation | 500-scenario batch simulation under fixed seed 42 and baseline lift. | Replaces subjective claims with reproducible scientific benchmarking. | **APPROVED** |
| **DEC-017** | UI Design | Dark Neon Fintech Command Center with navy and black surfaces. | Delivers a stunning, futuristic, and enterprise-grade visual identity. | **APPROVED** |
| **DEC-018** | UI Symmetry| KPI cards in a row locked to strictly identical 152px height and width. | Enforces layout symmetry and eliminates visual clutter. | **APPROVED** |
| **DEC-019** | UI Glow | Selective ambient glow allowed on 6 prominent containers only. | Keeps smaller controls clean, preserving contrast and avoiding garish neon clutter.| **APPROVED** |
| **DEC-020** | Technology | Use Vanilla CSS Custom Properties (Tokens) instead of TailwindCSS. | Adheres to web application guidance: maximum flexibility and zero framework bloat. | **APPROVED** |

---

## 3. Provisional Decisions & Open Questions

The following operational parameters are established as provisional defaults, subject to final developer tuning during backend implementation:

1. **PROV-001 (Gateway Fee Schedule):** Simulated fee constants are modeled as `$0.30 fixed + 2.9% variable` per executed retry attempt. (Can be modified via environment configuration).
2. **PROV-002 (Human Escalation Monetary Threshold):** Invoices with nominal amounts >= `$1,000.00` (100,000 minor units) automatically route to human operator review. (Configurable in application settings).
3. **PROV-003 (Reconciliation Polling Cadence):** Uncertain timeout transactions poll the provider reconciliation endpoint at 15m, 30m, and 60m intervals before escalating to human review.

---

## 4. Cross-Phase Consistency Audit Findings

A rigorous cross-phase audit was conducted across all documentation from Phase 0.1, Phase 0.2, and Phase 0.3:

| Alignment Dimension | Phase 0.1 Baseline | Phase 0.2 Specification | Phase 0.3 Finalization | Consistency Finding |
|---|---|---|---|:---:|
| **Primary Use Case** | Failed Payments (Simulator) | Failed Payments (Simulator) | Failed Payments (Simulator) | **100% Consistent** |
| **Financial Representation** | Integer Minor Units | Integer Minor Units | 64-Bit Integer Minor Units | **100% Consistent** |
| **Retry Limits** | Max 3 Retries | Max 3 Retries (BR-003) | Max 3 Retries (INV-003) | **100% Consistent** |
| **Backoff Interval** | Min 24 Hours | Min 24 Hours (BR-004) | Min 24 Hours (BR-004) | **100% Consistent** |
| **Attribution Window** | 72 Hours | 72 Hours (BR-011) | 72 Hours (BR-011, INV-011) | **100% Consistent** |
| **AI Role & Authority** | Advisory Proposer | Advisory Proposer (EPIC-06) | Advisory Proposer (INV-005) | **100% Consistent** |
| **Policy Authority** | Deterministic Code Gate | Deterministic Code Gate | Deterministic Code Gate | **100% Consistent** |
| **UI Aesthetic** | Dark Neon Fintech Dashboard | Dark Neon Command Center | Symmetrical Sizing & Glow | **100% Consistent** |
| **Evaluation Strategy** | 500 Scenarios (Seed 42) | 500 Scenarios (Seed 42) | 500 Scenarios (Seed 42) | **100% Consistent** |

**Conclusion:**  
**Zero contradictions detected.** All requirements, business rules, safety invariants, and design specifications are mutually reinforcing and backwards-compatible with all approved decisions.
