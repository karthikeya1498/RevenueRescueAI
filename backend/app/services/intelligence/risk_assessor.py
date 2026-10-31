"""Revenue risk assessment engine for recovery decision intelligence.

Author: Karthikeya
Architectural layer: domain service / risk assessment.

Computes a transparent 0-100 risk score and classifies the case into risk bands
(high, medium, low) with concrete contributing signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RiskAssessmentResult:
    """Outcome of risk assessment."""

    score: int
    band: str  # high, medium, low
    reasons: list[str] = field(default_factory=list)
    action_limit: str = "automatic"  # automatic, human_approval, block


class RiskAssessor:
    """Evaluates case risk dimensions and policy constraints."""

    HIGH_THRESHOLD = 70
    MEDIUM_THRESHOLD = 30

    @classmethod
    def assess(
        cls,
        *,
        failure_category: str,
        amount_minor: int,
        prior_attempts: int,
        unusual_velocity: bool = False,
        customer_restricted: bool = False,
        is_subscription: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> RiskAssessmentResult:
        """Calculate composite 0-100 risk score and operational action limit."""
        score = 0
        reasons: list[str] = []

        # 1. Fraud / Security Signal
        if failure_category in ("fraud_suspected", "risk_blocked"):
            score += 60
            reasons.append("provider_security_or_fraud_signal")

        # 2. Repeated Attempts Saturation
        if prior_attempts >= 4:
            score += 35
            reasons.append(f"repeated_failed_attempts ({prior_attempts} prior)")
        elif prior_attempts >= 2:
            score += 20
            reasons.append(f"elevated_attempt_count ({prior_attempts} prior)")

        # 3. Velocity Anomaly
        if unusual_velocity:
            score += 25
            reasons.append("unusual_retry_velocity_detected")

        # 4. Customer Account Restriction
        if customer_restricted:
            score += 35
            reasons.append("customer_account_restricted_or_suspended")

        # 5. Financial Exposure Magnitude
        if amount_minor >= 500_000:  # >= $5,000 / ₹5,000
            score += 20
            reasons.append(f"major_financial_exposure ({amount_minor / 100:,.2f})")
        elif amount_minor >= 100_000:  # >= $1,000 / ₹1,000
            score += 10
            reasons.append(f"high_value_transaction ({amount_minor / 100:,.2f})")

        # 6. Churn Impact
        if is_subscription and failure_category == "expired_card":
            score += 15
            reasons.append("recurring_subscriber_churn_risk")

        # Clamp between 0 and 100
        final_score = min(score, 100)

        # Determine Risk Band & Policy Action Limits
        if final_score >= cls.HIGH_THRESHOLD:
            band = "high"
            action_limit = "block"
        elif final_score >= cls.MEDIUM_THRESHOLD:
            band = "medium"
            action_limit = "human_approval"
        else:
            band = "low"
            action_limit = "automatic"

        if not reasons:
            reasons.append("no_elevated_risk_signals")

        return RiskAssessmentResult(
            score=final_score,
            band=band,
            reasons=reasons,
            action_limit=action_limit,
        )
