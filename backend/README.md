# RevenueRescue AI — Backend Development Guide

## 1. Project Overview

The **RevenueRescue AI** backend is a high-reliability, asynchronous financial service engineered in **Python 3.11+ / FastAPI / SQLAlchemy 2.0**. 

Its core responsibility is to safeguard merchants from involuntary customer churn through **Autonomous, Bounded, and Verified Revenue Recovery**:
- Ingesting raw payment failure notifications from payment gateways (Stripe, Razorpay, Simulator).
- Performing root-cause failure classification and AI advisory recovery recommendations.
- Enforcing non-negotiable financial safety rules through a Deterministic Policy Gate.
- Executing bounded recovery actions with strict UUIDv5 idempotency.
- Authoritatively verifying banking ledger settlements before declaring revenue recovered.
- Preserving an immutable, append-only relational audit ledger.

---

## 2. Prerequisites & Environment Compatibility

| Tool | Required Version | Verification Command |
| :--- | :--- | :--- |
| **Python** | 3.11 or higher (tested with 3.12 / 3.14) | `python --version` |
| **pip** | 23.0+ | `pip --version` |
| **Git** | 2.30+ | `git --version` |
| **Docker & Compose** | Docker 24+ / Compose v2 (optional for Postgres) | `docker --version` |

---

## 3. Installation & Local Setup

### Step 1: Clone or Navigate to the Backend
```powershell
# Windows PowerShell
cd c:\Users\vanka\Downloads\RevenueRescueAI-main\RevenueRescueAI-main\backend
```

### Step 2: Create and Activate a Virtual Environment
```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Required Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Configuration & Environment Variables

The application loads configuration via **Pydantic Settings** from `.env` in the current working directory.

### Quick Setup:
```powershell
# Windows PowerShell
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

### Key Environment Variables Explained:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `APP_NAME` | `RevenueRescue AI` | Application branding identifier. |
| `ENVIRONMENT` | `development` | Active profile: `development`, `test`, or `production`. |
| `LOG_LEVEL` | `INFO` | Logging threshold (`DEBUG`, `INFO`, `WARN`, `ERROR`). |
| `SERVER_HOST` | `0.0.0.0` | Network interface to bind HTTP server. |
| `SERVER_PORT` | `8000` | HTTP port for REST and WebSocket traffic. |
| `DATABASE_URL` | `sqlite:///./revenuerescue.db` | Connection URI. Supports SQLite locally and PostgreSQL in production. |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Trusted frontend origin for CORS policies. |
| `DB_POOL_SIZE` | `5` | Active database connection pool size (Postgres). |
| `DB_MAX_OVERFLOW` | `10` | Maximum surge connections permitted beyond pool size. |

> **Security Invariant:** Never put real API keys, card numbers, or passwords into `.env` or commit `.env` to Git.

---

## 5. Database Setup & Migrations

RevenueRescue AI supports a **dual-dialect persistence architecture**:
1. **SQLite (`sqlite:///./revenuerescue.db`):** Zero setup required for fast local development and unit tests. Foreign-key constraints are automatically enforced via `PRAGMA foreign_keys=ON`.
2. **PostgreSQL (`postgresql+psycopg://...`):** Full relational ACID persistence for staging and production.

### Starting Local PostgreSQL via Docker Compose:
```powershell
# From the backend directory
docker compose up -d postgres
```

### Running Database Migrations (Alembic):
```powershell
# Apply all pending schema migrations
alembic upgrade head

# Inspect current revision status
alembic current
```

---

## 6. Running the Application

### Development Mode (with Live Reload):
From the repository root:
```powershell
uvicorn app.main:app --app-dir backend --reload --port 8000
```
Or directly from the `backend/` directory:
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running:
- **Interactive OpenAPI Documentation (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 7. Health & Diagnostic Probes

The backend provides three distinct operational verification endpoints:

### 1. Service Liveness Check (`GET /health`)
```powershell
curl http://localhost:8000/health
```
**Expected Response:**
```json
{
  "status": "healthy",
  "service": "RevenueRescue AI",
  "phase": "foundation"
}
```

### 2. Dependency Readiness Check (`GET /ready`)
```powershell
curl http://localhost:8000/ready
```
**Expected Response:**
```json
{
  "status": "ready",
  "service": "RevenueRescue AI",
  "phase": "foundation",
  "environment": "development",
  "dependencies": {
    "configuration": "ready",
    "database": "deferred",
    "providers": "not_configured"
  }
}
```

### 3. Active Database Connectivity Probe (`GET /health/db`)
```powershell
curl http://localhost:8000/health/db
```
**Expected Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "dialect": "sqlite"
}
```

---

## 8. Running the Automated Test Suite

All tests run locally in under 30 seconds without external dependencies:

```powershell
# Run the complete test suite
pytest -v

# Run with concise output
pytest -q

# Run a specific test module
pytest tests/test_error_handling.py -v
pytest tests/test_health.py -v
```

---

## 9. Containerization & Docker Build

### Building the Production Container Image:
```powershell
# Build from the backend directory
docker build -t revenuerescue-backend:latest .
```

### Running the Complete Stack (Backend + Postgres):
```powershell
docker compose up -d
```

### Stopping and Cleaning Containers:
```powershell
# Stop services
docker compose down

# Stop and remove persistent database volumes (WARNING: wipes local DB data)
docker compose down -v
```

---

## 10. Troubleshooting & Common Solutions

### Problem 1: `ModuleNotFoundError: No module named 'app'`
- **Cause:** Running uvicorn without the proper app directory on the Python path.
- **Fix (Windows PowerShell):**
  ```powershell
  $env:PYTHONPATH = "c:\Users\vanka\Downloads\RevenueRescueAI-main\RevenueRescueAI-main\backend"
  uvicorn app.main:app --reload
  ```
  Or run from repository root using `--app-dir backend`:
  ```powershell
  uvicorn app.main:app --app-dir backend --reload
  ```

### Problem 2: `sqlite3.OperationalError: database is locked`
- **Cause:** Multiple concurrent test threads or processes accessing SQLite file.
- **Fix:** SQLite in unit tests uses thread-safe memory or isolated file sessions. Ensure no zombie uvicorn process is holding a lock on `revenuerescue.db`.

### Problem 3: `psycopg.OperationalError: connection to server at "localhost", port 5432 failed`
- **Cause:** PostgreSQL container is not running or port 5432 is blocked.
- **Fix:**
  ```powershell
  docker compose ps
  docker compose up -d postgres
  ```
  Verify container health: `docker inspect --format='{{json .State.Health}}' revenuerescue-backend-postgres-1`.

### Problem 4: `DeprecationWarning: HTTP_422_UNPROCESSABLE_ENTITY`
- **Cause:** Starlette / FastAPI updated status code name to `HTTP_422_UNPROCESSABLE_CONTENT`.
- **Fix:** Already resolved in `app.core.errors` via dynamic fallback `HTTP_422_STATUS`.
