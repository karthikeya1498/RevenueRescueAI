# RevenueRescueAI — Data Flow Architecture and Financial Authority

## 1. Executive Summary & Authoritative Source of Truth

In any fintech platform, ambiguity regarding data ownership leads to reconciliation disasters, duplicate charging, and false metrics reporting. **RevenueRescueAI enforces strict backend authority over all financial data.**

### Non-Negotiable Architectural Axioms:
1. **The Frontend is Never a Source of Truth:** The UI is an untrusted presentation layer. The browser client cannot compute recovered revenue, override policy checks, or alter retry counts. All metrics are computed server-side from immutable database ledgers.
2. **Integer Minor Units Only:** All monetary quantities are stored and transmitted as 64-bit integers representing minor currency units (e.g., $100.00 is strictly `10000` cents). Floating-point arithmetic (`0.1 + 0.2`) is completely prohibited.
3. **Data Minimization:** No Primary Account Numbers (PAN), CVVs, or unencrypted customer bank credentials enter RevenueRescueAI. Only tokenized provider identifiers (`pm_card_visa_4242`) are processed.

---

## 2. End-to-End Data Flow Diagram

```mermaid
flowchart TD
    subgraph External_Sources["1. External Event Sources"]
        GW[Stripe / Payment Gateway Webhook]
        SIM[Payment Simulator Mock Event]
    end

    subgraph Ingestion_Layer["2. Ingestion & Validation Layer"]
        SIG_CHK[HMAC-SHA256 Signature Validator]
        SCHEMA_VAL[JSON Schema / Pydantic Parser]
        DEDUP_CACHE[Deduplication Filter]
    end

    subgraph Relational_Store["3. Core Database (PostgreSQL Engine of Truth)"]
        TBL_EVENTS[(payment_events)]
        TBL_CASES[(recovery_cases)]
        TBL_DECISIONS[(agent_decisions)]
        TBL_ATTEMPTS[(recovery_attempts)]
        TBL_EVIDENCE[(recovery_evidence)]
        TBL_AUDIT[(audit_events - Append Only)]
    end

    subgraph Intelligence_Layer["4. Advisory & Policy Layer"]
        AI_CONTEXT[Context Assembler (Sanitizer)]
        LLM[AI Advisory Model / Fallback Engine]
        POLICY_GATE[Deterministic Policy Gate]
    end

    subgraph Execution_Layer["5. Execution & Settlement Layer"]
        REGISTRY[Tool Execution Registry]
        PAY_ADAPTER[Payment Gateway Adapter / Simulator]
        VERIFIER[Outcome Verification Engine]
    end

    subgraph Metrics_Presentation["6. Metrics & Presentation Layer"]
        METRICS_SVC[Metrics Aggregation Service]
        REST_API[FastAPI / REST Controller]
        UI_DASH[React / Next.js Fintech UI]
    end

    GW -->|POST /webhooks/gateway| SIG_CHK
    SIM -->|POST /simulator/events| SCHEMA_VAL
    SIG_CHK -->|Signature OK| SCHEMA_VAL
    SCHEMA_VAL -->|Validated DTO| DEDUP_CACHE
    
    DEDUP_CACHE -->|Check provider_event_id| TBL_EVENTS
    DEDUP_CACHE -->|Unique Event| TBL_EVENTS
    DEDUP_CACHE -->|Create / Bind Case| TBL_CASES
    
    TBL_CASES -->|Read Case Context & History| AI_CONTEXT
    AI_CONTEXT -->|Sanitized Prompt / Context| LLM
    LLM -->|Proposed Action DTO| POLICY_GATE
    POLICY_GATE -->|Record Decision & Rejection/Approval| TBL_DECISIONS
    
    POLICY_GATE -->|Approved Action Token| REGISTRY
    REGISTRY -->|Idempotent POST /charges| PAY_ADAPTER
    PAY_ADAPTER -->|Record In-Flight Attempt| TBL_ATTEMPTS
    PAY_ADAPTER -->|Gateway Response Payload| VERIFIER
    
    VERIFIER -->|Authoritative Evidence Record| TBL_EVIDENCE
    VERIFIER -->|Update State: RECOVERED or RETRY| TBL_CASES
    VERIFIER -->|Update Attempt Status| TBL_ATTEMPTS
    
    SIG_CHK -.->|Log| TBL_AUDIT
    POLICY_GATE -.->|Log| TBL_AUDIT
    REGISTRY -.->|Log| TBL_AUDIT
    VERIFIER -.->|Log| TBL_AUDIT
    
    TBL_CASES -->|Aggregated SQL Query| METRICS_SVC
    TBL_ATTEMPTS -->|Success Rate Calculation| METRICS_SVC
    METRICS_SVC -->|GET /api/v1/metrics/summary| REST_API
    REST_API -->|Read-Only JSON Stream| UI_DASH
```

---

## 3. Step-by-Step Data Movement

### Step 1: Event Origin & Ingestion
- **Origin:** Events originate from the external Payment Gateway (e.g., Stripe, Adyen) or the local `PaymentSimulator` during integration testing.
- **Entry Point:** HTTP POST to `/api/v1/webhooks/gateway` with header `Stripe-Signature` or `X-Webhook-Signature`.
- **Validation:** 
  1. HMAC-SHA256 signature calculated over raw bytes using merchant webhook secret.
  2. Payload parsed into `PaymentEventDTO` verifying non-null `event_id`, `amount_cents`, `currency`, and `customer_id`.
  3. Deduplication query: `SELECT id FROM payment_events WHERE provider_event_id = :id`.
