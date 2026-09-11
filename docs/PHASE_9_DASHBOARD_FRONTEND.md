# Phase 9: Dashboard & Frontend

**Project:** RevenueRescue AI  
**Author:** Karthikeya  
**Status:** Implemented against the Phase 8 synthetic evaluation baseline

## Purpose

Phase 9 turns the evaluation and agent-control layers into a visual command center. The dashboard is designed for operational review rather than autonomous execution. It surfaces evaluation health, recovery opportunity, policy outcomes, and transaction-level traces in one workspace.

## Command center

The overview page presents the 500-scenario baseline with recovered revenue, at-risk revenue, safety rate, attention volume, a recovery trend visualization, outcome donut, and recent agent traces. The displayed values are sourced from the inspected Phase 8 report generated with seed `42` and rule version `phase8.v1`.

## Recovery queue

The queue view presents synthetic cases that require attention, including at-risk revenue, awaiting-decision count, verification-pending count, and escalation count. Filtering is available for representative case states. Selecting a row opens the transaction trace drawer.

## Agent traces

The trace view exposes a transaction-level journey with these stages: risk detected, context gathered, agent decision, policy check, and tool execution or verification. Each trace includes the transaction identity, amount, risk reason, state, action, confidence, timestamp, and a structured decision summary. The drawer intentionally presents the action as an observable decision; it does not execute a recovery action.

## Evaluation Lab

The Evaluation Lab visualizes the 500-scenario batch metrics, outcome distribution, quality controls, and representative transactions. It distinguishes revenue recovery from action accuracy and safety, preventing a favorable recovery number from hiding unsafe or poor-quality decisions.

## Frontend verification

The local Vite application was inspected in a browser. The command center, Agent Traces page, trace detail drawer, and Evaluation Lab all rendered successfully. Responsive navigation and the trace drawer were implemented for smaller screens. The production TypeScript/Vite build passed.

## Scope boundary

This increment uses an inspected synthetic report snapshot for the frontend. It does not connect the browser directly to a production database, expose credentials, enable live payment execution, or provide a customer communication control. A future backend API should serve the same typed report and trace contracts with authentication and authorization.
