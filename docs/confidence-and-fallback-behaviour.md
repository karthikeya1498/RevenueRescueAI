# Confidence Scoring & Deterministic Fallback Behaviour

## 1. Objective

In financial AI applications, silent guessing or uncalibrated confidence scores are catastrophic. The engine implements explicit fallback behaviors when diagnostics are missing, unmapped, or ambiguous.

---

## 2. Confidence Calculation Principles

1. **Failure Analysis Confidence**:
   - Explicit keyword match on standard categories: `0.9000` to `0.9500`.
   - Generic or unmapped gateway error: `0.5500`.
2. **Strategy Confidence Synthesis**:
   $$\text{Confidence} = \min\left(\text{Failure Confidence}, \max\left(P(\text{Recovery}), 0.5000\right)\right)$$
   For terminal cases (`NO_ACTION`), confidence is strictly **`1.0000`** (100% certainty of halting).

---

## 3. Fallback Matrix

| Ambiguity / Anomaly Condition | Fallback Action / Classification | Confidence Output | System Behavior |
| :--- | :--- | :---: | :--- |
| **Missing Failure Code & Message** | `unknown_failure` $\rightarrow$ `MANUAL_REVIEW` | `0.5500` | Flags case for operator inspection. Never attempts blind automated charging. |
| **Unrecognized Decline Code** | `unknown_failure` $\rightarrow$ `MANUAL_REVIEW` | `0.5500` | Logs unknown code in audit trail for rule catalogue expansion. |
| **Terminal Case Status** | `case_already_resolved` $\rightarrow$ `NO_ACTION` | `1.0000` | Immutability guarantee: terminal cases never receive active recovery actions. |
| **Exhausted Attempts ($\ge 4$)** | `quota_exhausted` $\rightarrow$ `MANUAL_REVIEW` | `0.6000` | Blocks `RETRY_LATER` to prevent cardholder harassment. |
| **High Risk Signal ($\ge 70$)** | `risk_blocked` $\rightarrow$ `MANUAL_REVIEW` | `0.7500` | Suppresses automated retry; mandates compliance human sign-off. |
| **Database Failure / Exception** | Transaction Rollback | N/A | RFC-7807 error returned to client; financial records remain unmutated. |
