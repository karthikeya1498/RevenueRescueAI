"""Explanation generation service for recovery recommendations.

Author: Karthikeya
Architectural layer: domain service / explainability.

Synthesizes transparent, evidence-based explanations that describe why a recovery
strategy was selected, citing observable case data and failure diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.intelligence.failure_analyzer import FailureAnalysisResult
from app.services.intelligence.risk_assessor import RiskAssessmentResult
from app.services.intelligence.strategy_catalog import RecoveryStrategy


@dataclass(frozen=True)
class RecommendationExplanation:
    """Structured, evidence-backed explanation package."""

    summary: str
    supporting_evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


class ExplanationService:
    """Generates transparent, audit-ready explanations for operators and customers."""

    @classmethod
    def generate_explanation(
        cls,
        *,
        strategy: RecoveryStrategy,
        failure: FailureAnalysisResult | None = None,
        risk: RiskAssessmentResult | None = None,
        amount_minor: int = 0,
        currency: str = "USD",
        prior_attempts: int = 0,
        model_version: str = "deterministic-logistic-v1",
        failure_result: FailureAnalysisResult | None = None,
        risk_result: RiskAssessmentResult | None = None,
        selected_estimate: Any | None = None,
        case_context: dict[str, Any] | None = None,
    ) -> RecommendationExplanation:
        """Produce factual explanation citing verifiable evidence without hallucination."""
        actual_failure = failure or failure_result
        if actual_failure is None:
            raise ValueError("FailureAnalysisResult is required")
        actual_risk = risk or risk_result
        if actual_risk is None:
            raise ValueError("RiskAssessmentResult is required")

        if case_context:
            amount_minor = case_context.get("amount_minor", amount_minor)
            currency = case_context.get("currency", currency)
            prior_attempts = case_context.get("prior_attempts", prior_attempts)

        failure = actual_failure
        risk = actual_risk

        evidence: list[str] = []
        limitations: list[str] = []

        # 1. Compile Verifiable Evidence
        evidence.append(f"Recorded failure category: {failure.failure_category.upper()}")
        if failure.raw_code:
            evidence.append(f"Gateway decline code: {failure.raw_code}")
        evidence.append(f"Financial exposure: {currency} {amount_minor / 100:,.2f}")
        evidence.append(f"Assessed risk band: {risk.band.upper()} (score: {risk.score}/100)")
        evidence.append(f"Prior recovery attempts: {prior_attempts}")
        for r in risk.reasons:
            evidence.append(f"Risk signal: {r}")

        # 2. Strategy-Specific Summary
        if strategy == RecoveryStrategy.RETRY_LATER:
            summary = (
                f"Recommended automated retry because the failure category ({failure.failure_category}) "
                f"represents a transient issue with elevated recovery probability upon scheduled re-attempt."
            )
        elif strategy == RecoveryStrategy.UPDATE_PAYMENT_METHOD:
            summary = (
                f"Recommended customer payment method update because the recorded failure ({failure.failure_category}) "
                f"indicates that the payment instrument cannot be charged in its current state."
            )
        elif strategy == RecoveryStrategy.CUSTOMER_REMINDER:
            summary = (
                f"Recommended gentle customer reminder to prompt checkout completion or invoice settlement "
                f"for outstanding {currency} {amount_minor / 100:,.2f}."
            )
        elif strategy == RecoveryStrategy.SUPPORT_ESCALATION:
            summary = (
                f"Recommended high-touch concierge support escalation due to elevated exposure ({currency} "
                f"{amount_minor / 100:,.2f}) and repeated transaction friction."
            )
        elif strategy == RecoveryStrategy.MANUAL_REVIEW:
            summary = (
                f"Flagged for manual operator review due to high risk band ({risk.band.upper()}) "
                f"or diagnostic uncertainty ({failure.failure_category})."
            )
        else:  # NO_ACTION
            summary = "Halted automated recovery workflow as case is terminal, restricted, or ineligible."

        # 3. Document Limitations
        limitations.append(
            f"Strategy ranked using expected-value estimation model ({model_version})."
        )
        limitations.append(
            "This recommendation does NOT authorize or execute payments; policy validation is required."
        )

        return RecommendationExplanation(
            summary=summary,
            supporting_evidence=evidence,
            limitations=limitations,
        )
