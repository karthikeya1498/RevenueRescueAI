# RevenueRescueAI — Environment Configuration Specification

## 1. Executive Summary & Design Principles

Application configuration controls how software behaves across different runtime environments (local development, automated CI testing, and production deployment) without modifying source code.

RevenueRescueAI adheres to the **Twelve-Factor App Configuration Methodology**:
1. **Strict Separation of Config from Code:** Configuration varies substantially across deploys, code does not.
2. **Type Safety & Early Validation:** Configuration is loaded through **Pydantic Settings** (`BaseSettings`). If an environment variable is invalid (e.g., `PORT=abc`), the server halts immediately at startup with an unambiguous validation error rather than failing mysteriously at runtime.
3. **Zero Secrets in Version Control:** Production passwords, encryption keys, and webhook secrets must never be committed to Git.

---

## 2. Configuration Loading Hierarchy

Configuration values are resolved using the following order of precedence (highest priority wins):
1. **Operating System Environment Variables** (e.g., `export DATABASE_URL=...` or Docker environment overrides)
2. **Local Environment File (`.env.local`)** (developer machine-specific overrides)
3. **Default Environment File (`.env`)** (standard local development defaults)
4. **Hardcoded Defaults in `Settings` class** (safe fallbacks for local test runs)

---

## 3. Environment Variable Catalogue

| Environment Variable | Data Type | Default Value | Supported Values | Functional Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `APP_NAME` | `str` | `RevenueRescue AI` | Any string | Branding title for Swagger docs and logs. |
| `APP_PHASE` | `str` | `foundation` | `foundation`, `production-polish` | Architectural milestone identifier. |
| `ENVIRONMENT` | `str` | `development` | `development`, `test`, `production` | Active application execution profile. |
| `LOG_LEVEL` | `str` | `INFO` | `DEBUG`, `INFO`, `WARN`, `ERROR` | Minimum severity threshold for logging output. |
| `SERVER_HOST` | `str` | `0.0.0.0` | IP Address | Network interface bound by ASGI server. |
| `SERVER_PORT` | `int` | `8000` | 1–65535 | HTTP/WebSocket listening port. |
| `FRONTEND_ORIGIN` | `str` | `http://localhost:5173` | Valid URL | Single origin allowed for CORS requests. |
| `CORS_ORIGINS` | `list[str]` | `["http://localhost:5173"]` | JSON list of URLs | Full list of trusted web origins allowed for cross-origin API calls. |
| `DATABASE_URL` | `str` | `sqlite:///./revenuerescue.db` | SQLite / PostgreSQL URI | Connection string for relational database. |
| `DB_POOL_SIZE` | `int` | `5` | Positive integer | Active persistent connection pool size (Postgres). |
| `DB_MAX_OVERFLOW` | `int` | `10` | Non-negative integer | Burst connections permitted beyond pool size. |
| `DB_ECHO` | `bool` | `false` | `true`, `false` | When true, logs raw SQL statements (dev only). |
| `LLM_PROVIDER` | `str` | `None` | `openai`, `simulator` | External AI provider adapter selector. |
| `LLM_API_KEY` | `str` | `None` | Secret string | API key for LLM provider (optional in dev). |
| `PAYMENT_PROVIDER` | `str` | `None` | `razorpay`, `stripe`, `simulator` | External payment gateway adapter selector. |
| `RAZORPAY_WEBHOOK_SECRET` | `str` | `""` | Secret string | HMAC-SHA256 signature verification secret. |

---

## 4. Environment Profiles

### 4.1 Development Profile (`ENVIRONMENT=development`)
- Uses local SQLite database (`revenuerescue.db`) or local Docker PostgreSQL.
- Server runs with auto-reload enabled (`uvicorn --reload`).
- Interactive OpenAPI documentation enabled at `/docs`.
- Verbose logging and detailed error formatting.

### 4.2 Test Profile (`ENVIRONMENT=test`)
- Automatically activated during `pytest` runs.
- Uses isolated in-memory SQLite database (`sqlite:///:memory:`) or dedicated test file session.
- External payment providers are mocked or replaced with deterministic seeded simulation models (Seed 42).
- Zero side effects executed against external networks.

### 4.3 Production Profile (`ENVIRONMENT=production`)
- Requires PostgreSQL connection (`postgresql+psycopg://...`).
- CORS strictly restricted to merchant domain.
- `docs_url` and `redoc_url` can be restricted behind VPN or admin authentication.
- Secrets loaded exclusively from secure container environments or secret managers (AWS Secrets Manager, HashiCorp Vault).

---

## 5. Security & Secret Redaction Controls

1. **`.env` is Git-Ignored:** Both root `.gitignore` and `backend/.gitignore` include `.env` and `*.env`.
2. **Safe Dictionary Serialization:** The `Settings.safe_dict()` method strips all sensitive credentials:
   ```python
   # Returns dialect name ("postgresql" or "sqlite") instead of full connection string with passwords
   "database_dialect": "postgresql"
   ```
3. **Health Check Masking:** The `/ready` and `/health` endpoints never expose environment variables or connection strings.
