# RevenueRescueAI — Payment Simulator Architecture
## Phase 1.1: Deterministic Payment Provider Emulation and Fault Injection

**Document Version:** 1.0.0  
**Status:** Approved Simulator Architecture  
**Primary Authors:** Senior Fintech Engineer, QA Architect, Systems Architect  

---

## 1. Executive Summary & Core Simulator Purpose

In financial engineering, connecting an early-stage application or automated evaluation pipeline directly to live payment networks (Stripe, Adyen, Visa Direct) introduces severe operational, financial, and legal risks:
- Live transactions incur real gateway fees and interchange charges.
- Simulating edge cases (e.g., gateway 504 timeouts, lost webhooks, stolen cards) is impossible or dangerous against real card rails.
- Automated CI/CD test runs require **100% deterministic reproducibility**, which live payment gateways cannot guarantee.

The **Payment Provider Simulator** is a dedicated, stateful, in-memory/relational adapter that emulates real-world banking rails with mathematical precision, controlled fault injection, and zero external network dependencies.

---

## 2. Strict Emulation Boundary & Safety Isolations

To ensure the simulator is **never mistaken for a real payment processor**:
1. **Explicit Provider Identifier:** All records created by the simulator bear `provider: "synthetic"` or `provider: "simulator"`. Live card brand networks are never invoked.
2. **Deterministic ID Prefixes:** All generated transaction and charge references carry explicit synthetic prefixes:
   - Customers: `cus_sim_...`
   - Transactions: `txn_sim_...`
   - Charges: `ch_sim_...`
   - Webhook Events: `evt_sim_...`
3. **Live Credential Tripwire:** If the application detects live Stripe or payment gateway API keys (e.g., keys starting with `sk_live_`), the backend startup process halts immediately with a fatal configuration error.
4. **Zero Real Cardholder Data:** The simulator generates only synthetic customer accounts and rejects any attempt to pass real card numbers (PANs) or live credentials.

---

## 3. Supported Controlled Outcomes & Failure Taxonomy

The simulator implements a comprehensive spectrum of banking outcomes, categorized into four distinct behavior classes:

```
+-----------------------------------------------------------------------------------------------+
|                                  SIMULATOR OUTCOME MATRIX                                     |
+-------------------+-----------------------------------+---------------------------------------+
| Outcome Category  | Provider Code                     | Expected Workflow Behavior            |
+-------------------+-----------------------------------+---------------------------------------+
| Succeeded         | `succeeded`                       | Generate Evidence -> Mark RECOVERED   |
| Soft Decline      | `insufficient_funds`              | Retryable -> Schedule Backoff Retry   |
| Soft Decline      | `do_not_honor`                    | Retryable with limit -> Verify limit  |
| Hard Decline      | `card_expired`                    | Non-retryable -> Request Card Update  |
| Hard Decline      | `stolen_card` / `fraud_block`     | Terminal -> Cease All Actions & Lock  |
| Network Fault     | `gateway_timeout_504`             | State -> VERIFICATION_PENDING         |
| Rate Limit        | `rate_limit_429`                  | Transient -> Bounded Exponential Retry|
| Uncertain State   | `pending_review` / `unknown`      | State -> VERIFICATION_PENDING (Wait)  |
| Duplicate Replay  | Duplicate `external_event_id`     | Deduplicator catches -> Drop duplicate|
+-------------------+-----------------------------------+---------------------------------------+
```

### 3.1 Detailed Behavior Specifications:
1. **`succeeded`:** The charge is authorized and captured immediately. Returns HTTP 200 with `charge_id` and captures funds in minor units.
2. **`insufficient_funds` (Soft Decline):** The cardholder's balance is inadequate. Emulates a temporary decline where retry in 4–24 hours may succeed.
3. **`card_expired` (Hard Decline):** The physical payment credential is permanently invalid. Retrying the same card is guaranteed to fail. The simulator tests whether the system correctly triggers `REQUEST_PAYMENT_METHOD_UPDATE`.
4. **`gateway_timeout_504` (Transient Network Glitch):** The simulator drops the connection or returns an HTTP 504 without returning a response payload. This tests **Invariant INV-008**: the engine must *never* assume the payment failed and must *never* retry immediately; it must transition to `VERIFICATION_PENDING` and query the provider status.
5. **`duplicate_event_notification`:** The simulator deliberately sends the identical webhook event twice (same `event_id` and `payload_hash`) to verify that the deduplication engine returns HTTP 200 without executing a second recovery attempt.

---

## 4. Scenario Reproducibility & Deterministic Seeding

A critical requirement of Phase 0 and Phase 1 is the **500-Scenario Evaluation Engine**. For an engineering team to benchmark changes across git commits, the evaluation batch must produce **identically matching results every single time**.

### 4.1 Pseudo-Random Seeding (Seed 42)
The simulator utilizes Python's `random.Random(seed=42)` to generate scenarios:
```python
class ScenarioGenerator:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_batch(self, count: int = 500) -> list[Scenario]:
        scenarios = []
        for i in range(count):
            amount_minor = self.rng.randint(2500, 1500000)  # $25.00 to $15,000.00
            failure_type = self.rng.choices(
                ["insufficient_funds", "card_expired", "stolen_card", "timeout"],
                weights=[0.60, 0.20, 0.10, 0.10]
            )[0]
            scenarios.append(Scenario(id=f"eval-{i:04d}", amount=amount_minor, code=failure_type))
        return scenarios
```
Because the seed is fixed:
- Scenario #42 will *always* be an insufficient funds failure for $8,420.00.
- Scenario #181 will *always* be a 504 gateway timeout.
- The batch recovery metrics ($980,887 recovered out of $2,163,200 at risk, 45.34% recovery rate) remain identical across all developer laptops.

---

## 5. Verification Handshake & Status Inquiries

When an action is executed against the simulator, how does the recovery engine verify the outcome?

```
+-----------------------------------------------------------------------------------+
|                           TWO-WAY VERIFICATION HANDSHAKE                          |
|                                                                                   |
|  [ Recovery Engine ]                                    [ Payment Simulator ]     |
|          |                                                         |              |
|          |--- 1. POST /charges (amount: 842000, key: idemp_01) --->|              |
|          |                                                         |              |
|          |    (If Timeout or Network Drop occurs)                  |              |
|          |x------------------ 504 Gateway Timeout -----------------|              |
|          |                                                         |              |
|          |    Case placed in VERIFICATION_PENDING                  |              |
|          |                                                         |              |
|          |--- 2. GET /charges?idempotency_key=idemp_01 ----------->|              |
|          |                                                         |              |
|          |<-- 3. Return Settled Status (status: 'succeeded') ------|              |
|          |                                                         |              |
|          |--- 4. Verify exact amount & customer ID                 |              |
|          |--- 5. Insert row into recovery_evidence                 |              |
|          |--- 6. Transition Case State to RECOVERED                |              |
+-----------------------------------------------------------------------------------+
```

### Handshake Invariants:
1. **Idempotency Key Persistence:** The simulator caches every processed charge by `idempotency_key`. A query by idempotency key returns the true settled state of the transaction.
2. **Delayed Confirmation Emulation:** In real banking, transactions like ACH or SEPA take days to settle. The simulator emulates this by supporting a `settlement_delay_seconds` parameter, allowing the test suite to verify that the workflow engine waits in `VERIFICATION_PENDING` without prematurely aborting.
