"""Deterministic, versioned recovery probability estimator.

Author: Karthikeya
Architectural layer: domain service / statistical estimator.

Implements a calibrated, inspectable logistic probability model (deterministic-logistic-v1).
Produces reproducible estimates without black-box hallucination, serving as the
authoritative baseline for RevenueRescueAI.
"""

from __future__ import annotations

from decimal import Decimal
from math import exp
from typing import Any

from app.core.enums import ActionType
from app.services.intelligence.model_adapter import RecoveryEstimatorAdapter


class LogisticRecoveryEstimator(RecoveryEstimatorAdapter):
    """Calibrated logistic regression estimator with explicit, inspectable coefficients."""

    VERSION = "deterministic-logistic-v1"

    # Transparent regression weights
    COEFFICIENTS = {
        "bias": -0.65,
        "low_attempts_bonus": 0.42,
        "repeated_attempts_penalty": -0.25,
        "customer_history_weight": 0.55,
        "alternate_method_bonus": 0.25,
        "retryable_action_bonus": 0.45,
        "high_risk_penalty": -1.20,
        "operator_review_bonus": 0.10,
        "stop_penalty": -0.45,
    }

    @property
    def model_version(self) -> str:
        return self.VERSION

    def estimate_recovery_probability(
        self,
        *,
        action_type: ActionType,
        failure_category: str,
        is_retryable: bool,
        amount_minor: int,
        prior_attempts: int,
        customer_success_rate: float = 0.5,
        alternate_method_available: bool = True,
        risk_score: int = 0,
        features: dict[str, Any] | None = None,
    ) -> Decimal:
        """Calculate mathematically bounded conditional recovery probability."""
        z = self.COEFFICIENTS["bias"]

        # 1. Attempt History Impact
        if prior_attempts <= 1:
            z += self.COEFFICIENTS["low_attempts_bonus"]
        else:
            z += self.COEFFICIENTS["repeated_attempts_penalty"] * min(prior_attempts, 4)

        # 2. Historical Customer Reliability
        # Centers customer_success_rate around 0.5
        normalized_rate = max(0.0, min(1.0, customer_success_rate))
        z += self.COEFFICIENTS["customer_history_weight"] * (normalized_rate - 0.5)

        # 3. Action-Specific Interactions
        if action_type == ActionType.SEND_REMINDER and alternate_method_available:
            z += self.COEFFICIENTS["alternate_method_bonus"]

        if action_type == ActionType.RETRY_PAYMENT and is_retryable:
            z += self.COEFFICIENTS["retryable_action_bonus"]

        if action_type == ActionType.REQUEST_OPERATOR_REVIEW:
            z += self.COEFFICIENTS["operator_review_bonus"]

        if action_type == ActionType.STOP:
            z += self.COEFFICIENTS["stop_penalty"]

        # 4. Severe Risk Penalization
        if risk_score >= 70:
            z += self.COEFFICIENTS["high_risk_penalty"]

        # 5. Logistic Sigmoid Function: p = 1 / (1 + e^(-z))
        prob_raw = 1.0 / (1.0 + exp(-z))

        # Clamp between 0.0100 and 0.9900 to prevent degenerate probabilities
        prob_clamped = max(0.01, min(0.99, round(prob_raw, 4)))
        return Decimal(str(prob_clamped)).quantize(Decimal("0.0001"))
