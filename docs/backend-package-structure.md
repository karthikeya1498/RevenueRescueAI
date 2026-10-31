# RevenueRescueAI — Backend Package Architecture & Responsibility Matrix

## 1. Executive Summary

A clean package architecture ensures that a system remains modular, testable, and understandable as it scales. In financial recovery software, failing to maintain strict package boundaries leads to circular dependencies, spaghetti code, and accidental bypasses of safety policies.

RevenueRescueAI adheres to a **Layered Domain-Driven Modular Monolith Architecture**. High-level policy and business logic depend on domain models, while external payment frameworks and database libraries are isolated in infrastructure adapters.

---

## 2. Directory Tree of the Backend Application

```
backend/
├── app/
│   ├── main.py                     # Application factory & router wiring
│   │
│   ├── api/                        # HTTP transport layer
│   │   ├── routes/                 # FastAPI API route controllers
│   │   │   ├── health.py           # /health, /ready, /health/db probes
│   │   │   ├── realtime.py         # WebSocket live stream controllers
│   │   │   └── recovery_intelligence.py # Risk diagnosis & webhook routes
│   │   └── schemas/                # Inbound/outbound Pydantic DTOs
│   │
│   ├── core/                       # Shared technical infrastructure
│   │   ├── config.py               # Typed Pydantic Settings & environment
│   │   ├── database.py             # SQLAlchemy engine, session, & base mixins
│   │   ├── enums.py                # Ubiquitous domain vocabulary enumerations
│   │   ├── errors.py               # RFC-7807 problem details & global handlers
│   │   ├── logging.py              # Structured logging configuration
│   │   └── observability.py        # Request ID & access logging middleware
│   │
│   ├── models/                     # Relational domain entity definitions
│   │   └── domain.py               # SQLAlchemy ORM mapped entities
│   │
│   ├── repositories/               # Data access layer (CRUD & queries)
│   │   └── webhook_events.py       # Deduplication & raw event persistence
│   │
│   ├── services/                   # Core business domain logic
│   │   ├── intelligence.py         # AI diagnosis & prompt contextualization
│   │   ├── risk_detection.py       # Revenue-at-risk scoring algorithms
│   │   ├── verification.py         # Outcome verification & ledger attribution
│   │   └── seed_service.py         # Deterministic demo fixture generation
│   │
│   ├── policy/                     # Safety invariants & Policy Gate
│   │   └── safety.py               # Deterministic rule evaluation (Veto power)
│   │
│   ├── tools/                      # Bounded tool execution registry
│   │   ├── contracts.py            # Tool interface contracts & intent schemas
│   │   ├── recovery.py             # Payment simulator charge implementations
│   │   └── registry.py             # Allow-listed execution dispatcher
│   │
│   ├── workflows/                  # Finite state machine orchestration
│   │   └── vertical_recovery.py    # End-to-end recovery coordinator
│   │
│   ├── resilience/                 # Network fault tolerance & backoff
│   │   ├── executor.py             # Circuit breakers & timeout wrappers
│   │   └── recovery.py             # Checkpoint resumption primitives
│   │
│   └── evaluation/                 # 500-scenario deterministic benchmark
│       ├── baselines.py            # Static comparison recovery strategies
│       ├── metrics.py              # Recovery rate & safety compliance math
│       ├── report.py               # Benchmark markdown report generator
│       └── simulator.py            # Seeded virtual payment network
│
├── migrations/                     # Alembic schema version scripts
│   ├── env.py                      # Migration runtime runner
│   └── versions/                   # Versioned DDL migration scripts
│
├── tests/                          # Pytest automated test suite
├── .env.example                    # Documented configuration template
├── .gitignore                      # Python & SQLite exclusions
├── compose.yaml                    # Local containerized PostgreSQL setup
├── Dockerfile                      # Non-root container build file
└── README.md                       # Developer setup & operational manual
```

---

## 3. Package Responsibility Matrix

| Package Path | Primary Responsibility | Owned Data & Concepts | Permitted Inbound Calls From | Forbidden Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| `app.core` | Application lifecycle, settings, database engine, errors, logging. | Configuration, DB engine, standard error responses. | Every package in `app.*`. | Must NOT import from `services`, `policy`, `workflows`, or `api`. |
| `app.models` | Declarative SQLAlchemy ORM entity models. | Relational database schema mappings (`recovery_cases`, `audit_events`). | `repositories`, `services`, `workflows`. | Must NOT import from `api` or `services`. |
| `app.api` | HTTP/REST presentation, JSON deserialization, route controllers. | HTTP request/response DTOs, endpoint status codes. | External HTTP clients, browsers, webhooks. | Route controllers must NOT contain raw SQL queries or direct DB transaction logic. |
| `app.services`| Pure business logic (risk calculation, AI advisory, verification). | Risk scores, diagnosis context, attribution verdicts. | `workflows`, `api.routes`. | Must NOT directly call external network APIs without going through `app.tools` or `app.resilience`. |
| `app.policy` | Deterministic safety rule enforcement and veto decisions. | 6 safety invariants, retry budgets, quiet hours. | `workflows`, `api.routes`. | Must NEVER depend on untrusted AI outputs or execute external side effects. |
| `app.tools` | Bounded tool execution registry with strict allow-listing. | Idempotency keys, tool schemas, simulated charges. | `workflows` (ONLY after Policy Gate approval). | Tools cannot execute without receiving a valid authorization token. |
| `app.workflows`| Finite state machine coordination and event sequencing. | Case state lifecycle transitions (`DETECTED` -> `RECOVERED`). | `api.routes`, event ingestion listeners. | Workflows must NOT bypass the Policy Gate or Verification services. |
| `app.evaluation`| 500-scenario deterministic benchmarking (Seed 42). | Synthetic scenarios, ground truth comparison, metric rates. | CLI test scripts, admin evaluation endpoints. | Must NOT write to production tables. |

---

## 4. Architectural Dependency Inversion Rule

```
   [ Transport: app.api ]
             │
             ▼
   [ Coordination: app.workflows ]
      │             │             │
      ▼             ▼             ▼
[ Services ]   [ Policy Gate ]   [ Bounded Tools ]
      │             │             │
      └─────────────┼─────────────┘
                    ▼
          [ Domain: app.models ]
                    │
                    ▼
         [ Foundation: app.core ]
```

### Key Architectural Safeguards:
1. **Unidirectional Dependency:** Dependencies only flow downward toward `app.core`. `app.core` has zero knowledge of `app.services` or `app.api`.
2. **AI Cannot Execute Tools:** The AI package (`app.services.intelligence`) cannot call `app.tools`. It delivers an advisory suggestion to `app.workflows`, which must route it through `app.policy.safety` before `app.tools` can be invoked.
3. **Audit Immutability:** Audit rows are emitted by `app.workflows` and saved directly via transactional database models in `app.models`, ensuring zero data loss during network crashes.
