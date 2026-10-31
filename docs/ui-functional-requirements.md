# RevenueRescueAI — User Interface Functional Requirements & Design System

> **Document ID:** DOC-UIR-009  
> **Phase:** 0.2 (User Stories, Functional Requirements & Acceptance Criteria)  
> **Status:** Approved Baseline  
> **Audience:** Product Engineering, Architecture, QA, Security, Beginner Developers  

---

## 1. Executive Summary

The RevenueRescueAI interface is envisioned as an enterprise-grade **Dark Futuristic Fintech Command Center**. A financial recovery operator or finance executive does not want a playful, cartoonish, or cluttered interface; they require a high-density, mission-critical workspace that delivers immediate situational awareness, total diagnostic explainability, and unambiguous financial metrics.

This document formally specifies the functional requirements for five core application views, establishes the visual design system, defines accessible interactive behaviors, and specifies loading, empty, and error states.

*(Note: This is a requirements-engineering specification. No frontend code is implemented in this phase.)*

---

## 2. Visual Design System & Aesthetic Foundation

```text
+------------------------------------------------------------------------+
| SURFACE ARCHITECTURE:                                                  |
| - Base Canvas:       Deep Void Black        (#06090E)                  |
| - Primary Panel:     Deep Midnight Navy     (#0B0F19)                  |
| - Card / Container:  Rich Dark Charcoal     (#111827)                  |
| - Table Alternate:   Obsidian Slate         (#0D131F)                  |
| - Surface Borders:   Subtle Cyan/Blue Edge  (1px solid #1E293B)        |
+------------------------------------------------------------------------+
| ACCENT COLOR SYSTEM:                                                   |
| - Electric Cyan:     System Live Nodes & Telemetry  (#06B6D4 / #22D3EE)|
| - Royal Blue:        Primary Action & Navigation    (#3B82F6 / #60A5FA)|
| - Neon Purple:       AI Diagnostic Reasoning Badges (#A855F7)          |
| - Vivid Magenta:     High-Priority Escalation Alerts(#EC4899)          |
| - Emerald Green:     Confirmed Recovered Settlement (#10B981)          |
| - Warning Amber:     Revenue at Risk / Soft Decline (#F59E0B)          |
| - Crimson Red:       Hard Decline / Terminal Stop   (#F43F5E)          |
+------------------------------------------------------------------------+
| TYPOGRAPHY & DATA DENSITY:                                             |
| - Primary Headings:  Outfit / Inter, Sans-Serif, High-Contrast White   |
| - Financial Figures: Tabular Monospace (tabular-nums, e.g., JetBrains) |
| - Text Contrast:     Minimum 4.5:1 (WCAG 2.1 AA Standard)              |
+------------------------------------------------------------------------+
```

---

## 3. Page-by-Page Functional Requirements

---

### Page 1: Executive Command Center & Dashboard

#### 1. Purpose & Layout
The central mission control for finance executives and recovery operations managers. Provides instant situational awareness through top-tier KPI cards, time-series recovery trends, and live queue status.

#### 2. Functional Requirements
- **FR-UI-001 (KPI Strip):** The page shall render five primary financial KPI cards across the top viewport:
  1. *Confirmed Recovered Revenue:* Large monospace dollar figure formatted as `$XX,XXX.XX` with a positive trend badge.
  2. *Total Revenue at Risk:* Gross problem size in amber typography.
  3. *Recovery Success Rate:* Percentage calculated as $\frac{R_{\text{recovered}}}{R_{\text{eligible}}} \times 100\%$ with decimal precision.
  4. *Active Pipeline Cases:* Current volume of cases undergoing active recovery.
  5. *Safety Violations Blocked:* Defensive metric showing policy gate efficacy (must display `100% Defended` or `0 Violations`).
- **FR-UI-002 (Recovery Trend Chart):** Renders a responsive time-series visualization comparing cumulative recovered revenue against the cumulative revenue-at-risk trajectory.
- **FR-UI-003 (Workflow Status Funnel):** Renders a horizontal funnel chart showing case drop-off across lifecycle stages: `Detected` -> `Eligible` -> `Actioned` -> `Verified Recovered`.
- **FR-UI-004 (Recent Live Activity Feed):** Displays the five most recent verified recovery settlements with animated micro-pulse indicator.

---

### Page 2: At-Risk Revenue & Case Queue

#### 1. Purpose & Layout
The tactical operating workspace for RevOps analysts. Features a high-density, paginated table of all active and resolved recovery cases with multi-criteria filtering and instant search.

