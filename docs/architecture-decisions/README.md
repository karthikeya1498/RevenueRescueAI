# RevenueRescueAI — Architecture Decision Records (ADRs)
## Phase 1.1: Formal Architectural Decisions Register

This directory contains the immutable Architecture Decision Records (ADRs) establishing the technical architecture, technology selections, and safety boundaries for RevenueRescueAI.

---

## Index of Approved Architecture Decision Records

| ADR ID | Decision Title | Status | Scope | Deciders |
| :--- | :--- | :--- | :--- | :--- |
| [ADR-001](ADR-001-architectural-style.md) | **Architectural Style — Modular Monolith** | Approved | System Architecture | Principal Architect, Full-Stack Lead |
| [ADR-002](ADR-002-frontend-technology.md) | **Frontend Technology — React 19, TypeScript, Vite & CSS Tokens** | Approved | Frontend Tier | Full-Stack Lead, UI/UX Lead |
| [ADR-003](ADR-003-backend-technology.md) | **Backend Technology — Python 3.11+, FastAPI & Pydantic v2** | Approved | Backend Gateway & Domain | Principal Architect, Backend Lead |
| [ADR-004](ADR-004-database-selection.md) | **Database Selection — PostgreSQL 16 & SQLite Dual-Dialect** | Approved | Persistence Tier | Database Architect, Fintech Lead |
| [ADR-005](ADR-005-ai-integration-strategy.md) | **AI Integration Strategy — Zero-Trust Advisor & Policy Supremacy** | Approved | AI & Safety Policy | AI Architect, Security Lead |
| [ADR-006](ADR-006-payment-simulator-design.md) | **Payment Simulator Design — Seeded Emulation & Fault Injection** | Approved | Simulation & Testing | Fintech Lead, QA Architect |
| [ADR-007](ADR-007-workflow-execution-strategy.md) | **Workflow Execution Strategy — Deterministic Finite State Machine** | Approved | Lifecycle Management | Principal Architect, Backend Lead |
| [ADR-008](ADR-008-api-communication.md) | **API Communication — RESTful Contracts & Real-Time WebSockets** | Approved | Integration Protocols | Full-Stack Lead, Principal Architect |
| [ADR-009](ADR-009-testing-strategy.md) | **Testing Strategy — Deterministic Pytest & Cypress E2E** | Approved | Quality Assurance | QA Architect, Full-Stack Lead |
| [ADR-010](ADR-010-deployment-approach.md) | **Deployment Approach — Containerized Docker Compose** | Approved | Infrastructure & DevOps| DevOps Lead, Principal Architect |

---

## Architectural Decision Standard Format
Every ADR adheres to the standard Michael Nygard format:
1. **Context:** Business and technical drivers necessitating the decision.
2. **Problem:** Core technical challenge to be resolved.
3. **Options Considered:** Viable alternatives evaluated during planning.
4. **Decision:** The chosen path forward.
5. **Reasons:** Technical, financial, and educational justifications.
6. **Trade-offs & Consequences:** Explicit benefits and acknowledged downsides.
7. **Reconsideration Conditions:** Measurable triggers that would prompt re-evaluating the decision.
