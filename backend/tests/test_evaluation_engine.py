"""Phase 8 evaluation engine tests.

Author: Karthikeya
"""

from decimal import Decimal

from app.evaluation.metrics import calculate_metrics, evaluate
from app.evaluation.simulator import BatchEvaluationEngine, build_scenarios


def test_scenario_generation_is_reproducible() -> None:
    """The same seed creates the same ordered scenario batch."""

    first = build_scenarios(seed=7, count=10)
    second = build_scenarios(seed=7, count=10)

    assert first == second
    assert [row.scenario_id for row in first] == [row.scenario_id for row in second]


def test_batch_run_is_reproducible() -> None:
    """The same scenarios produce identical simulation results."""

    scenarios = build_scenarios(seed=42, count=25)
    engine = BatchEvaluationEngine()

    first = engine.run(scenarios, seed=42)
    second = engine.run(scenarios, seed=42)

    assert first == second
    assert first.rule_version == "phase8.v1"


def test_metrics_measure_recovery_and_action_quality() -> None:
    """The report contains revenue, recovery, safety, and quality metrics."""

    run = BatchEvaluationEngine().run(build_scenarios(seed=42, count=25), seed=42)
    metrics = evaluate(run)

    assert metrics.scenario_count == 25
    assert metrics.at_risk_count == 20
    assert metrics.recovered_count > 0
    assert metrics.total_at_risk_revenue_minor > 0
    assert metrics.recovered_revenue_minor > 0
    assert Decimal("0") <= metrics.revenue_recovery_rate <= Decimal("1")
    assert Decimal("0") <= metrics.case_recovery_rate <= Decimal("1")
    assert Decimal("0") <= metrics.action_accuracy <= Decimal("1")
    assert Decimal("0") <= metrics.safety_rate <= Decimal("1")
    assert metrics.failure_count > 0
    assert metrics.escalation_count > 0
    assert metrics.verification_count > 0
    assert metrics.stopped_count > 0


def test_empty_metrics_are_zero_safe() -> None:
    """An empty evaluation result remains reportable without division errors."""

    metrics = calculate_metrics([])

    assert metrics.scenario_count == 0
    assert metrics.revenue_recovery_rate == Decimal("0.0000")
    assert metrics.case_recovery_rate == Decimal("0.0000")
    assert metrics.action_accuracy == Decimal("0.0000")


def test_invalid_batch_size_is_rejected() -> None:
    """Evaluation requests must contain at least one scenario."""

    try:
        build_scenarios(seed=42, count=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("zero-sized evaluation batch was accepted")
