"""Metrics and report aggregation for Phase 8 evaluation runs.

Author: Karthikeya
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from app.evaluation.simulator import EvaluationRun, ScenarioOutcome, SimulationResult


@dataclass(frozen=True)
class EvaluationMetrics:
    """Aggregated metrics for one deterministic evaluation batch."""

    scenario_count: int
    at_risk_count: int
    recovered_count: int
    total_at_risk_revenue_minor: int
    recovered_revenue_minor: int
    revenue_recovery_rate: Decimal
    case_recovery_rate: Decimal
    action_accuracy: Decimal
    safety_rate: Decimal
    failure_count: int
    escalation_count: int
    verification_count: int
    stopped_count: int
    rejected_count: int
    outcome_counts: dict[str, int]


def _rate(numerator: int, denominator: int) -> Decimal:
    """Return a four-decimal rate and avoid division by zero."""

    if denominator == 0:
        return Decimal("0.0000")
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))


def calculate_metrics(results: Iterable[SimulationResult]) -> EvaluationMetrics:
    """Calculate business and action-quality metrics from simulation results."""

    rows = list(results)
    at_risk = [row for row in rows if row.outcome is not ScenarioOutcome.ALREADY_SUCCEEDED]
    recovered = [row for row in at_risk if row.recovered]
    total_revenue = sum(row.amount_minor for row in at_risk)
    recovered_revenue = sum(row.amount_minor for row in recovered)
    failures = [row for row in rows if row.failure_kind is not None]
    escalations = [row for row in rows if row.disposition and row.disposition.value == "escalate"]
    verifications = [row for row in rows if row.disposition and row.disposition.value == "verify"]
    stopped = [row for row in rows if row.disposition and row.disposition.value == "stop"]
    rejected = [row for row in rows if row.policy_decision.outcome.value == "reject"]
    outcome_counts: dict[str, int] = {}
    for row in rows:
        outcome_counts[row.outcome.value] = outcome_counts.get(row.outcome.value, 0) + 1
    return EvaluationMetrics(
        scenario_count=len(rows),
        at_risk_count=len(at_risk),
        recovered_count=len(recovered),
        total_at_risk_revenue_minor=total_revenue,
        recovered_revenue_minor=recovered_revenue,
        revenue_recovery_rate=_rate(recovered_revenue, total_revenue),
        case_recovery_rate=_rate(len(recovered), len(at_risk)),
        action_accuracy=_rate(sum(row.was_action_correct for row in rows), len(rows)),
        safety_rate=_rate(sum(row.was_safe for row in rows), len(rows)),
        failure_count=len(failures),
        escalation_count=len(escalations),
        verification_count=len(verifications),
        stopped_count=len(stopped),
        rejected_count=len(rejected),
        outcome_counts=outcome_counts,
    )


def evaluate(run: EvaluationRun) -> EvaluationMetrics:
    """Calculate metrics for one evaluation run."""

    return calculate_metrics(run.results)
