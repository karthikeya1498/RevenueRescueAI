# RevenueRescue AI

**RevenueRescue AI** is an agentic revenue-recovery system designed to respond to payment failures and other revenue-at-risk events with bounded reasoning, deterministic policy controls, controlled tools, verification, and complete auditability.

> **Core principle:** an AI agent may propose a recovery action, but deterministic policy and resilience layers decide whether that action is permitted, how uncertainty is handled, and when the system must stop or escalate.

**Author:** Karthikeya  
**Repository:** [github.com/karthikeya1498/RevenueRescueAI](https://github.com/karthikeya1498/RevenueRescueAI)

## What is implemented

| Layer | Status | Scope |
|---|---:|---|
| Phase 1 | Complete | Foundation, architecture, conventions, tests, ADRs, documentation |
| Phase 2 | Complete | SQLAlchemy models, Alembic migration, deterministic synthetic fixtures |
| Phase 3 | Complete | Deterministic failed-payment and stale-pending risk detection |
| Phase 4 | Complete | Structured agent brain with strict bounded decisions |
| Phase 5 | Complete | Allow-listed dry-run tools and controlled tool contracts |
| Phase 6 | Complete | Retry budgets, duplicate prevention, success protection, stop and escalation rules |
| Phase 7 | Complete | Failure classification, timeout handling, uncertainty preservation, resumability |
| Phase 8 | Complete | Reproducible batch simulation and recovery/action-quality metrics |
| Phase 9 | Complete | Visual command center, recovery queue, Evaluation Lab, agent traces |
| Phase 10 | Complete | Observability, readiness probes, CI, container and Compose deployment configuration |
| Phase 11 | Prepared | README, five-minute video materials, failure story, architecture explanation, and mock panel |

### Production-gap closure capabilities

The repository also includes an inspectable `deterministic-logistic-v1` recovery-probability estimator, failure classification, 0–100 risk scoring, expected-value action ranking with integer minor-unit costs, explainable rationale, signed provider-webhook verification, event-id idempotency, verified recovery attribution, durable webhook/evidence schema, and counterfactual baseline comparison. These controls are deliberately labeled as prototype or synthetic where provider evidence is unavailable; they do not turn synthetic results into production claims.

The repository remains a **simulation and engineering demonstration**. It does not execute real payments, send customer messages, or claim production financial effectiveness. The persistence review and rewrite is documented in [DATABASE_REVIEW_AND_REWRITE.md](docs/DATABASE_REVIEW_AND_REWRITE.md).

## System flow

```text
Revenue-risk event
        ↓
Deterministic risk detection
        ↓
Context assembly
        ↓
Structured agent reasoning
        ↓
Safety and policy validation
        ↓
Controlled tool boundary
        ↓
Resilient execution and verification
        ↓
Recover / retry / escalate / stop
        ↓
Audit and evaluation
```

## Verified Phase 8/9 baseline

The checked-in report at [`artifacts/evaluation_report_500.json`](artifacts/evaluation_report_500.json) was generated with seed `42` and rule version `phase8.v1`.

| Metric | Result |
|---|---:|
| Scenarios | 500 |
| At-risk cases | 400 |
| Recovered cases | 182 |
| At-risk revenue | 2,163,200 minor units |
| Recovered revenue | 980,887 minor units |
| Revenue recovery rate | 45.34% |
| Case recovery rate | 45.50% |
| Action accuracy | 20.00% |
| Safety rate | 100.00% |
| Failures / escalations / verifications | 181 / 90 / 91 |

These are **synthetic regression metrics**, not a forecast or claim about real customer revenue.

## Run locally

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
ruff check backend/app backend/tests backend/migrations backend/scripts
uvicorn app.main:app --app-dir backend --reload
```

The service exposes `GET /health` for liveness and `GET /ready` for configuration readiness. Every HTTP response includes an `x-request-id`; the access logger emits one structured JSON event per request.

### Evaluation

```bash
python backend/scripts/run_evaluation.py \
  --seed 42 \
  --count 500 \
  --output artifacts/evaluation_report_500.json
```

### Frontend

```bash
cd frontend
npm ci --omit=dev
npm run build
npm run dev
```

The dashboard provides the command center, recovery queue, Evaluation Lab, transaction-level traces, and a structured trace drawer. It runs in simulation mode and intentionally has no side-effecting recovery controls. The backend additionally exposes `POST /api/v1/recovery/decision-preview`, `POST /api/v1/recovery/strategy-comparison`, and a signature-protected provider webhook boundary.

## Deployment configuration

The Phase 10 baseline includes [`docker/backend.Dockerfile`](docker/backend.Dockerfile), [`docker-compose.yml`](docker-compose.yml), and [`ci.yml`](.github/workflows/ci.yml). The container runs as a non-root user, has a liveness health check, and uses PostgreSQL-shaped configuration in Compose. Secrets are supplied through environment configuration; no credentials are checked in.

```bash
docker compose up --build
```

## Repository guide

| Path | Responsibility |
|---|---|
| `backend/app/agents` | Structured agent contracts, provider boundary, and brain orchestration |
| `backend/app/evaluation` | Deterministic scenarios, simulation engine, metrics, baseline comparisons, and report serialization |
| `backend/app/services/intelligence.py` | Failure classification, probability, risk, expected value, and explainable action ranking |
| `backend/app/services/verification.py` | Signature verification, webhook idempotency, canonical payloads, and verified attribution |
| `backend/app/workflows/vertical_recovery.py` | Connected case lifecycle, bounded agent, policy gate, controlled tool, verification-pending state, and audit transitions |
| `backend/app/policy` | Safety and policy enforcement |
| `backend/app/resilience` | Failure classification, backoff, execution envelope, and resumability |
| `backend/app/tools` | Allow-listed dry-run controlled tools |
| `backend/app/models` and `backend/migrations` | Persistence models and schema migration |
| `backend/app/core` | Settings, database, logging, and request observability |
| `frontend/src` | Phase 9 visual command center and transaction trace experience |
| `docs` | Phase-specific implementation records and acceptance material |
| `submission` | Video script, failure story, architecture explanation, and panel preparation |

## Safety boundary

No real payment provider is configured. No LLM call occurs in tests. Controlled tools default to dry-run behavior. Duplicate idempotency keys, terminal states, successful transactions, retry budgets, unknown outcomes, invalid model outputs, timeouts, and provider failures are all explicit decision inputs rather than hidden exceptions. A webhook is not accepted without a configured HMAC secret, and recovery is not attributable without verified provider evidence matching the transaction, amount, currency, and attribution window. See [the data card](docs/DATA_CARD_AND_EVALUATION.md) and [gap-closure design](docs/PRODUCTION_GAP_CLOSURE.md).

The dry-run vertical slice is executable and tested: detected case → context-ready → awaiting decision → bounded agent output → deterministic policy → controlled tool intent → verification pending → audit trail. Provider credentials are intentionally required before any external side effect can be enabled.

## Project documentation

Begin with [ARCHITECTURE.md](ARCHITECTURE.md), then review [SAFETY_AND_POLICY.md](SAFETY_AND_POLICY.md), [FAILURE_HANDLING.md](FAILURE_HANDLING.md), and the phase records in [`docs/`](docs/). The submission materials are in [`submission/`](submission/).

## Development rules

Changes must preserve typed boundaries, integer minor-unit money values, deterministic tests, explicit failure outcomes, auditability, and the prohibition on unreviewed side effects. See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_DOCUMENTATION_STANDARD.md](CODE_DOCUMENTATION_STANDARD.md).
