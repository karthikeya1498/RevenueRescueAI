# RevenueRescueAI — Repository Structure Specification
## Phase 1.1: Clean Directory Layout, Architectural Layers, and Dependency Rules

**Document Version:** 1.0.0  
**Status:** Approved Repository Architecture  
**Primary Authors:** Senior Full-Stack Engineer, Principal Software Architect, DevOps Lead  

---

## 1. Executive Summary & Design Principles

A well-structured repository reflects the system's architecture at a glance. In RevenueRescueAI, the directory layout is designed to:
1. **Mirror the Modular Monolith:** Frontend, backend, database migrations, tests, and documentation are cleanly partitioned at the root.
2. **Prevent Spaghetti Coupling:** Internal backend layers follow a strict one-way dependency rule (lower layers never import higher layers).
3. **Avoid Overengineering:** We avoid "clean architecture dogmatism" (e.g., 8 nested subfolders for an interface with one implementation). Directories exist only where justified by clear separation of concerns.
4. **Align with Existing Codebase:** Seamlessly incorporates the existing working FastAPI backend, React 19 frontend, and Alembic database migrations.

---

## 2. Complete Proposed Directory Tree

```
RevenueRescueAI/
├── .github/                                # GitHub Actions CI/CD workflows
│   └── workflows/
│       ├── backend-tests.yml               # Automated Pytest suite & linting
│       └── frontend-e2e.yml                # Cypress E2E automated test runs
│
├── backend/                                # Python FastAPI Backend Service
│   ├── app/                                # Core Application Source Code
│   │   ├── __init__.py
│   │   ├── main.py                         # Application factory & router wiring
│   │   │
│   │   ├── agents/                         # AI Recommendation & Reasoning Layer
│   │   │   ├── __init__.py
│   │   │   ├── brain.py                    # Agent brain orchestrator
│   │   │   ├── contracts.py                # Typed decision schemas (Pydantic v2)
│   │   │   └── providers.py                # Deterministic baseline & LLM provider
│   │   │
│   │   ├── api/                            # HTTP & WebSocket Ingress Gateway
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── health.py               # Liveness & readiness probes
│   │   │       ├── realtime.py             # WebSocket streaming for live dashboard
│   │   │       └── recovery_intelligence.py# Webhooks, cases, queue operations
│   │   │
│   │   ├── core/                           # Cross-Cutting Infrastructure & Utilities
│   │   │   ├── __init__.py
│   │   │   ├── config.py                   # Pydantic-settings typed configuration
│   │   │   ├── database.py                 # SQLAlchemy engine, session & mixins
│   │   │   ├── enums.py                    # Canonical domain states & action enums
│   │   │   ├── logging.py                  # Structured JSON logging configuration
│   │   │   └── observability.py            # Correlation IDs & request middleware
│   │   │
│   │   ├── evaluation/                     # 500-Scenario Batch Evaluation Engine
│   │   │   ├── __init__.py
│   │   │   ├── baselines.py                # Deterministic scoring baselines
│   │   │   ├── metrics.py                  # Financial & safety metric calculators
│   │   │   ├── report.py                   # Evaluation summary markdown generator
│   │   │   └── simulator.py                # Batch scenario runner (Seed 42)
│   │   │
│   │   ├── models/                         # Domain Entities & Persistence (SQLAlchemy)
│   │   │   ├── __init__.py
│   │   │   └── domain.py                   # Customers, Txns, Cases, Attempts, Audit
│   │   │
│   │   ├── policy/                         # Deterministic Safety Policy Engine
│   │   │   ├── __init__.py
│   │   │   └── safety.py                   # Hard invariant checks (INV-001..016)
│   │   │
│   │   ├── repositories/                   # Data Access & Idempotency Layer
│   │   │   ├── __init__.py
│   │   │   └── webhook_events.py           # Provider event deduplication repository
│   │   │
│   │   ├── resilience/                     # Circuit Breakers & Retry Handlers
│   │   │   ├── __init__.py
│   │   │   ├── executor.py                 # Bounded execution wrapper with timeouts
│   │   │   └── recovery.py                 # Resilient state recovery logic
│   │   │
│   │   ├── schemas/                        # API Request/Response Data Contracts
│   │   │   └── __init__.py
│   │   │
│   │   ├── services/                       # Application Business Logic Services
│   │   │   ├── __init__.py
│   │   │   ├── intelligence.py             # Decision preview & context aggregator
│   │   │   ├── risk_detection.py           # Ingestion, validation & risk scoring
│   │   │   ├── seed_service.py             # Deterministic test fixture seeding
│   │   │   └── verification.py             # 72h attribution evidence verification
│   │   │
│   │   ├── tools/                          # Bounded Financial Action Adapters
│   │   │   ├── __init__.py
│   │   │   ├── contracts.py                # Tool parameter & result contracts
│   │   │   ├── recovery.py                 # Provider charge & update tools
│   │   │   └── registry.py                 # Allow-listed tool registry
│   │   │
│   │   └── workflows/                      # State Machine & Lifecycle Management
│   │       ├── __init__.py
│   │       └── vertical_recovery.py        # End-to-end recovery state machine
│   │
│   ├── migrations/                         # Alembic Database Migrations
│   │   ├── env.py
│   │   └── versions/                       # Versioned SQL migration scripts
│   │
│   ├── scripts/                            # Operational CLI Scripts
│   │   └── run_evaluation.py               # Headless 500-scenario evaluation CLI
│   │
│   └── tests/                              # Comprehensive Pytest Suite (57+ tests)
│       ├── test_agent_brain_tools.py
│       ├── test_app_startup.py
│       ├── test_database_integrity.py
│       ├── test_evaluation_engine.py
│       ├── test_health.py
│       ├── test_observability.py
│       ├── test_phase2_models.py
│       ├── test_policy_resilience.py
│       ├── test_realtime.py
│       ├── test_recovery_intelligence.py
│       ├── test_resilient_executor.py
│       ├── test_risk_detection.py
│       └── test_vertical_workflow.py
│
├── frontend/                               # React 19 Client Dashboard
│   ├── cypress/                            # Cypress E2E automated test specs
│   ├── src/                                # Frontend Source Code
│   │   ├── main.tsx                        # Application root, state & view router
│   │   ├── realtime.ts                     # WebSocket client with auto-reconnect
│   │   ├── styles.css                      # Vanilla CSS custom tokens & layout
│   │   └── vite-env.d.ts
│   ├── index.html                          # Single-page HTML shell
│   ├── package.json                        # Dependencies (React 19, TypeScript, Vite)
│   ├── tsconfig.json                       # Strict TypeScript compiler options
│   └── vite.config.ts                      # Vite build & local proxy configuration
│
├── docker/                                 # Containerization Assets
│   ├── backend.Dockerfile                  # Multi-stage Python ASGI container
│   └── frontend.Dockerfile                 # Nginx static SPA container
│
├── docs/                                   # Architectural & Requirements Documentation
│   ├── architecture-decisions/             # ADR-001 through ADR-010
│   ├── architecture.md                     # Overall architectural blueprint
│   ├── system-architecture-diagrams.md     # Mermaid visual diagrams
│   ├── technology-stack.md                 # Technology evaluation & trade-offs
│   ├── component-responsibilities.md       # Module ownership & contracts
│   ├── data-architecture.md                # Financial data & integer precision
│   ├── ai-architecture.md                  # Responsible AI & safety policy gate
│   ├── payment-simulator-architecture.md   # Provider simulation & fault injection
│   ├── security-architecture.md            # Threat model & trust boundaries
│   ├── repository-structure.md             # This document
│   └── phase-1.1-acceptance-checklist.md   # Traceability & sign-off checklist
│
├── docker-compose.yml                      # Local multi-container orchestration
├── pyproject.toml                          # Python dependencies, Ruff & Pytest config
└── README.md                               # Project quickstart & overview
```