#### 2. Functional Requirements
- **FR-UI-005 (Global Search Bar):** Real-time text search filtering across `case_id`, `customer_id`, `invoice_id`, and `customer_email`.
- **FR-UI-006 (Multi-Dimension Filter Bar):**
  - *State Filter:* Multi-select dropdown for `DETECTED`, `ELIGIBLE`, `POLICY_APPROVED`, `WAITING_FOR_VERIFICATION`, `RECOVERED`, `ESCALATED`, `HALTED`.
  - *Failure Reason Filter:* Dropdown for `Temporary Balance`, `Technical Error`, `Stolen Card`, `Network Timeout`.
  - *Amount Range Slider:* Dual-handle slider filtering min/max transaction amounts.
- **FR-UI-007 (Case Queue Table):** Renders high-density rows containing:
  - Checkbox (for bulk selection).
  - Case ID (monospace link).
  - Customer identifier & masked email.
  - Nominal Amount (tabular numerals, e.g., `$149.00`).
  - Failure Class badge (color-coded).
  - Current State badge (semantic styling).
  - Attempt Counter (e.g., `1 / 3`).
  - Ingestion Timestamp.
- **FR-UI-008 (Row Click Interaction):** Clicking any row opens the Case Diagnostic Trace Drawer (Page 3 component).

---

### Page 3: Recovery Workflows & Case Diagnostic Drawer

#### 1. Purpose & Layout
A slide-over right drawer (or dedicated detail page) that provides complete, explainable insight into the decision-making lifecycle for a single selected recovery case.

#### 2. Functional Requirements
- **FR-UI-009 (Header Summary):** Displays Case ID, Customer Reference, Amount in currency, and current Workflow State badge.
- **FR-UI-010 (Telemetry & Diagnosis Section):**
  - Displays raw gateway response code (e.g., `card_declined: 51`).
  - Normalized failure class and decline severity (Soft vs. Hard).
  - AI Model Confidence Score (progress bar from 0% to 100%).
  - AI Explainability Rationale box: plain-English paragraph detailing why the strategy was chosen.
- **FR-UI-011 (Policy Enforcement Log):**
  - Checkmark list of every policy rule evaluated:
    - [x] Rule 1: Invoice Unpaid Check (PASS)
    - [x] Rule 2: Hard Decline Prohibition (PASS)
    - [x] Rule 3: Attempt Budget <= 3 (PASS: Attempt 1 of 3)
    - [x] Rule 4: Backoff Interval >= 24h (PASS: Scheduled in 48h)
  - Policy Decision token: `APPROVED` (Green) or `REJECTED` (Red).
- **FR-UI-012 (Tool Execution & Settlement Proof):**
  - Idempotency Token used (`idemp_case_101_att_1`).
  - Dispatched timestamp and provider acknowledgment latency.
  - Authoritative Gateway Settlement Receipt: displays raw transaction ID, settlement timestamp, captured amount, and verification status badge.
- **FR-UI-013 (Sequential Audit Timeline):** Vertical timeline component showing chronological transitions from `DETECTED` to final resolution.

---

### Page 4: Immutable Audit Log Explorer

#### 1. Purpose & Layout
A compliance and forensic investigation interface allowing auditors and SREs to inspect the global append-only event stream.

#### 2. Functional Requirements
- **FR-UI-014 (Audit Event Stream Table):** Displays columns:
  - Event UUID.
  - ISO-8601 UTC Timestamp (with microsecond precision).
  - Correlation ID (copy-to-clipboard button).
  - Case ID.
  - Actor / System Component (`EVENT_INGESTION`, `POLICY_GATE`, `WORKFLOW_ENGINE`, `OPERATOR`).
  - Action Executed (`CASE_DETECTED`, `POLICY_APPROVED`, `TOOL_DISPATCHED`, `SETTLEMENT_VERIFIED`).
  - Payload SHA-256 Hash.
- **FR-UI-015 (Correlation ID Deep Filter):** Allows pasting a correlation ID to instantly isolate every distributed system event associated with that specific execution trace.
- **FR-UI-016 (CSV / JSON Compliance Export):** Button allowing auditors to export the filtered audit stream as a cryptographically signed CSV or JSON file.

---

### Page 5: Evaluation Lab & Baseline Comparison

#### 1. Purpose & Layout
A specialized analytical workbench where RevOps analysts run reproducible batch simulations and compare RevenueRescueAI's recovery performance against counterfactual baselines.

