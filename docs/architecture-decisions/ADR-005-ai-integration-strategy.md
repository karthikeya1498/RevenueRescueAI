# ADR-005: AI Integration Strategy — Zero-Trust Advisor with Policy Supremacy

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** AI Systems Architect, Security Engineer, Principal Architect  

---

## 1. Context
Revenue recovery requires contextual analysis of payment failures, prior attempt histories, and customer notes. However, probabilistic LLMs suffer from hallucinations, non-deterministic outputs, and vulnerability to prompt injection.

## 2. Problem
How can the system leverage AI reasoning for failure diagnosis and recommendation without risking unauthorized financial side effects or policy violations?

## 3. Options Considered
1. **Fully Autonomous Agentic LLM:** An LLM with direct access to payment API tools that executes actions autonomously.
2. **Pure Deterministic Rules:** Hardcoded if/else statements with zero machine learning or natural language reasoning.
3. **Zero-Trust AI Advisor with Deterministic Policy Supremacy (Hybrid):** An AI layer that outputs structured proposals into a rigid Pydantic contract, with an absolute deterministic policy gate holding veto authority.

## 4. Decision
We choose the **Zero-Trust AI Advisor with Deterministic Policy Supremacy (Hybrid Architecture)**, backed by a **100% offline Deterministic Logistic Baseline (`deterministic-logistic-v1`)** and an optional external LLM advisor.

## 5. Reasons
- **Absolute Financial Safety:** The AI possesses zero execution permissions and zero tool-calling privileges. It can propose `RETRY_NOW`, but the Policy Engine enforces safety invariants (INV-001 through INV-016), retry budgets, and cooling-off periods.
- **Resilient Fallback:** If the external LLM times out (>3.0s), errors, returns malformed JSON, or attempts prompt injection, the system falls back seamlessly to the local baseline model.
- **Zero Cost for MVP:** The system runs completely free of external API token charges using the deterministic baseline.
- **Interview-Grade Design:** Demonstrates mature understanding of AI safety in high-stakes financial domains.

## 6. Trade-offs & Consequences
- **Positive:** Immune to rogue AI behavior, compliant with card brand retry mandates, testable offline.
- **Negative:** Requires maintaining both the deterministic baseline algorithm and the structured Pydantic decision schema.

## 7. Reconsideration Conditions
Re-evaluate autonomous tool-calling only in non-financial, non-destructive exploratory domains (e.g., generating internal developer documentation).
