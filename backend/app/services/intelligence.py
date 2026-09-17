"""Deterministic decision intelligence for bounded revenue recovery.

Author: Karthikeya
This module deliberately contains no provider calls. It produces reproducible,
calibrated-looking estimates from documented features; production training can
replace the estimator behind the same interface without changing policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from math import exp
from typing import Iterable

ACTIONS = ("retry_payment", "send_reminder", "request_operator_review", "stop")


@dataclass(frozen=True)
class FailureClassification:
    category: str
    retryable: bool
    confidence: Decimal
    explanation: str


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    band: str
    reasons: tuple[str, ...]
    action_limit: str


@dataclass(frozen=True)
class ActionEstimate:
    action: str
    probability: Decimal
    amount_minor: int
    recovery_value_minor: int
    cost_minor: int
    expected_value_minor: int
    explanation: tuple[str, ...]


@dataclass(frozen=True)
class DecisionAnalysis:
    classification: FailureClassification
    risk: RiskAssessment
    estimates: tuple[ActionEstimate, ...]
    recommended_action: str
    confidence: Decimal
    rationale: tuple[str, ...]


def _probability(value: float) -> Decimal:
    return Decimal(str(max(0.01, min(0.99, round(value, 4))))).quantize(Decimal("0.0001"))


def classify_failure(code: str | None, message: str | None = None) -> FailureClassification:
    """Map provider-safe failure codes to an explicit recovery disposition."""
    text = f"{code or ''} {message or ''}".lower()
    rules = (
        (
            ("insufficient", "funds", "balance"),
            "insufficient_funds",
            True,
            "Offer an alternate method after a cooling period.",
        ),
        (
            ("timeout", "timed_out", "network"),
            "provider_timeout",
            True,
            "Verify provider state before retrying.",
        ),
        (
            ("authentication", "3ds", "auth"),
            "authentication_required",
            True,
            "Require customer authentication; do not blind retry.",
        ),
        (("expired", "card_expired"), "expired_card", False, "Request an updated payment method."),
        (
            ("fraud", "blocked", "risk"),
            "risk_blocked",
            False,
            "Stop automated recovery and require human review.",
        ),
        (
            ("decline", "do_not_honor", "bank"),
            "bank_decline",
            True,
            "Prefer an alternate payment method over repeated retries.",
        ),
    )
    for needles, category, retryable, explanation in rules:
        if any(needle in text for needle in needles):
            return FailureClassification(category, retryable, Decimal("0.9000"), explanation)
    return FailureClassification(
        "unknown_failure",
        False,
        Decimal("0.5500"),
        "Insufficient evidence; escalate instead of guessing.",
    )


class RecoveryProbabilityModel:
    """Small, inspectable logistic estimator with a versioned feature contract."""

    version = "deterministic-logistic-v1"
    coefficients = {
        "bias": -0.65,
        "low_attempts": 0.42,
        "customer_history": 0.55,
        "alternate_method": 0.35,
        "retryable": 0.30,
        "high_risk_penalty": -1.20,
    }

    def predict(
        self,
        *,
        action: str,
        failure: FailureClassification,
        prior_attempts: int,
        customer_success_rate: float = 0.5,
        alternate_method_available: bool = True,
        risk_score: int = 0,
    ) -> Decimal:
        """Return a bounded probability; no floating result is exposed to callers."""
        x = self.coefficients["bias"]
        x += (
            self.coefficients["low_attempts"]
            if prior_attempts <= 1
            else -0.25 * min(prior_attempts, 4)
        )
        x += self.coefficients["customer_history"] * (customer_success_rate - 0.5)
        x += (
            self.coefficients["alternate_method"]
            if alternate_method_available and action == "send_reminder"
            else 0
        )
        x += (
            self.coefficients["retryable"] if failure.retryable and action == "retry_payment" else 0
        )
        x += self.coefficients["high_risk_penalty"] if risk_score >= 71 else 0
        if action == "request_operator_review":
            x += 0.10
        if action == "stop":
            x -= 0.45
        return _probability(1 / (1 + exp(-x)))


class RiskEngine:
    """Transparent 0-100 risk score with conservative bands."""

    def assess(
        self,
        *,
        failure: FailureClassification,
        amount_minor: int,
        prior_attempts: int,
        unusual_velocity: bool = False,
        customer_restricted: bool = False,
    ) -> RiskAssessment:
        score = 0
        reasons: list[str] = []
        if failure.category == "risk_blocked":
            score += 60
            reasons.append("provider_risk_signal")
        if prior_attempts >= 3:
            score += 25
            reasons.append("repeated_attempts")
        if unusual_velocity:
            score += 25
            reasons.append("unusual_retry_velocity")
        if customer_restricted:
            score += 30
            reasons.append("customer_restricted")
        if amount_minor >= 100_000:
            score += 15
            reasons.append("high_value_transaction")
        score = min(score, 100)
        band = "high" if score >= 71 else "medium" if score >= 31 else "low"
        limit = "block" if band == "high" else "human_approval" if band == "medium" else "automatic"
        return RiskAssessment(score, band, tuple(reasons) or ("no_elevated_risk_signal",), limit)


class ExpectedValueEngine:
    costs_minor = {
        "retry_payment": 2,
        "send_reminder": 15,
        "request_operator_review": 250,
        "stop": 0,
    }

    def rank(
        self,
        *,
        amount_minor: int,
        failure: FailureClassification,
        prior_attempts: int,
        risk: RiskAssessment,
        customer_success_rate: float = 0.5,
        alternate_method_available: bool = True,
    ) -> tuple[ActionEstimate, ...]:
        model = RecoveryProbabilityModel()
        rows: list[ActionEstimate] = []
        for action in ACTIONS:
            probability = model.predict(
                action=action,
                failure=failure,
                prior_attempts=prior_attempts,
                customer_success_rate=customer_success_rate,
                alternate_method_available=alternate_method_available,
                risk_score=risk.score,
            )
            cost = self.costs_minor[action]
            value = int(
                (Decimal(amount_minor) * probability).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
            explanation = [f"probability={probability}", f"cost={cost} minor units"]
            if action == "retry_payment" and not failure.retryable:
                explanation.append("failure is not retryable")
            if risk.band == "high" and action not in {"request_operator_review", "stop"}:
                explanation.append("high-risk action requires policy block")
            rows.append(
                ActionEstimate(
                    action, probability, amount_minor, value, cost, value - cost, tuple(explanation)
                )
            )
        return tuple(sorted(rows, key=lambda row: row.expected_value_minor, reverse=True))


def analyze_recovery(
    *,
    amount_minor: int,
    failure_code: str | None,
    failure_message: str | None,
    prior_attempts: int,
    customer_success_rate: float = 0.5,
    alternate_method_available: bool = True,
    unusual_velocity: bool = False,
    customer_restricted: bool = False,
) -> DecisionAnalysis:
    failure = classify_failure(failure_code, failure_message)
    risk = RiskEngine().assess(
        failure=failure,
        amount_minor=amount_minor,
        prior_attempts=prior_attempts,
        unusual_velocity=unusual_velocity,
        customer_restricted=customer_restricted,
    )
    estimates = ExpectedValueEngine().rank(
        amount_minor=amount_minor,
        failure=failure,
        prior_attempts=prior_attempts,
        risk=risk,
        customer_success_rate=customer_success_rate,
        alternate_method_available=alternate_method_available,
    )
    permitted = [
        row
        for row in estimates
        if not (risk.band == "high" and row.action not in {"request_operator_review", "stop"})
        and not (row.action == "retry_payment" and not failure.retryable)
    ]
    winner = permitted[0] if permitted else next(row for row in estimates if row.action == "stop")
    confidence = min(failure.confidence, max(winner.probability, Decimal("0.5000")))
    rationale = (
        f"{failure.category}: {failure.explanation}",
        f"risk={risk.band} ({risk.score}/100)",
        (
            f"{winner.action} has highest permitted expected value of "
            f"{winner.expected_value_minor} minor units"
        ),
        *winner.explanation,
    )
    return DecisionAnalysis(
        failure,
        risk,
        estimates,
        winner.action,
        confidence.quantize(Decimal("0.0001")),
        tuple(rationale),
    )


def compare_strategies(analyses: Iterable[DecisionAnalysis]) -> dict[str, dict[str, int | str]]:
    """Aggregate expected values for strategy comparison without inventing outcomes."""
    totals: dict[str, int] = {action: 0 for action in ACTIONS}
    counts: dict[str, int] = {action: 0 for action in ACTIONS}
    for analysis in analyses:
        for estimate in analysis.estimates:
            totals[estimate.action] += estimate.expected_value_minor
            counts[estimate.action] += 1
    return {
        action: {
            "total_expected_value_minor": totals[action],
            "scenario_count": counts[action],
            "method": "expected_value_estimate",
        }
        for action in ACTIONS
    }
