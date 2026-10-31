# ADR-007: Workflow Execution Strategy — Deterministic Finite State Machine

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Principal Software Architect, Senior Backend Engineer  

---

## 1. Context
A recovery case transitions through multiple phases: detection, risk evaluation, diagnosis, recommendation, policy approval, execution, outcome verification, and audit logging. State transitions must be strictly bounded, irreversible once terminal, and resilient against race conditions.

## 2. Problem
How should workflow execution and case state management be orchestrated without adding complex external orchestration engines?

## 3. Options Considered
1. **Ad-Hoc Boolean Flags:** Using columns like `is_recovered`, `is_failed`, and `is_escalated` on a case table.
2. **External Workflow Orchestrator (Temporal / Airflow / AWS Step Functions):** Heavyweight workflow engines requiring dedicated worker clusters and external state databases.
3. **Deterministic Relational Finite State Machine (FSM):** A state machine enforced in domain Python code and backed by ACID relational transitions, optimistic versioning, and monotonic sequence numbers.

## 4. Decision
We choose a **Deterministic Relational Finite State Machine (FSM)** implemented in `backend/app/workflows/vertical_recovery.py`.

## 5. Reasons
- **Explicit Valid State Transitions:** A strict transition matrix ensures that illegal transitions (e.g., `RECOVERED -> DETECTED` or reversing a `TERMINATED` case) are rejected with typed domain errors.
- **Terminal State Immutability (INV-004):** Once a case reaches a terminal state (`RECOVERED`, `FAILED`, `TERMINATED`), no automated process or API call can reopen it.
- **Zero Heavy Infrastructure:** Temporal and Airflow require separate daemons, Redis/Zookeeper, and complex deployment pipelines. The in-process FSM runs within existing FastAPI database sessions with zero operational overhead.
- **Audit Traceability:** Every state change automatically generates a record in `case_state_transitions` with monotonic sequence numbers.

## 6. Trade-offs & Consequences
- **Positive:** Atomic state changes, simple to understand and test, complete isolation.
- **Negative:** Long-sleeping distributed workflows (e.g., waiting 3 weeks for manual legal review) are handled via scheduled polling or status queries rather than persistent engine sleep timers.

## 7. Reconsideration Conditions
Re-evaluate external workflow orchestrators if recovery lifecycles span months with thousands of human-in-the-loop task routing steps.
