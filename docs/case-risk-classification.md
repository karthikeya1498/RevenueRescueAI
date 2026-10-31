# Case Risk Classification

**Phase**: 2.7 — Recovery Case Management Engine  
**Author**: Karthikeya  
**Status**: APPROVED & VERIFIED  

---

## 1. Risk Classification vs. Operational Priority

A fundamental architectural principle of RevenueRescueAI is the strict distinction between **Operational Priority** and **Revenue Risk Classification**:

- **Operational Priority (`priority: int`)**: *How urgently should the system or operator work on this case?* Expressed on a scale of `1` to `1000`.
- **Revenue Risk Classification (`risk_tier: str`)**: *How severe is the potential permanent revenue loss and churn situation?* Expressed as `HIGH`, `MEDIUM`, or `LOW`.

---

## 2. Risk Classification Rules

The deterministic classifier evaluates:
1. **Monetary Exposure Magnitude**:
   - `amount_minor >= 500,000` (>= $5,000 / ₹5,000): `+50` points.
   - `amount_minor >= 100,000` (>= $1,000 / ₹1,000): `+30` points.
   - `amount_minor >= 25,000` (>= $250 / ₹250): `+15` points.
   - Under $250: `+5` points.
2. **Recurring Revenue Impact**:
   - `SUBSCRIPTION_PAYMENT_FAILED`: `+25` points (risks ongoing subscriber lifetime value).
   - `INVOICE_OVERDUE`: `+20` points (uncollected accounts receivable aging).
   - `CHECKOUT_ABANDONED`: `+15` points (immediate buyer drop-off).
   - `PAYMENT_FAILED`: `+10` points (standard transaction failure).
3. **Failure Criticality**:
   - `fraud_suspected`: `+35` points (acute chargeback and loss risk). Immediately triggers `HIGH` risk tier.
   - `card_expired`: `+20` points (requires cardholder action; structural churn risk).
   - `do_not_honor`: `+15` points (hard issuer decline).
   - `insufficient_funds`: `+10` points (often transient).
   - `processing_error`: `+5` points (transient network glitch).
4. **Customer VIP/Enterprise Tier**:
   - Enterprise or Tier-1 customer: `+20` points.

---

## 3. Tier Decision Boundaries

- **`HIGH` Risk Tier**:
  - `risk_score >= 50` OR failure reason is `fraud_suspected`.
  - Situation: Large revenue loss, immediate subscriber churn danger, or acute chargeback risk.
- **`MEDIUM` Risk Tier**:
  - `25 <= risk_score < 50`.
  - Situation: Moderate exposure, standard card decline, or actionable renewal problem.
- **`LOW` Risk Tier**:
  - `risk_score < 25`.
  - Situation: Small transaction amount, transient network glitch, or low-probability churn situation.

---

## 4. Explainability and Auditability

Each risk evaluation produces a `RiskClassificationResult`:
```python
@dataclass(frozen=True)
class RiskClassificationResult:
    risk_tier: RiskTier
    reason: str
    factors: dict[str, Any]
```
The result is stored in the case's `metadata_json` under `"risk_tier"`, `"risk_reason"`, and `"risk_factors"`, and is mirrored in the initial `CASE_OPENED` compliance audit log.
