"""Expected-value strategy selector for revenue recovery intelligence.

Author: Karthikeya
Architectural layer: domain service / strategy selection.

Ranks approved strategies using expected net recovery value:
Expected Value = (Amount * Probability) - Strategy Cost
Filters out policy-violating or invalid strategies, ensuring transparent selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.core.enums import ActionType
from app.services.intelligence.failure_analyzer import FailureAnalysisResult
from app.services.intelligence.model_adapter import RecoveryEstimatorAdapter
from app.services.intelligence.risk_assessor import RiskAssessmentResult
from app.services.intelligence.strategy_catalog import RecoveryStrategy, StrategyCatalog


@dataclass(frozen=True)
class StrategyCandidateEstimate:
    """Estimated value and probability for a specific recovery strategy candidate."""

    strategy: RecoveryStrategy
    action_type: ActionType
    probability: Decimal
    recovery_value_minor: int
    cost_minor: int
    expected_value_minor: int
    permitted: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def gross_recovery_minor(self) -> int:
        """Alias for recovery_value_minor."""
        return self.recovery_value_minor

    @property
    def rejection_reasons(self) -> list[str]:
        """Alias for reasons."""
        return self.reasons


CandidateEstimate = StrategyCandidateEstimate


@dataclass(frozen=True)
class StrategySelectionResult:
    """Outcome of strategy selection."""

    selected_strategy: RecoveryStrategy
    action_type: ActionType
    confidence: Decimal
    expected_value_minor: int
    candidates: list[StrategyCandidateEstimate]
    selection_rationale: list[str]

    @property
    def selected_action(self) -> ActionType:
        """Alias for action_type."""
        return self.action_type

    @property
    def estimates(self) -> list[StrategyCandidateEstimate]:
        """Alias for candidates."""
        return self.candidates


class StrategySelector:
    """Selects the optimal recovery strategy by evaluating expected financial net recovery."""

    def __init__(self, estimator: RecoveryEstimatorAdapter) -> None:
        self.estimator = estimator

    def select_strategy(
        self,
        *,
        amount_minor: int,
        failure: FailureAnalysisResult | None = None,
        risk: RiskAssessmentResult | None = None,
        prior_attempts: int = 0,
        customer_success_rate: float = 0.5,
        alternate_method_available: bool = True,
        is_case_terminal: bool = False,
        failure_result: FailureAnalysisResult | None = None,
        risk_result: RiskAssessmentResult | None = None,
        is_terminal_case: bool = False,
        is_subscription: bool = False,
    ) -> StrategySelectionResult:
        """Evaluate strategy candidates and pick the highest expected-value permitted strategy."""
        actual_failure = failure or failure_result
        if actual_failure is None:
            raise ValueError("FailureAnalysisResult is required")
        actual_risk = risk or risk_result
        if actual_risk is None:
            raise ValueError("RiskAssessmentResult is required")
        failure = actual_failure
        risk = actual_risk
        actual_terminal = is_case_terminal or is_terminal_case

        candidates: list[StrategyCandidateEstimate] = []
        all_specs = StrategyCatalog.all_strategies()

        # Terminal case shortcut
        if actual_terminal:
            spec = StrategyCatalog.get(RecoveryStrategy.NO_ACTION)
            candidate = StrategyCandidateEstimate(
                strategy=RecoveryStrategy.NO_ACTION,
                action_type=ActionType.STOP,
                probability=Decimal("0.0000"),
                recovery_value_minor=0,
                cost_minor=0,
                expected_value_minor=0,
                permitted=True,
                reasons=["Case is already in a terminal state; recovery halted."],
            )
            return StrategySelectionResult(
                selected_strategy=RecoveryStrategy.NO_ACTION,
                action_type=ActionType.STOP,
                confidence=Decimal("1.0000"),
                expected_value_minor=0,
                candidates=[candidate],
                selection_rationale=["Case is terminal. No active recovery strategy permitted."],
            )

        for spec in all_specs:
            reasons: list[str] = []
            permitted = True

            # 1. Estimate conditional recovery probability
            prob = self.estimator.estimate_recovery_probability(
                action_type=spec.action_type,
                failure_category=failure.failure_category,
                is_retryable=failure.retryable,
                amount_minor=amount_minor,
                prior_attempts=prior_attempts,
                customer_success_rate=customer_success_rate,
                alternate_method_available=alternate_method_available,
                risk_score=risk.score,
            )

            # 2. Check Strategy-Specific Preconditions & Policy Guardrails
            if spec.strategy == RecoveryStrategy.RETRY_LATER:
                if not failure.retryable:
                    permitted = False
                    reasons.append("Failure category is not retryable.")
                if risk.band == "high":
                    permitted = False
                    reasons.append("High risk band blocks automated retry.")
                if prior_attempts >= 4:
                    permitted = False
                    reasons.append("Exceeded maximum retry attempt quota.")

            elif spec.strategy == RecoveryStrategy.UPDATE_PAYMENT_METHOD:
                if failure.failure_category not in (
                    "expired_card",
                    "invalid_payment_details",
                    "bank_decline",
                ):
                    reasons.append("Card update not required for transient failure.")
                    # Still permitted, but lower expected utility

            elif spec.strategy == RecoveryStrategy.MANUAL_REVIEW:
                if risk.band == "high" or failure.failure_category in ("fraud_suspected", "unknown_failure"):
                    reasons.append("High risk or fraud signal flags case for manual review.")

            # 3. Calculate Financial Metrics
            # Expected Gross Recovery = Amount * Probability
            recovery_val = int(
                (Decimal(amount_minor) * prob).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            cost = spec.estimated_cost_minor
            expected_net = recovery_val - cost

            reasons.append(f"Estimated recovery probability: {prob * 100:.2f}%")
            reasons.append(f"Estimated intervention cost: {cost} minor units")

            candidates.append(
                StrategyCandidateEstimate(
                    strategy=spec.strategy,
                    action_type=spec.action_type,
                    probability=prob,
                    recovery_value_minor=recovery_val,
                    cost_minor=cost,
                    expected_value_minor=expected_net,
                    permitted=permitted,
                    reasons=reasons,
                )
            )

        # 4. Pick Winner
        # Separate permitted candidates
        permitted_candidates = [c for c in candidates if c.permitted]

        # Prioritize safety: if high risk, route to MANUAL_REVIEW or NO_ACTION
        if risk.band == "high":
            high_risk_candidates = [
                c for c in permitted_candidates
                if c.strategy in (RecoveryStrategy.MANUAL_REVIEW, RecoveryStrategy.NO_ACTION)
            ]
            if high_risk_candidates:
                permitted_candidates = high_risk_candidates

        # Rank by expected value descending
        permitted_candidates.sort(key=lambda c: c.expected_value_minor, reverse=True)

        winner = (
            permitted_candidates[0]
            if permitted_candidates
            else next(c for c in candidates if c.strategy == RecoveryStrategy.NO_ACTION)
        )

        # Confidence is bounded by failure classification certainty and probability
        confidence = min(failure.confidence, max(winner.probability, Decimal("0.5000")))

        rationale: list[str] = [
            f"Selected {winner.strategy.value} with expected net value of {winner.expected_value_minor} minor units.",
            f"Failure category: {failure.failure_category} ({failure.explanation})",
            f"Risk assessment: {risk.band.upper()} (score {risk.score}/100, limit: {risk.action_limit})",
        ]
        rationale.extend(winner.reasons)

        return StrategySelectionResult(
            selected_strategy=winner.strategy,
            action_type=winner.action_type,
            confidence=confidence.quantize(Decimal("0.0001")),
            expected_value_minor=winner.expected_value_minor,
            candidates=candidates,
            selection_rationale=rationale,
        )
