"""Machine-readable and human-readable evaluation reporting for Phase 8.

Author: Karthikeya
"""

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from app.evaluation.metrics import EvaluationMetrics, evaluate
from app.evaluation.simulator import BatchEvaluationEngine, build_scenarios


def _json_default(value):
    """Serialize Decimal values and enums for JSON reports."""

    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    raise TypeError(f"unsupported report value: {type(value)!r}")


def metrics_to_dict(metrics: EvaluationMetrics) -> dict:
    """Return a stable JSON-compatible metric dictionary."""

    return asdict(metrics)


def run_report(*, seed: int = 42, count: int = 100) -> dict:
    """Run a deterministic batch and return its complete report."""

    scenarios = build_scenarios(seed=seed, count=count)
    run = BatchEvaluationEngine().run(scenarios, seed=seed)
    metrics = evaluate(run)
    return {
        "seed": seed,
        "rule_version": run.rule_version,
        "metrics": metrics_to_dict(metrics),
        "results": [
            {
                "scenario_id": result.scenario_id,
                "amount_minor": result.amount_minor,
                "currency": result.currency,
                "outcome": result.outcome,
                "proposed_action": result.proposed_action,
                "expected_action": result.expected_action,
                "policy_outcome": result.policy_decision.outcome,
                "policy_reason": result.policy_decision.reason,
                "provider_result": result.provider_result,
                "recovered": result.recovered,
                "failure_kind": result.failure_kind,
                "disposition": result.disposition,
                "was_action_correct": result.was_action_correct,
                "was_safe": result.was_safe,
            }
            for result in run.results
        ],
    }


def write_json_report(path: str | Path, *, seed: int = 42, count: int = 100) -> Path:
    """Write a reproducible JSON evaluation report."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(run_report(seed=seed, count=count), default=_json_default, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
