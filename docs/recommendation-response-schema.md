# Recommendation Response Schema & API Contract

## 1. Schema Definition (`CaseRecommendationDTO`)

The [`CaseRecommendationDTO`](file:///c:/Users/vanka/Downloads/RevenueRescueAI-main/RevenueRescueAI-main/backend/app/schemas/recommendations.py) is the external response contract returned by the intelligence engine:

```json
{
  "id": "7b36f874-8d96-419b-a3d8-7b960534c03d",
  "case_id": "c138d58a-36b9-470a-8bf7-e1da84988e01",
  "decision_version": 1,
  "recommended_strategy": "RETRY_LATER",
  "action_type": "retry_payment",
  "failure_category": "insufficient_funds",
  "risk_band": "low",
  "risk_score": 10,
  "recovery_probability": "0.5548",
  "confidence": "0.9500",
  "expected_value_minor": 6933,
  "explanation": "Recommended automated retry because the failure category (insufficient_funds) indicates a transient balance shortage that typically clears within 24 to 72 hours. Assessed risk band is LOW (score: 10/100).",
  "supporting_evidence": [
    "Recorded failure category: INSUFFICIENT_FUNDS",
    "Gateway decline code: insufficient_funds",
    "Financial exposure: USD 125.00",
    "Assessed risk band: LOW (score: 10/100)",
    "Prior recovery attempts: 0"
  ],
  "limitations": [
    "Probability estimate represents conditional statistical expectation, not a guaranteed financial outcome.",
    "Recommendation is subject to policy validation and retry limits in Phase 2.9 before execution."
  ],
  "analysis_method": "hybrid_expected_value",
  "model_version": "deterministic-logistic-v1",
  "validation_status": "not_validated",
  "generated_at": "2026-10-31T22:30:00Z",
  "candidate_strategies": [
    {
      "strategy": "RETRY_LATER",
      "action_type": "retry_payment",
      "probability": "0.5548",
      "recovery_value_minor": 6935,
      "cost_minor": 2,
      "expected_value_minor": 6933,
      "permitted": true,
      "reasons": [
        "Estimated recovery probability: 55.48%",
        "Estimated intervention cost: 2 minor units"
      ]
    },
    {
      "strategy": "UPDATE_PAYMENT_METHOD",
      "action_type": "send_reminder",
      "probability": "0.5050",
      "recovery_value_minor": 6313,
      "cost_minor": 15,
      "expected_value_minor": 6298,
      "permitted": true,
      "reasons": [
        "Card update not required for transient failure.",
        "Estimated recovery probability: 50.50%",
        "Estimated intervention cost: 15 minor units"
      ]
    },
    {
      "strategy": "MANUAL_REVIEW",
      "action_type": "request_operator_review",
      "probability": "0.4676",
      "recovery_value_minor": 5845,
      "cost_minor": 250,
      "expected_value_minor": 5595,
      "permitted": true,
      "reasons": [
        "Estimated recovery probability: 46.76%",
        "Estimated intervention cost: 250 minor units"
      ]
    },
    {
      "strategy": "NO_ACTION",
      "action_type": "stop",
      "probability": "0.3340",
      "recovery_value_minor": 4175,
      "cost_minor": 0,
      "expected_value_minor": 4175,
      "permitted": true,
      "reasons": [
        "Estimated recovery probability: 33.40%",
        "Estimated intervention cost: 0 minor units"
      ]
    }
  ]
}
```

---

## 2. Key Field Semantics

- **`validation_status`**: Stamped as `not_validated`. This makes it mathematically and operationally impossible for any automated background worker to execute the action without passing through Phase 2.9 Policy validation.
- **`decision_version`**: Strictly monotonically increasing integer ($1, 2, 3\dots$) per recovery case, guaranteeing audit trail integrity.
- **`candidate_strategies`**: Exposes the full comparative economic evaluation, showing why `RETRY_LATER` was chosen over other candidate actions.