- **Storage:** Persisted into `payment_events` table as an immutable raw event record.

### Step 2: Case Creation & Context Assembly
- If no active case exists for the `invoice_id`, a new row is created in `recovery_cases` with `state = 'DETECTED'`.
- The case metadata is populated: `nominal_amount_cents`, `currency`, `failure_code`, `customer_id`, and `attempt_count = 0`.
- Case transitions through `VALIDATING` and `ELIGIBILITY_CHECK`.

### Step 3: AI Advisory Data Movement
- The `ContextAssembler` extracts:
  - Case attributes: `failure_code` (e.g., `insufficient_funds`), `attempt_count`, `currency`, `nominal_amount_cents`.
  - Customer payment history: prior successful payment count, customer tenure.
- **Sanitization & Masking:** Strips customer names, email addresses, and phone numbers. Replaces with pseudo-anonymized customer UUID.
- Context formatted into strict JSON prompt delivered to the AI model.
- AI returns JSON matching schema: `{"action_type": "SCHEDULED_RETRY", "delay_hours": 24, "reasoning": "Soft decline on Friday night; schedule retry Monday morning."}`.

### Step 4: Policy Recording & Action Dispatch
- Proposed action delivered to `PolicyValidationEngine`.
- Deterministic rules evaluated synchronously against database state.
- Result recorded in `agent_decisions`:
  - `case_id`, `action_proposed`, `is_policy_approved`, `rejection_reason`, `created_at`.
- If approved, `ToolExecutionRegistry` generates a deterministic UUIDv5 `idempotency_key = uuid5(case_id, attempt_number)`.

### Step 5: Execution, Verification, & Evidence Storage
- `ToolExecutionRegistry` dispatches HTTP POST to the payment adapter.
- In-flight attempt saved in `recovery_attempts`: `status = 'IN_PROGRESS'`.
- Adapter returns provider response.
- `OutcomeVerificationService` performs strict validation:
  1. Provider status must equal `"succeeded"`.
  2. Transaction amount must exactly match `case.nominal_amount_cents`.
  3. Currency must match `case.currency`.
- If verified, a record is inserted into `recovery_evidence` containing `provider_transaction_id`, `gateway_receipt_hash`, and `verified_at`.
- `recovery_cases` updated: `state = 'RECOVERED'`, `recovered_amount_cents = nominal_amount_cents`.

### Step 6: Audit Logging
- Every single state mutation, policy decision, attempt dispatch, and verification verdict writes a synchronous, append-only row to `audit_events`.
- Columns: `id`, `case_id`, `correlation_id`, `actor_type`, `event_type`, `old_state`, `new_state`, `payload_hash`, `created_at`.
- Immutable: Database user permissions revoke `UPDATE` and `DELETE` on this table.

### Step 7: Dashboard Metrics Derivation
- Frontend calls `GET /api/v1/metrics/overview`.
- The `DashboardMetricsService` executes optimized SQL aggregation queries directly against Postgres:
  - **Revenue at Risk:** `SELECT COALESCE(SUM(nominal_amount_cents), 0) FROM recovery_cases WHERE state NOT IN ('RECOVERED', 'CLOSED');`
  - **Recovered Revenue:** `SELECT COALESCE(SUM(recovered_amount_cents), 0) FROM recovery_cases WHERE state = 'RECOVERED';`
  - **Recovery Rate (%):** `(recovered_cases_count / total_eligible_cases_count) * 100`.
- The API delivers a strongly typed JSON response. The client merely renders the numbers.

---

## 4. Authoritative Source of Truth Matrix

| Financial Concept / Metric | Authoritative Database Source | Table & Column | Why External Sources / UI Are Disallowed |
| :--- | :--- | :--- | :--- |
| **Gross Revenue at Risk** | PostgreSQL | `recovery_cases.nominal_amount_cents` | Gateway payloads can have fluctuating statuses; only ingested, validated active cases represent true at-risk pipeline. |
| **Gross Recovered Revenue** | PostgreSQL | `recovery_cases.recovered_amount_cents` | Webhook HTTP success != settled recovery. Only rows backed by `recovery_evidence` entries are tallied. |
| **Case Recovery State** | PostgreSQL | `recovery_cases.state` | State machine transitions are transactional and locked against race conditions. |
| **Retry Attempt Counter** | PostgreSQL | `recovery_cases.attempt_count` | AI or external queues could lose count; database counter guarantees compliance with Max Retries <= 3. |
| **Legitimate Recovery Proof**| PostgreSQL | `recovery_evidence.provider_transaction_id` | Prevents audit discrepancies by storing gateway cryptographic receipt hashes. |
| **Safety Compliance Rate** | PostgreSQL | `agent_decisions.is_policy_approved` | Evaluated mathematically from recorded policy pass/reject counts; cannot be falsified. |
| **Audit History** | PostgreSQL | `audit_events` | Immutable append-only ledger; authoritative legal proof for SOC2/PCI-DSS compliance. |

---

## 5. Data Flow Invariants & Boundaries

1. **Unidirectional Execution Flow:** Data never flows backwards from external tools into policy evaluation without passing through the Verification Service.
2. **Transaction Isolation:** Financial mutations (case state + attempt record + audit row) must occur within `READ COMMITTED` or `SERIALIZABLE` isolation levels to eliminate phantom reads.
3. **Audit Immutability:** Audit rows cannot be altered, even by database administrators, preserving evidentiary value for external financial audits.
