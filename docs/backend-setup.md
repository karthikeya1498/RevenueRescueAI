# RevenueRescueAI — Backend Development Setup Guide

## 1. Executive Summary

This document specifies the exact, step-by-step procedure for preparing, configuring, and verifying the **RevenueRescueAI** backend development environment. It is designed to enable any software engineer or student developer to establish a fully functional local development workstation with zero guesswork.

---

## 2. Prerequisites & Machine Compatibility

Before setting up the project, ensure the following core tools are installed on your workstation:

| Tool | Minimum Version | Verified Local Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11.0+ | **3.14.4** | Core programming runtime. |
| **pip** | 23.0+ | **24.0+** | Python package manager. |
| **Git** | 2.30+ | **2.54.0** | Version control system. |
| **Docker** | 24.0+ | **29.6.1** | Containerization for PostgreSQL. |
| **OS** | Windows 10/11 or Linux/macOS | Windows 11 (PowerShell 5.1/7+) | Host operating system. |

---

## 3. Step-by-Step Local Setup Instructions

### Step 3.1: Navigate to the Project Root
Open Windows PowerShell (or terminal) and switch to the project directory:
```powershell
cd c:\Users\vanka\Downloads\RevenueRescueAI-main\RevenueRescueAI-main
```

### Step 3.2: Create and Activate a Dedicated Virtual Environment
A virtual environment isolates project dependencies, preventing version conflicts with other Python projects on your machine.
```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```
*Tip: If PowerShell displays a script execution policy error (`Execution_Policies`), run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and re-run the activation script.*

### Step 3.3: Install Backend Dependencies
Upgrade package tooling and install the pinned dependencies:
```powershell
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

## 4. Environment File Configuration

RevenueRescueAI uses **Pydantic Settings** to automatically read environment variables from `.env` files with strong type checking.

Create your local `.env` file from the provided example template:
```powershell
# Windows PowerShell
Copy-Item backend\.env.example backend\.env
Copy-Item backend\.env.example .env

# Linux / macOS
cp backend/.env.example backend/.env
cp backend/.env.example .env
```

### Critical Environment Settings for Local Development:
```env
APP_NAME=RevenueRescue AI
APP_PHASE=foundation
ENVIRONMENT=development
LOG_LEVEL=INFO

SERVER_HOST=0.0.0.0
SERVER_PORT=8000
FRONTEND_ORIGIN=http://localhost:5173

# Local SQLite connection (default for instant development without Docker)
DATABASE_URL=sqlite:///./revenuerescue.db
```

---

## 5. Database Initialization

RevenueRescueAI supports two database engines out of the box:

### Option A: Local SQLite (Instant Setup - Recommended for Beginners)
No additional services are required. The SQLite database engine initializes automatically when the application starts, creating the local file `revenuerescue.db`.
- Foreign key constraints are automatically enabled on connection:
  ```python
  PRAGMA foreign_keys=ON;
  ```

### Option B: Local PostgreSQL via Docker Compose
For testing with production-grade PostgreSQL 16:
```powershell
# Start PostgreSQL container in background
docker compose up -d postgres

# Verify container health
docker compose ps
```
Update your `.env` file to use the PostgreSQL URL:
```env
DATABASE_URL=postgresql+psycopg://revenuerescue:revenuerescue@localhost:5432/revenuerescue
```

### Applying Schema Migrations:
```powershell
# Apply Alembic schema migrations
alembic upgrade head
```

---

## 6. Running the Development Server

Start the Uvicorn ASGI server with live auto-reload enabled:

```powershell
# Run from repository root
uvicorn app.main:app --app-dir backend --reload --port 8000
```

### Verifying Service Startup:
Open your web browser and navigate to:
- **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 7. Verification Checklist

Execute these three verification commands in a new terminal to confirm your setup:

```powershell
# 1. Check Service Liveness
curl http://localhost:8000/health

# 2. Check Database Connectivity Probe
curl http://localhost:8000/health/db

# 3. Run Automated Tests
cd backend
pytest -q
```
Expected test output: `61 passed in ~25s`.
