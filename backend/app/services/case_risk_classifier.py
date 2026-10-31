"""Deterministic revenue risk classification engine for RevenueRescueAI.

Author: Karthikeya
Architectural layer: domain service / risk evaluation.

Classifies the financial risk severity (how serious the potential revenue loss is)
independently from operational queue priority (how urgently the team should act).

Evaluation factors:
1. Exposure magnitude (monetary amount at risk in minor units).
2. Failure category / reason (fraud, churn risk, permanent decline vs transient).
3. Event type (e.g., subscription renewal loss has recurring LTV impact).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.enums import CanonicalEventType, FailureCategory, RiskTier


@dataclass(frozen=True)
class RiskClassificationResult:
    """Result of deterministic revenue risk classification."""

    risk_tier: RiskTier
    reason: str
    factors: dict[str, Any]


class CaseRiskClassifier:
    """Classifies case revenue risk into HIGH, MEDIUM, or LOW severity."""

    # Thresholds in minor units (cents / paise)
    HIGH_EXPOSURE_THRESHOLD = 500_000   # >= $5,000 / ₹5,000
    MEDIUM_EXPOSURE_THRESHOLD = 100_000 # >= $1,000 / ₹1,000

    @classmethod
    def classify_risk(
        cls,
        *,
        amount_minor: int,
        currency: str,
        failure_code: str | None,
        event_type: str,
        customer_tier: str | None = None,
    ) -> RiskClassificationResult:
        """Classify revenue risk severity deterministically.

        Risk answers: 'How serious is the potential revenue loss?'
        - HIGH: Severe potential revenue loss or churn risk.
        - MEDIUM: Moderate exposure or actionable failure.
        - LOW: Small exposure or readily recoverable transient failure.
        """
        reasons: list[str] = []
        factors: dict[str, Any] = {
            "amount_minor": amount_minor,
            "currency": currency,
            "failure_code": failure_code,
            "event_type": event_type,
            "customer_tier": customer_tier,
        }

        clean_code = (failure_code or "").strip().lower()
        clean_event = (event_type or "").strip().upper()

        # Score-based classification to avoid brittle multi-branch trees
        # Risk score: >= 70 -> HIGH, >= 40 -> MEDIUM, < 40 -> LOW
        risk_score = 0

        # 1. Financial exposure component (up to 50 points)
        if amount_minor >= cls.HIGH_EXPOSURE_THRESHOLD:
            risk_score += 50
            reasons.append(f"Major financial exposure ({currency} {amount_minor / 100:,.2f})")
            factors["exposure_score"] = 50
        elif amount_minor >= cls.MEDIUM_EXPOSURE_THRESHOLD:
            risk_score += 30
            reasons.append(f"Significant financial exposure ({currency} {amount_minor / 100:,.2f})")
            factors["exposure_score"] = 30
        elif amount_minor >= 25_000:  # >= $250
            risk_score += 15
            reasons.append(f"Moderate financial exposure ({currency} {amount_minor / 100:,.2f})")
            factors["exposure_score"] = 15
        else:
            factors["exposure_score"] = 5

        # 2. Event type / Churn impact component
        if clean_event == CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value:
            risk_score += 25
            reasons.append("Recurring subscription failure risks ongoing customer churn")
            factors["event_type_score"] = 25
        elif clean_event == CanonicalEventType.INVOICE_OVERDUE.value:
            risk_score += 20
            reasons.append("Overdue B2B invoice represents aged accounts receivable risk")
            factors["event_type_score"] = 20
        elif clean_event == CanonicalEventType.CHECKOUT_ABANDONED.value:
            risk_score += 15
            reasons.append("Abandoned checkout may lead to immediate loss of high-intent buyer")
            factors["event_type_score"] = 15
        else:
            factors["event_type_score"] = 10

        # 3. Failure category risk severity
        if clean_code in ("fraud_suspected", "fraudulent", FailureCategory.FRAUD_SUSPECTED.value):
            risk_score += 35
            reasons.append("Suspected fraud represents acute chargeback and loss risk")
            factors["failure_code_score"] = 35
        elif clean_code in ("card_expired", "expired_card", FailureCategory.CARD_EXPIRED.value):
            risk_score += 20
            reasons.append("Expired payment instrument requires customer intervention to avoid churn")
            factors["failure_code_score"] = 20
        elif clean_code in ("do_not_honor", "card_declined", FailureCategory.DO_NOT_HONOR.value):
            risk_score += 15
            reasons.append("Hard issuer decline indicates payment instrument friction")
            factors["failure_code_score"] = 15
        elif clean_code in ("insufficient_funds", FailureCategory.INSUFFICIENT_FUNDS.value):
            risk_score += 10
            reasons.append("Insufficient funds is typically recoverable with optimal retry timing")
            factors["failure_code_score"] = 10
        elif clean_code in ("processing_error", "network_error", "timeout", FailureCategory.PROCESSING_ERROR.value):
            risk_score += 5
            reasons.append("Transient infrastructure glitch has low structural churn risk")
            factors["failure_code_score"] = 5
        else:
            factors["failure_code_score"] = 10

        # 4. Customer tier adjustment if present
        if customer_tier and customer_tier.strip().lower() in ("enterprise", "vip", "tier_1"):
            risk_score += 20
            reasons.append(f"High-value customer segment ({customer_tier}) escalates risk")
            factors["customer_tier_score"] = 20

        # Determine Tier: Fraud suspected or risk score >= 50 qualifies as HIGH risk
        if risk_score >= 50 or clean_code in (
            "fraud_suspected",
            "fraudulent",
            FailureCategory.FRAUD_SUSPECTED.value,
        ):
            tier = RiskTier.HIGH
        elif risk_score >= 25:
            tier = RiskTier.MEDIUM
        else:
            tier = RiskTier.LOW


        factors["calculated_risk_score"] = risk_score
        final_reason = ". ".join(reasons) if reasons else "Standard risk classification."

        return RiskClassificationResult(
            risk_tier=tier,
            reason=final_reason,
            factors=factors,
        )
