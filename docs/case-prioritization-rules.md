# Case Prioritization Rules

**Phase**: 2.7 — Recovery Case Management Engine  
**Author**: Karthikeya  
**Status**: APPROVED & VERIFIED  

---

## 1. Prioritization Overview

In RevenueRescueAI, **Operational Priority** determines queue position in the operator workbench and automated execution dispatch.
- **Scale**: Integer from `1` (highest urgency) to `1000` (lowest urgency).
- **Ordering Invariant**: Ascending order (`order_by(RecoveryCase.priority.asc())`). Lower integer values are pulled first.
- **Rule Design**: Strictly deterministic, explainable, and transparent. No black-box AI weights.

---

## 2. Calculation Breakdown

Every case starts with `BASE_PRIORITY = 100`. Adjustments are applied additively:

### 2.1 Financial Exposure Adjustments
| Exposure Condition | Adjustment | Rationale |
| :--- | :--- | :--- |
| `amount_minor >= 500,000` (>= $5,000 / ₹5,000) | `-50` | Major revenue exposure demands top queue priority |
| `amount_minor >= 100,000` (>= $1,000 / ₹1,000) | `-25` | Significant revenue exposure prioritized |
| `amount_minor >= 25,000` (>= $250 / ₹250) | `-10` | Moderate exposure |
| `amount_minor < 5,000` (< $50 / ₹50) | `+15` | Low exposure routed to standard queue |

### 2.2 Failure Category Adjustments
| Failure Category | Adjustment | Rationale |
| :--- | :--- | :--- |
| `insufficient_funds` | `-20` | Transient balance shortage has high recovery probability via timed retry |
| `processing_error`, `network_error`, `timeout` | `-25` | Transient gateway error prioritized for rapid re-attempt |
| `authentication_required`, `3d_secure` | `+10` | Requires cardholder step-up intervention |
| `card_expired` | `+15` | Requires customer payment method update |
| `do_not_honor`, `card_declined` | `+10` | Bank decline requires customer inquiry |
| `fraud_suspected` | `+50` | De-prioritized for automated retry and flagged for risk review |

### 2.3 Elapsed Aging Escalations
| Unresolved Elapsed Time | Adjustment | Rationale |
| :--- | :--- | :--- |
| `elapsed_hours >= 48` | `-20` | Unresolved for > 48h; critical aging escalation |
| `elapsed_hours >= 24` | `-10` | Unresolved for > 24h; elevated operational priority |

### 2.4 Final Clamping
The raw score is clamped to maintain the invariant:
$$\text{final\_priority} = \max(1, \min(1000, \text{score}))$$

---

## 3. Explainability Model

Every prioritization execution outputs a structured `PriorityResult`:
```python
@dataclass(frozen=True)
class PriorityResult:
    priority: int
    reason: str
    factors: dict[str, Any]
```
Example Output:
- **Priority**: `25`
- **Reason**: *"Significant exposure (USD 1,499.00) prioritized. Transient balance shortage has high recovery probability via scheduled retry."*
- **Factors**: `{"base_priority": 100, "exposure_adjustment": -25, "failure_adjustment": -20, "amount_minor": 149900, "currency": "USD"}`
