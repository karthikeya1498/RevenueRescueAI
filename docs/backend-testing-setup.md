# RevenueRescueAI — Backend Testing Foundation & Test Suite Architecture

## 1. Executive Summary

In financial software, tests are not merely an afterthought—they are the formal mathematical proof that safety invariants, retry limits, and accounting rules cannot be violated.

RevenueRescueAI features a comprehensive, fast, and completely deterministic automated test suite built on **Pytest + AnyIO + FastAPI TestClient**:
- **Zero External Dependencies:** Tests do not make network calls or require paid third-party sandbox accounts.
- **Isolated Persistence:** Tests run against in-memory or isolated test databases, ensuring zero state pollution across test runs.
- **High Speed:** The entire 61-test suite runs in under 30 seconds on a standard laptop.

---

## 2. Test Suite Organization

All tests reside under [`backend/tests/`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/):

| Test Module | Coverage Area & Invariants Verified | Test Count |
| :--- | :--- | :---: |
| [`test_app_startup.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_app_startup.py) | Application factory creates FastAPI instance and exposes standard routes. | 1 |
| [`test_health.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_health.py) | Verifies `/health` returns stable foundation liveness contract. | 1 |
| [`test_error_handling.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_error_handling.py) | Verifies RFC-7807 problem details, 422 validation parsing, and 500 stack trace redaction. | 4 |
| [`test_observability.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_observability.py) | Verifies request ID propagation and structured JSON access logs. | 3 |
| [`test_database_integrity.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_database_integrity.py) | Verifies SQLite foreign key pragma, unique idempotency constraints, and non-negative amount boundaries. | 4 |
| [`test_policy_resilience.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_policy_resilience.py) | Verifies retry budget limits (<= 2 retries), terminal state locks, and timeout backoff schedules. | 12 |
| [`test_recovery_intelligence.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_recovery_intelligence.py) | Verifies HMAC-SHA256 webhook verification, failure classification, and expected recovery value math. | 7 |
| [`test_resilient_executor.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_resilient_executor.py) | Verifies timeout wrappers, circuit breakers, and classification of transient vs. permanent API failures. | 5 |
| [`test_risk_detection.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_risk_detection.py) | Verifies revenue-at-risk scoring bands, stale pending payment detection, and batch input order preservation. | 7 |
| [`test_vertical_workflow.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_vertical_workflow.py) | Verifies the end-to-end 14-state workflow connecting AI recommendation, Policy Gate, and Audit ledger. | 2 |
| [`test_evaluation_engine.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_evaluation_engine.py) | Verifies 500-scenario deterministic generation (Seed 42) and zero-safe recovery rate metrics. | 5 |
| [`test_phase2_models.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_phase2_models.py) | Verifies relational persistence of cases, attempts, and external transaction identities. | 3 |
| [`test_realtime.py`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/tests/test_realtime.py) | Verifies WebSocket live stream handshake and heartbeat protocols. | 1 |
| **Total Test Count** | **Comprehensive Regression & Foundation Suite** | **61** |

---

## 3. Running Tests from the Command Line

### 3.1 Run All Tests:
```powershell
# Navigate to backend directory
cd backend

# Execute pytest
pytest -v
```

### 3.2 Run with Concise Output (Dots):
```powershell
pytest -q
```

### 3.3 Run a Single Test Module:
```powershell
pytest tests/test_error_handling.py -v
```

### 3.4 Run a Single Test Function:
```powershell
pytest tests/test_error_handling.py::test_unhandled_crash_does_not_leak_stack_trace -v
```

---

## 4. Test Isolation and Fixtures

1. **In-Memory / Isolated SQLite Databases:** Tests use SQLAlchemy session fixtures that initialize database tables in temporary schemas or in-memory tables. No changes made during testing persist to `revenuerescue.db`.
2. **Deterministic Seed (Seed 42):** Random number generators in simulator evaluations are seeded with constant integer `42`, guaranteeing 100% reproducible test outputs across different machines.
3. **No Network Side Effects:** Outbound HTTP clients (such as OpenAI or Razorpay adapters) are patched using FastAPI `TestClient` or unittest mocks, ensuring tests pass even without internet access.
