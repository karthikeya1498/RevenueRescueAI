# RevenueRescueAI — Non-Functional Quality Requirements

> **Document ID:** DOC-NFR-007  
> **Phase:** 0.2 (User Stories, Functional Requirements & Acceptance Criteria)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

Non-Functional Requirements (NFRs) define the operational quality attributes, safety guarantees, security boundaries, and architectural constraints under which RevenueRescueAI must operate. In financial technology, NFRs are as critical as functional features: a system that correctly recovers money but leaks credit card numbers into logs or exhibits non-deterministic race conditions fails enterprise deployment standards.

This document establishes measurable, verifiable non-functional requirements across thirteen architectural dimensions. Each requirement includes a unique identifier (`NFR-001` to `NFR-020`), a business rationale, priority, acceptance criteria, and specific verification methods.

---

## 2. Non-Functional Requirements Index

| Requirement ID | Quality Dimension | Requirement Title | Priority |
|---|---|---|:---:|
| **NFR-001** | Reliability | Webhook Perimeter High Availability & Fault Tolerance | **MUST** |
| **NFR-002** | Reliability | Crash Recovery & Workflow State Resumability | **MUST** |
| **NFR-003** | Data Consistency | Zero Floating-Point Financial Currency Invariant | **MUST** |
| **NFR-004** | Data Consistency | Atomic State Transitions & Outbox Pattern | **MUST** |
| **NFR-005** | Idempotency | End-to-End Replay & Duplicate Invariant | **MUST** |
| **NFR-006** | Security | Cryptographic Webhook Authentication (HMAC-SHA256) | **MUST** |
| **NFR-007** | Security | Zero Hardcoded Secrets & Environment Injection | **MUST** |
| **NFR-008** | Security | Least-Privilege Database Access Isolation | **MUST** |
| **NFR-009** | Privacy | PII & PCI Masking in Application Logs | **MUST** |
| **NFR-010** | Privacy | Synthetic Fixture Invariant (Zero Real Customer Data) | **MUST** |
| **NFR-011** | Performance | Webhook Ingestion Acknowledgment Latency (< 500ms) | **MUST** |
| **NFR-012** | Performance | Rapid Local Unit Test Suite Execution (< 10 Seconds) | **MUST** |
| **NFR-013** | Maintainability | Strict Modular Monolith Architecture & Type Hints | **MUST** |
| **NFR-014** | Maintainability | Automated Linting & Code Quality Gates | **MUST** |
| **NFR-015** | Observability | Structured JSON Logging with Trace Correlation IDs | **MUST** |
| **NFR-016** | Observability | Standardized Health & Readiness Probes (`/health`, `/ready`)| **MUST** |
| **NFR-017** | Testability | Deterministic Test Suite (Zero External Network Calls)| **MUST** |
| **NFR-018** | Reproducibility | Fixed-Seed Simulation Reproducibility (Seed 42) | **MUST** |
| **NFR-019** | Accessibility | WCAG 2.1 AA Compliance & Tabular Numerals | **MUST** |
| **NFR-020** | Deployment | Multi-Platform Docker Compose & Python Setup | **MUST** |

---

## 3. Detailed Non-Functional Requirement Specifications

---

### Reliability & Resilience

#### NFR-001: Webhook Perimeter Fault Tolerance
- **Description:** The webhook ingestion service shall maintain 99.9% availability during local operations and handle sudden traffic spikes (up to 100 requests/second) without dropping transactions.
- **Rationale:** Dropped webhooks mean unrecorded payment failures and permanent revenue leakage.
- **Priority:** **MUST**
- **Acceptance Criterion:** Under a burst load of 100 concurrent webhook requests, 100% of requests receive a valid HTTP status code within 500ms; zero socket drops.
- **Dependencies:** FastAPI ASGI server, connection pooling.
- **Verification Method:** Load testing script using `locust` or `pytest-benchmark`.

---

