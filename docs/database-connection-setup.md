# RevenueRescueAI — Database Connection & Migration Architecture

## 1. Executive Summary

In a financial platform, database reliability, transaction isolation, and connection pooling are non-negotiable. An incorrectly configured connection pool or missing foreign-key enforcement can lead to orphaned records, double charging, and database deadlocks.

RevenueRescueAI implements a **Dual-Dialect Persistence Strategy**:
1. **SQLite 3 (Development & Unit Testing):** Fast, zero-configuration local persistence allowing the entire test suite to execute in under 30 seconds without spinning up external containers.
2. **PostgreSQL 16 (Staging & Production):** Enterprise relational ACID database supporting row-level locking (`SELECT FOR UPDATE`), strict unique constraints, and high-concurrency connection pooling via `psycopg`.

---

## 2. SQLAlchemy Engine & Connection Pool Architecture

The database engine is configured in [`app/core/database.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/core/database.py).

```
[ FastAPI Route Handler ]
          │
          ▼ Depends(get_db)
[ SQLAlchemy Session (SessionLocal) ]
          │
          ▼ Executes Transaction
[ SQLAlchemy Engine (Connection Pool) ]
          │
          ├── pool_pre_ping = True (Detects dropped connections before queries)
          ├── pool_size = 5 (Persistent active connection limit)
          └── max_overflow = 10 (Temporary surge connection limit)
          │
          ▼ TCP Connection
[ Database Engine (PostgreSQL 16 / SQLite 3) ]
```

### Key Connection Pool Parameters Explained:
- **`pool_pre_ping=True` (Pessimistic Disconnect Handling):** Before handing a connection from the pool to a worker, SQLAlchemy sends a lightweight ping (`SELECT 1`). If the connection was terminated by an upstream firewall or gateway restart, the dead connection is transparently recycled rather than throwing a `ConnectionResetError` to the customer.
- **`pool_size=5`:** The number of persistent connections kept open inside the pool.
- **`max_overflow=10`:** The maximum number of extra connections created during sudden traffic spikes. When traffic subsides, these extra connections are closed cleanly.

---

## 3. SQLite Foreign Key Invariant Enforcement

By default, SQLite does not enforce relational foreign-key constraints unless explicitly commanded. In RevenueRescueAI, this is strictly prevented by registering an engine connection listener:

```python
if database_url().startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```
**Why this matters for beginners:** If table `recovery_attempts` references `recovery_cases(id)`, SQLite will reject inserting an attempt with a non-existent case ID, guaranteeing identical relational behavior between local development and production PostgreSQL.

---

## 4. Session Lifecycle & The `get_db` Pattern

In FastAPI, database sessions are injected into route handlers using the dependency injection pattern:

```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()  # Automatically rolls back on unhandled error
        raise
    finally:
        db.close()     # Always returns connection to the pool
```

### Safety Guarantees of this Pattern:
1. **Zero Connection Leaks:** The `finally` block guarantees that even if a function crashes or raises an exception, the connection is returned to the pool immediately.
2. **Automatic Rollback:** If an unhandled exception occurs inside a route handler, any uncommitted SQL statements are immediately rolled back, preventing corrupted partial states in the database.

---

## 5. Schema Migration Architecture (Alembic)

Schema evolution in RevenueRescueAI is managed using **Alembic**. Developers never run manual `CREATE TABLE` statements in production.

### Directory Layout:
- `alembic.ini`: Configuration file specifying migration directory and database URL.
- `backend/migrations/env.py`: Python runtime script that inspects SQLAlchemy `Base.metadata` and executes migrations within explicit transactions.
- `backend/migrations/versions/`: Chronologically ordered, immutable Python migration files.

### Common Migration Commands:
```powershell
# Apply all pending migrations to the database
alembic upgrade head

# Roll back the single most recent migration
alembic downgrade -1

# Generate a new migration script by comparing code models to database
alembic revision --autogenerate -m "add_table_name"

# View current database migration revision
alembic current
```

---

## 6. Real-Time Database Health Probing

To verify database connectivity without querying business data, the backend exposes the `check_database_connection()` probe via `GET /health/db`:

```powershell
curl http://localhost:8000/health/db
```
**Healthy Response (`200 OK`):**
```json
{
  "status": "healthy",
  "database": "connected",
  "dialect": "sqlite"
}
```
If the database drops or is unreachable, the endpoint returns `503 Service Unavailable`:
```json
{
  "status": "unhealthy",
  "database": "unavailable",
  "dialect": "postgresql"
}
```
This enables container orchestrators (Docker, Kubernetes) to monitor database readiness accurately.
