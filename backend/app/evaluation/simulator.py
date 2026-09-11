"""Deterministic batch simulation engine for Phase 8.

Author: Karthikeya
Architectural layer: evaluation engine.

The simulator uses synthetic scenarios only. It never calls payment providers,
customer channels, or an external model. Every outcome is controlled by the
scenario specification so evaluation runs are reproducible.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable
from uuid import UUID, uuid5

from app.core.enums import ActionType, RecoveryCaseState, TransactionStatus
from app.policy.safety import PolicyContext, PolicyDecision, SafetyPolicy
from app.resilience.recovery import FailureKind, RecoveryDisposition, ResiliencePolicy

_EVAL_NAMESPACE = UUID("0b11f2bf-95a3-5d0b-b9a8-2c86e8c3a5dc")


class ScenarioOutcome(StrEnum):
    """Ground-truth outcome used only by the synthetic evaluation harness."""

    RECOVERABLE = "recoverable"
    PERMANENT_FAILURE = "permanent_failure"
    UNCERTAIN = "uncertain"
    ALREADY_SUCCEEDED = "already_succeeded"


class SimulatedProviderResult(StrEnum):
    """Provider-like result returned by the synthetic simulator."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvaluationScenario:
    """One deterministic synthetic case with ground truth and proposed action."""

    scenario_id: str
    amount_minor: int
    currency: str
    outcome: ScenarioOutcome
    proposed_action: ActionType
    prior_attempt_count: int = 0
    provider_result: SimulatedProviderResult = SimulatedProviderResult.SUCCEEDED
    expected_action: ActionType = ActionType.RETRY_PAYMENT
    allowed_actions: frozenset[ActionType] = frozenset(
        {ActionType.RETRY_PAYMENT, ActionType.REQUEST_OPERATOR_REVIEW, ActionType.STOP}
    )
    has_uncertain_attempt: bool = False
    duplicate_idempotency: bool = False


@dataclass(frozen=True)
class SimulationResult:
    """Auditable result for one simulated scenario."""

    scenario_id: str
    amount_minor: int
    currency: str
    outcome: ScenarioOutcome
    proposed_action: ActionType
    expected_action: ActionType
    policy_decision: PolicyDecision
    provider_result: SimulatedProviderResult | None
    recovered: bool
    failure_kind: FailureKind | None
    disposition: RecoveryDisposition | None
    was_action_correct: bool
    was_safe: bool


@dataclass(frozen=True)
class EvaluationRun:
    """Immutable batch evaluation output."""

    seed: int
    rule_version: str
    results: tuple[SimulationResult, ...]


def scenario_uuid(seed: int, scenario_id: str) -> UUID:
    """Return a stable identifier for an evaluation scenario."""

    return uuid5(_EVAL_NAMESPACE, f"{seed}:{scenario_id}")


def build_scenarios(seed: int = 42, count: int = 20) -> list[EvaluationScenario]:
    """Build a deterministic, balanced synthetic evaluation batch."""

    if count < 1:
        raise ValueError("count must be positive")
    templates = [
        (
            ScenarioOutcome.RECOVERABLE,
            ActionType.RETRY_PAYMENT,
            SimulatedProviderResult.SUCCEEDED,
            ActionType.RETRY_PAYMENT,
        ),
        (
            ScenarioOutcome.RECOVERABLE,
            ActionType.REQUEST_OPERATOR_REVIEW,
            SimulatedProviderResult.SUCCEEDED,
            ActionType.RETRY_PAYMENT,
        ),
        (
            ScenarioOutcome.PERMANENT_FAILURE,
            ActionType.RETRY_PAYMENT,
            SimulatedProviderResult.FAILED,
            ActionType.REQUEST_OPERATOR_REVIEW,
        ),
        (
            ScenarioOutcome.UNCERTAIN,
            ActionType.RETRY_PAYMENT,
            SimulatedProviderResult.UNKNOWN,
            ActionType.REQUEST_OPERATOR_REVIEW,
        ),
        (
            ScenarioOutcome.ALREADY_SUCCEEDED,
            ActionType.RETRY_PAYMENT,
            SimulatedProviderResult.SUCCEEDED,
            ActionType.STOP,
        ),
    ]
    scenarios: list[EvaluationScenario] = []
    for index in range(count):
        outcome, proposed, provider_result, expected = templates[(index + seed) % len(templates)]
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"eval-{seed:04d}-{index:04d}",
                amount_minor=1000 + ((index * 137 + seed * 17) % 9000),
                currency="INR",
                outcome=outcome,
                proposed_action=proposed,
                provider_result=provider_result,
                expected_action=expected,
                prior_attempt_count=0,
                has_uncertain_attempt=False,
                duplicate_idempotency=index % 11 == 0,
            )
        )
    return scenarios