---

## 3. Layer Dependency Rules & Architecture Boundaries

To ensure that the codebase remains maintainable as features expand, we enforce strict **Layer Dependency Rules**:

```
[ API Routes ]  -->  [ Services / Workflows ]  -->  [ Domain Models / DB ]
      |                      |                              |
      v                      v                              v
[ Observability ]     [ Policy / Agent ]            [ Core Utilities ]
```

### Inviolable Rules:
1. **Domain Models are Pure Persistence:** `backend/app/models/` must NEVER import from `services/`, `workflows/`, `agents/`, or `api/`. Models represent database state and constraints only.
2. **AI Agents Have Zero Direct Execution:** `backend/app/agents/` must NEVER import `tools/recovery.py` directly. Agents produce structured intents, which must be passed to the Policy Engine.
3. **The Policy Engine is Autonomous:** `backend/app/policy/` must NEVER call external network services, LLMs, or payment providers. It evaluates pure mathematical rules against input objects.
4. **Tools are Allow-Listed:** `backend/app/tools/` must only expose tools registered in `registry.py`. Unregistered tools cannot be invoked by workflows.
5. **No Direct Database Access in Routes:** `backend/app/api/` routes must delegate business logic to services or workflows, avoiding ad-hoc SQL queries in HTTP handlers.