#### NFR-002: Crash Recovery & Workflow State Resumability
- **Description:** The system shall persist case state atomically at every transition so that in the event of a sudden process crash or server reboot, in-flight cases can be resumed without data corruption or duplicate actions.
- **Rationale:** Distributed systems fail; crash resilience guarantees zero lost recovery workflows.
- **Priority:** **MUST**
- **Acceptance Criterion:** When the application process is terminated via `SIGKILL` mid-workflow, restarting the application detects unfinished cases in `ACTION_EXECUTING` and safely triggers status reconciliation without duplicating the charge.
- **Dependencies:** Relational database transaction management.
- **Verification Method:** Chaos test terminating server process mid-action and asserting state recovery on restart.

---

### Data Consistency & Idempotency

#### NFR-003: Zero Floating-Point Financial Currency Invariant
- **Description:** All monetary values in database columns, schemas, memory objects, and calculations must be strictly represented as 64-bit signed integers in currency minor units (cents/paise).
- **Rationale:** Binary floating-point arithmetic causes rounding errors (e.g., `$0.10 + $0.20 = $0.30000000000000004`), which violates accounting audits.
- **Priority:** **MUST (Non-negotiable architectural invariant)**
- **Acceptance Criterion:** Database column type inspection verifies 100% of currency columns are `BigInteger`; static analysis verifies zero `float()` casts in financial math.
- **Dependencies:** SQLAlchemy model schema definitions.
- **Verification Method:** Automated database schema reflection test.

---

#### NFR-004: Atomic State Transitions & Outbox Pattern
- **Description:** Every state transition and its corresponding audit log entry must be written within a single atomic database transaction (`COMMIT` or `ROLLBACK`).
- **Rationale:** Prevents "split-brain" states where a case changes state but no audit trail is recorded.
- **Priority:** **MUST**
- **Acceptance Criterion:** If an audit record insertion fails, the case state update is rolled back 100% of the time.
- **Dependencies:** Relational database ACID transactions.
- **Verification Method:** Failure injection test throwing an error during audit write and asserting case state rollback.

---

#### NFR-005: End-to-End Replay & Duplicate Invariant
- **Description:** Replaying the identical webhook payload or re-executing an existing action must result in zero duplicate database cases and zero secondary payment gateway debits.
- **Rationale:** At-least-once message delivery in cloud architectures routinely delivers duplicate messages.
- **Priority:** **MUST**
- **Acceptance Criterion:** The Duplicate Action Rate across all evaluation runs and test suites must be exactly 0.00%.
- **Dependencies:** Unique database indexes on `event_id` and `idempotency_key`.
- **Verification Method:** Automated integration test replaying identical webhooks and actions 10 times consecutively.

---

### Security & Privacy

#### NFR-006: Cryptographic Webhook Authentication (HMAC-SHA256)
- **Description:** All incoming webhook HTTP requests must be authenticated using HMAC-SHA256 signatures with constant-time comparison.
- **Rationale:** Prevents unauthorized attackers from forging payment failure webhooks or manipulating recovery states.
- **Priority:** **MUST**
- **Acceptance Criterion:** 100% of requests with missing, forged, or expired signatures are rejected with HTTP 401 Unauthorized; zero unauthenticated payloads reach the database.
- **Dependencies:** Python `hmac` and `hashlib` libraries.
- **Verification Method:** Security test suite firing forged signatures.

---

#### NFR-007: Zero Hardcoded Secrets & Environment Injection
- **Description:** No credentials, API keys, webhook secrets, or private keys shall be committed to source control or embedded in application code.
- **Rationale:** Protects against credential theft and repository security breaches.
- **Priority:** **MUST**
- **Acceptance Criterion:** Automated secret scanner (`trufflehog` or `git-secrets`) returns 0 high-entropy secret matches across repository git history. All secrets loaded via environment variables (`.env`).
- **Dependencies:** Pydantic `BaseSettings`.
- **Verification Method:** Automated pre-commit git secret scan.

---

