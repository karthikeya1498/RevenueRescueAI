"""Counterfactual baseline strategies for honest evaluation comparisons.
Author: Karthikeya

Baselines use the same synthetic ground truth as the main simulator. They are
not production claims and are labeled counterfactual in every result.
"""

from dataclasses import dataclass
from typing import Iterable

from app.core.enums import ActionType
from app.evaluation.simulator import EvaluationScenario, ScenarioOutcome


@dataclass(frozen=True)
class BaselineMetric:
    strategy: str
    scenario_count: int
    recovered_count: int
    recovered_revenue_minor: int
    recovery_rate: float
    methodology: str


def _would_recover(scenario: EvaluationScenario, action: ActionType) -> bool:
    return scenario.outcome is ScenarioOutcome.RECOVERABLE and scenario.expected_action is action


def compare_baselines(scenarios: Iterable[EvaluationScenario]) -> tuple[BaselineMetric, ...]:
    """Compare no-op, always-retry, rule, and expected-action counterfactuals."""
    rows = list(scenarios)
    at_risk = [row for row in rows if row.outcome is not ScenarioOutcome.ALREADY_SUCCEEDED]
    strategies = {
        "do_nothing": lambda row: ActionType.STOP,
        "always_retry": lambda row: ActionType.RETRY_PAYMENT,
        "rule_based": lambda row: (
            ActionType.SEND_REMINDER if row.prior_attempt_count else ActionType.RETRY_PAYMENT
        ),
        "oracle_upper_bound": lambda row: row.expected_action,
    }
    metrics = []
    for name, selector in strategies.items():
        recovered = [row for row in at_risk if _would_recover(row, selector(row))]
        revenue = sum(row.amount_minor for row in recovered)
        metrics.append(
            BaselineMetric(
                name,
                len(rows),
                len(recovered),
                revenue,
                round(len(recovered) / len(at_risk), 4) if at_risk else 0.0,
                "synthetic counterfactual using scenario ground truth",
            )
        )
    return tuple(metrics)
