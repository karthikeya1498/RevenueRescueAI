# RevenueRescue AI

RevenueRescue AI is an **agentic revenue recovery system** planned to detect revenue at risk, gather context, select a bounded recovery strategy, pass it through deterministic policy, execute controlled tools, verify outcomes, and audit every meaningful decision.

## Current milestone

**Phase 1 — Engineering Foundation & Architecture Baseline.** This repository currently contains a runnable FastAPI skeleton, a minimal React/Vite/TypeScript surface, typed configuration, logging conventions, tests, documentation, and future-state boundaries. It is **not** a production financial recovery system and performs no real payment or customer action.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --app-dir backend --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Backend verification: `pytest`. Frontend verification: `cd frontend && npm run build`.

## Navigation

| Area | Purpose |
|---|---|
| `backend/app` | Explicit future boundaries for APIs, core, models, schemas, services, agents, tools, policies, workflows, and repositories |
| `backend/tests` | Executable foundation behavior tests |
| `frontend/src` | Minimal presentation entry point; no recovery business logic |
| `docs/adr` | Architecture decisions and consequences |
| Root `.md` files | Constitution, architecture, safety, failure, evaluation, and contribution guidance |

Read [ARCHITECTURE.md](ARCHITECTURE.md) first, then [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md). The roadmap is documented in [PROJECT_SPECIFICATION.md](PROJECT_SPECIFICATION.md).

## Phase boundary

Phase 2 may begin only after Karthikeya reviews the Phase 1 completion report and explicitly approves progression. No evaluation results, financial claims, production readiness, or autonomous recovery capability are claimed here.