#### 2. Functional Requirements
- **FR-UI-017 (Simulation Control Bar):**
  - Seed input field (default: `42`).
  - Scenario Count dropdown (`100`, `500`, `1,000`).
  - Rule Version selector (`phase8.v1`).
  - "Run Batch Evaluation" button with loading progress indicator.
- **FR-UI-018 (Comparative Baseline Table):** Renders a structured matrix comparing:
  - Baseline 1: Do-Nothing (0.0% recovery).
  - Baseline 2: Always-Retry (blind retrier).
  - Baseline 3: Simple Rule-Based (standard 24h backoff).
  - Baseline 4: RevenueRescueAI Agent.
  - Baseline 5: Oracle Upper Bound.
  - Columns display: Recovered Count, Recovered Revenue ($), Revenue Recovery Rate (%), Relative Lift (%), Safety Violation Rate (must be 0.00%).
- **FR-UI-019 (Synthetic Benchmark Disclaimer Notice):** Prominently rendered warning banner:  
  `"NOTICE: Evaluation Lab operates exclusively on synthetic regression fixtures. Benchmark results do not represent live customer revenue."`

---

## 4. Universal Interactive States & Accessibility Standards

### 4.1 State Definitions
- **Loading State:** Shimmer/skeleton screens matching card and table dimensions; spinner on action buttons. Never show raw blank screens during API fetch.
- **Empty State:** Clean, dark illustrations with clear messaging (e.g., *"No cases match the selected filter criteria. Reset filters to view all cases."*) and a reset button.
- **Error State:** High-visibility banner with error explanation, correlation ID for debugging, and a single-click "Retry Request" action.

### 4.2 Semantic Status Badge Standards
Status badges must adhere to uniform semantic color coding across all views:

| Badge Text | Fill Color | Border Color | Meaning |
|---|---|---|---|
| `RECOVERED` | Emerald Green (`#064E3B`) | `#10B981` | Real funds confirmed collected. |
| `AT RISK` | Dark Amber (`#78350F`) | `#F59E0B` | Uncollected money requiring intervention. |
| `ELIGIBLE` | Deep Cyan (`#164E63`) | `#06B6D4` | Passed pre-screening; queued for action. |
| `POLICY APPROVED` | Royal Blue (`#1E3A8A`) | `#3B82F6` | Validated by policy; authorized for dispatch. |
| `VERIFYING` | Pulsing Violet (`#4C1D95`) | `#A855F7` | Awaiting provider settlement receipt. |
| `UNCERTAIN` | Indigo Slate (`#312E81`) | `#6366F1` | Gateway timed out; actions frozen. |
| `ESCALATED` | Vivid Magenta (`#831843`) | `#EC4899` | High value / anomaly; human review required. |
| `HALTED` | Dark Charcoal (`#1E293B`) | `#64748B` | Terminal stop; retries exhausted. |

### 4.3 Accessibility & Keyboard Navigation (WCAG 2.1 AA)
- **Keyboard Navigation:** All interactive elements (buttons, inputs, drawer close, table rows) must be fully navigable using `Tab`, `Enter`, `Space`, and `Escape`.
- **Visible Focus Rings:** Focused elements must display a distinct 2px electric cyan outline (`outline: 2px solid #06B6D4; outline-offset: 2px;`).
- **Screen Reader Support:** All KPI figures, icon buttons, and status badges must include descriptive `aria-label` attributes.
- **Tabular Figures:** All financial figures must use `font-variant-numeric: tabular-nums` to guarantee vertical decimal alignment.

---

## 5. Scope Boundary: MVP vs. Post-MVP UI Capabilities

| Interface Feature | Phase 0.2 / MVP Scope | Post-MVP Future Scope |
|---|:---:|:---:|
| **Executive KPI Cards** | **MANDATORY** | Real-time WebSocket streaming |
| **Recovery Case Queue** | **MANDATORY** | Bulk operator multi-actions |
| **Case Diagnostic Drawer** | **MANDATORY** | Live AI chat prompt debugger |
| **Audit Log Explorer** | **MANDATORY** | Cryptographic blockchain ledger export |
| **Evaluation Lab Table** | **MANDATORY** | Dynamic custom curve training interface |
| **Dark Neon Fintech Theme**| **MANDATORY** | User-customizable CSS theme toggles |
| **Authentication & SSO UI** | Local perspective toggle | Okta / Azure AD SAML Login Screen |
| **Hosted Customer Portal** | Simulated mock receipt | Live responsive card update checkout |