#### NFR-008: Least-Privilege Database Access Isolation
- **Description:** Application database connections must use a dedicated database user with permissions restricted to application schemas, with explicit prohibition on modifying audit tables (`INSERT`, `SELECT` only).
- **Rationale:** Defense-in-depth: prevents SQL injection from altering historical audit records or dropping database tables.
- **Priority:** **MUST**
- **Acceptance Criterion:** Attempting to execute an `UPDATE` or `DELETE` query on the `audit_events` table using the application connection throws a SQL permission denied error.
- **Dependencies:** PostgreSQL / SQLite permission configuration.
- **Verification Method:** SQL permission assertion test.

---

#### NFR-009: PII & PCI Masking in Application Logs
- **Description:** Application logging filters shall automatically mask card numbers (PAN), CVVs, and sensitive customer identifiers before emitting structured JSON logs.
- **Rationale:** Strict compliance with PCI-DSS Requirement 3 and privacy protection laws (GDPR/CCPA).
- **Priority:** **MUST**
- **Acceptance Criterion:** Regex scan across 10,000 generated test log lines reveals zero 16-digit credit card patterns; card numbers appear strictly as `****-****-****-1234`.
- **Dependencies:** Python logging filter pipeline.
- **Verification Method:** Log pattern regex scanner in CI pipeline.

---

#### NFR-010: Synthetic Fixture Invariant (Zero Real Customer Data)
- **Description:** The local development, testing, and evaluation environments must operate exclusively on deterministically generated synthetic customer and transaction fixtures.
- **Rationale:** Eliminates compliance liability and privacy risks for developers and evaluators.
- **Priority:** **MUST**
- **Acceptance Criterion:** All customer names, emails, card numbers, and bank tokens are explicitly generated from mock seed algorithms.
- **Dependencies:** Synthetic scenario generator.
- **Verification Method:** Automated check verifying zero production database dumps in repository.

---

### Performance & Efficiency

#### NFR-011: Webhook Ingestion Acknowledgment Latency (< 500ms)
- **Description:** The webhook perimeter endpoint must process cryptographic verification, schema validation, and database ingestion within 500 milliseconds (P95) under standard local execution.
- **Rationale:** External payment providers (Stripe, Razorpay) enforce strict 2–5 second timeout windows before declaring webhook delivery failure and scheduling retries.
- **Priority:** **MUST**
- **Acceptance Criterion:** 95% of synthetic webhook requests receive HTTP 200 acknowledgment in under 500ms on standard developer hardware.
- **Dependencies:** Async FastAPI request handlers.
- **Verification Method:** Automated latency benchmark test over 200 requests.

---

#### NFR-012: Rapid Local Unit Test Suite Execution (< 10 Seconds)
- **Description:** The entire core automated unit and policy test suite must execute in under 10 seconds locally.
- **Rationale:** Fast test suites encourage continuous test-driven development (TDD) for beginner developers without context-switching delays.
- **Priority:** **MUST**
- **Acceptance Criterion:** Running `pytest backend/tests/unit` completes in < 10.0 seconds.
- **Dependencies:** In-memory SQLite / mock adapters.
- **Verification Method:** Timed pytest execution command.

---

### Maintainability & Architecture

#### NFR-013: Strict Modular Monolith Architecture & Type Hints
- **Description:** The codebase shall be organized as a clean modular monolith with strict domain boundaries (`ingestion`, `intelligence`, `policy`, `workflow`, `tools`, `verification`, `audit`), with 100% type annotations across public function signatures.
- **Rationale:** Ensures clean code readability for beginner developers without the operational overhead of microservices.
- **Priority:** **MUST**
- **Acceptance Criterion:** Running `mypy` in strict mode passes with 0 type errors across backend packages.
- **Dependencies:** Python 3.11+, MyPy.
- **Verification Method:** Static type checking execution.

---

#### NFR-014: Automated Linting & Code Quality Gates
- **Description:** All code must conform to PEP-8 standards and pass automated linting checks using `ruff` without warnings or syntax errors.
- **Rationale:** Enforces uniform code readability and prevents code quality regressions.
- **Priority:** **MUST**
- **Acceptance Criterion:** `ruff check backend/` returns 0 errors.
- **Dependencies:** Ruff linter.
- **Verification Method:** Automated linting script execution.

