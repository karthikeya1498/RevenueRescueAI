# ADR-009: Testing Strategy — Deterministic Pytest & Cypress E2E

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** QA Architect, Senior Full-Stack Engineer  

---

## 1. Context
Financial recovery systems cannot tolerate regressions in safety invariants, idempotency checks, or monetary math. Test suites must run fast, execute deterministically, and provide 100% confidence across all layers.

## 2. Problem
What testing strategy and tooling should be adopted to ensure rigorous test coverage without introducing slow, flaky tests?

## 3. Options Considered
1. **Manual Testing Only:** Testing via browser and Postman manually.
2. **Heavy Containerized Test Suites (Testcontainers):** Spinning up real Docker containers for every test run.
3. **Multi-Tier Automated Testing:** Fast in-memory unit/integration tests (Pytest + SQLite) combined with end-to-end browser tests (Cypress).

## 4. Decision
We choose **Multi-Tier Automated Testing**:
1. **Backend Unit & Integration:** `pytest` + `pytest-asyncio` + `anyio` with isolated in-memory SQLite fixtures (currently 57 tests passing in <8 seconds).
2. **Frontend End-to-End:** `Cypress` for critical user journeys (command center navigation, queue filtering, trace inspection).
3. **500-Scenario Batch Evaluation:** Headless CLI evaluation testing recovery rates, safety rates, and action accuracy against Seed 42.

## 5. Reasons
- **Fast Feedback Loop:** Sub-10-second backend test execution encourages developers to run tests continuously during local coding.
- **Coverage of Invariants:** Invariants INV-001 through INV-016 are validated by dedicated test cases (e.g., `test_terminal_case_stops_any_action`, `test_retry_limit_escalates_instead_of_retrying`).
- **Reproducible E2E Verification:** Cypress verifies that real browser DOM elements (cards, tables, buttons) render and interact properly without manual clicking.

## 6. Trade-offs & Consequences
- **Positive:** High test confidence, zero flaky network dependencies, automated CI readiness.
- **Negative:** Requires maintaining test fixtures and deterministic seeds across updates.

## 7. Reconsideration Conditions
Re-evaluate if performance testing under 50,000 concurrent webhooks requires distributed load generators (e.g., Locust or k6).