class BatchEvaluationEngine:
    """Run deterministic policy-and-outcome simulations."""

    def __init__(
        self,
        *,
        policy: SafetyPolicy | None = None,
        resilience: ResiliencePolicy | None = None,
        rule_version: str = "phase8.v1",
    ) -> None:
        self.policy = policy or SafetyPolicy()
        self.resilience = resilience or ResiliencePolicy()
        self.rule_version = rule_version

    def run(self, scenarios: Iterable[EvaluationScenario], *, seed: int = 42) -> EvaluationRun:
        """Simulate scenarios in input order without side effects."""

        results = tuple(self._run_one(scenario) for scenario in scenarios)
        return EvaluationRun(seed=seed, rule_version=self.rule_version, results=results)

    def _run_one(self, scenario: EvaluationScenario) -> SimulationResult:
        idempotency_key = f"{scenario.scenario_id}:attempt:1"
        policy_decision = self.policy.evaluate(
            PolicyContext(
                case_state=RecoveryCaseState.RETRY_ELIGIBLE,
                transaction_status=TransactionStatus.FAILED,
                action=scenario.proposed_action,
                retry_attempt_count=scenario.prior_attempt_count,
                prior_idempotency_keys=frozenset({idempotency_key})
                if scenario.duplicate_idempotency
                else frozenset(),
                idempotency_key=idempotency_key,
                has_uncertain_attempt=scenario.has_uncertain_attempt,
            )
        )
        failure_kind: FailureKind | None = None
        disposition: RecoveryDisposition | None = None
        provider_result: SimulatedProviderResult | None = None
        recovered = False
        if policy_decision.outcome.value == "allow":
            provider_result = scenario.provider_result
            if (
                provider_result is SimulatedProviderResult.SUCCEEDED
                and scenario.outcome is ScenarioOutcome.RECOVERABLE
            ):
                recovered = True
            elif provider_result is SimulatedProviderResult.TIMEOUT:
                failure_kind = FailureKind.TIMEOUT
                classification = self.resilience.classify(failure_kind, attempt_number=1)
                disposition = classification.disposition
            elif provider_result is SimulatedProviderResult.FAILED:
                failure_kind = FailureKind.PERMANENT_API
                classification = self.resilience.classify(failure_kind, attempt_number=2)
                disposition = classification.disposition
            elif provider_result is SimulatedProviderResult.UNKNOWN:
                failure_kind = FailureKind.UNCERTAIN_OUTCOME
                classification = self.resilience.classify(failure_kind, attempt_number=1)
                disposition = classification.disposition
        else:
            disposition = {
                "stop": RecoveryDisposition.STOP,
                "escalate": RecoveryDisposition.ESCALATE,
                "reject": RecoveryDisposition.STOP,
            }.get(policy_decision.outcome.value)
        return SimulationResult(
            scenario_id=scenario.scenario_id,
            amount_minor=scenario.amount_minor,
            currency=scenario.currency,
            outcome=scenario.outcome,
            proposed_action=scenario.proposed_action,
            expected_action=scenario.expected_action,
            policy_decision=policy_decision,
            provider_result=provider_result,
            recovered=recovered,
            failure_kind=failure_kind,
            disposition=disposition,
            was_action_correct=scenario.proposed_action is scenario.expected_action,
            was_safe=policy_decision.outcome.value in {"allow", "stop", "escalate", "reject"},
        )