---

### Observability & Traceability

#### NFR-015: Structured JSON Logging with Trace Correlation IDs
- **Description:** Every log message emitted by the backend must be formatted as structured JSON containing ISO-8601 `timestamp`, `log_level`, `request_id`, `case_id` (if applicable), and `component_name`.
- **Rationale:** Enables centralized log aggregation, instant correlation of distributed events, and rapid debugging.
- **Priority:** **MUST**
- **Acceptance Criterion:** Log line schema matches standard JSON format; correlation IDs propagate across ingestion to verification.
- **Dependencies:** Python `structlog` or standard JSON logging formatter.
- **Verification Method:** Log schema parsing assertion test.

---

#### NFR-016: Standardized Health & Readiness Probes (`/health`, `/ready`)
- **Description:** The application shall expose `GET /health` (liveness probe) and `GET /ready` (readiness probe verifying database connectivity and configuration validity).
- **Rationale:** Standard cloud-native observability pattern for container orchestration and deployment verification.
- **Priority:** **MUST**
- **Acceptance Criterion:** `GET /health` returns HTTP 200 `{ "status": "healthy" }`; `GET /ready` returns HTTP 200 if database connects, or HTTP 503 if database is disconnected.
- **Dependencies:** FastAPI router.
- **Verification Method:** Integration test testing health endpoints under connected and disconnected database states.

---

### Testability & Reproducibility

#### NFR-017: Deterministic Test Suite (Zero External Network Calls)
- **Description:** The automated test suite must run 100% offline without requiring outbound internet connectivity or paid external API services.
- **Rationale:** Guarantees that CI/CD pipelines and local developer workstations can test the entire system reliably without external failure points.
- **Priority:** **MUST**
- **Acceptance Criterion:** Running the test suite with network interfaces disabled completes with 100% passing tests.
- **Dependencies:** Mock adapters and local payment provider simulator.
- **Verification Method:** Test execution in isolated offline network sandbox.

---

#### NFR-018: Fixed-Seed Simulation Reproducibility (Seed 42)
- **Description:** Running the batch evaluation harness on 500 scenarios with seed `42` must produce identical numerical outputs, recovery rates, and SHA-256 report checksums across repeated runs.
- **Rationale:** Core scientific evaluation requirement: ensures benchmark claims are mathematically reproducible by third parties.
- **Priority:** **MUST**
- **Acceptance Criterion:** Executing the evaluation script twice with seed 42 produces identical JSON report artifacts with matching SHA-256 hashes.
- **Dependencies:** Deterministic random number generator (`random.seed(42)`).
- **Verification Method:** Script comparing SHA-256 hashes of consecutive evaluation runs.

---

### Usability, Accessibility & UI Quality

#### NFR-019: WCAG 2.1 AA Compliance & Tabular Numerals
- **Description:** The dashboard frontend shall adhere to WCAG 2.1 Level AA accessibility standards (minimum 4.5:1 text contrast ratio) and format all financial figures using monospace tabular numbers (`font-variant-numeric: tabular-nums`).
- **Rationale:** Guarantees readability for visually impaired operators and aligns financial decimal columns vertically for error-free scanning.
- **Priority:** **MUST**
- **Acceptance Criterion:** Automated accessibility audit (`axe-core` / Lighthouse accessibility) scores >= 90; financial tables use tabular numerals.
- **Dependencies:** CSS typography standards.
- **Verification Method:** Automated Lighthouse accessibility audit.

---

#### NFR-020: Multi-Platform Docker Compose & Python Setup
- **Description:** The application must build and run identically across Linux, macOS, and Windows 11 environments using standard Docker Compose and standard Python virtual environments (`.venv`).
- **Rationale:** Ensures frictionless onboarding for beginner developers regardless of operating system.
- **Priority:** **MUST**
- **Acceptance Criterion:** `docker compose up --build` spins up backend and frontend services successfully without platform-specific path or dependency errors.
- **Dependencies:** `docker-compose.yml`, multi-stage Dockerfiles.
- **Verification Method:** Cross-platform container execution check.
