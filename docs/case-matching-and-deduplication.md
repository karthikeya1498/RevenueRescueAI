# Case Matching and Deduplication

**Phase**: 2.7 — Recovery Case Management Engine  
**Author**: Karthikeya  
**Status**: APPROVED & VERIFIED  

---

## 1. Principles of Case Identity

In financial systems, a customer may experience multiple genuine payment failures over time. Therefore, deduplication must **never** be performed solely on customer ID.

Instead, **Case Identity** is defined by the unique business revenue-risk problem represented by the canonical case key:

$$\text{case\_key} = f(\text{event\_type}, \text{provider}, \text{business\_reference}, \text{period})$$

### Case Key Syntax
- Subscription renewals: `CASE-SUB-{subscription_reference}-{billing_period}`
- Invoices: `CASE-INV-{invoice_reference}`
- Checkout abandonments: `CASE-CHK-{checkout_session_id}`
- Standard transactions: `CASE-TX-{provider}-{payment_reference}`

---

## 2. Handling Real-World Deduplication Scenarios

| Scenario | Input Pattern | Engine Behavior | Integrity Guarantee |
| :--- | :--- | :--- | :--- |
| **Scenario A: Exact Duplicate Event** | Same `(provider, external_event_id)` received again | Caught at Phase 2.6 ingestion boundary (`duplicate = True`); ignored by case engine | Zero duplicate cases; existing case remains untouched |
| **Scenario B: Subsequent Failure for Active Payment** | Distinct gateway retry failure for same payment intent | Matched by `case_key`; existing case updated; failure count incremented; `CASE_UPDATED` logged | Preserves single case for ongoing problem; maintains failure count history |
| **Scenario C: Distinct Payments for Same Customer** | Same customer, different `payment_reference` (e.g. `PAY-1` and `PAY-2`) | Different `case_key` derived; separate `RecoveryCase` records created | Legitimately tracks concurrent revenue problems independently |
| **Scenario D: Repeated Subscription Billings** | Same subscription, different monthly billing cycles (`202610` vs `202611`) | Distinct billing-period qualified keys; separate recovery cases created | Never merges distinct monthly accounting periods |
| **Scenario E: Late Failure for Terminal Case** | Failure arrives for a case already in `RECOVERED` or `STOPPED` | Case engine detects terminal status; historical resolution is preserved; event is ignored | Historical financial resolution is immutable; prevents phantom resurrection |
| **Scenario F: Concurrent Ingestion Conflict** | Two workers process failures for the same transaction simultaneously | Unique constraint `uq_recovery_case_key` raises `IntegrityError`; handled via nested transaction rollback and fallback to update | Exactly one case created; zero duplicate cases; safe retry semantics |
