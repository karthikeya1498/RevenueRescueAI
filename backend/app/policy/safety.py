"""Deterministic safety and policy enforcement for Phases 6 and 7.

Author: Karthikeya
Architectural layer: policy boundary.

This module decides whether a proposed action is permissible. It does not
execute tools, call providers, or rely on model confidence.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from app.core.enums import ActionType, RecoveryAttemptStatus, RecoveryCaseState, TransactionStatus


class PolicyOutcome(StrEnum):
    ALLOW = "allow"
    REJECT = "reject"
    STOP = "stop"
    ESCALATE = "escalate"


class PolicyReason(StrEnum):
    ALLOWED = "allowed"
    CASE_TERMINAL = "case_terminal"
    TRANSACTION_ALREADY_SUCCEEDED = "transaction_already_succeeded"
    RETRY_LIMIT_REACHED = "retry_limit_reached"
    DUPLICATE_ATTEMPT = "duplicate_attempt"
    ACTION_NOT_PERMITTED = "action_not_permitted"
    UNCERTAIN_OUTCOME_REQUIRES_VERIFICATION = "uncertain_outcome_requires_verification"
    MISSING_IDEMPOTENCY_KEY = "missing_idempotency_key"
    CASE_STATE_NOT_ACTIONABLE = "case_state_not_actionable"


@dataclass(frozen=True)
class PolicyConfig:
    """Explicit safety limits for one policy version."""

    max_retry_attempts: int = 2
    allowed_actions: frozenset[ActionType] = frozenset(
        {
            ActionType.RETRY_PAYMENT,
            ActionType.SEND_REMINDER,
            ActionType.REQUEST_OPERATOR_REVIEW,
            ActionType.STOP,
        }
    )
    policy_version: str = "phase6.v1"


@dataclass(frozen=True)
class PolicyContext:
    """Facts required to validate one proposed action."""

    case_state: RecoveryCaseState
    transaction_status: TransactionStatus
    action: ActionType
    retry_attempt_count: int
    prior_idempotency_keys: frozenset[str] = frozenset()
    idempotency_key: str | None = None
    has_uncertain_attempt: bool = False


@dataclass(frozen=True)
class PolicyDecision:
    """Auditable result of deterministic policy evaluation."""

    outcome: PolicyOutcome
    reason: PolicyReason
    policy_version: str
    retry_allowed: bool = False
    should_stop: bool = False
    should_escalate: bool = False


_TERMINAL_STATES = frozenset(
    {RecoveryCaseState.RECOVERED, RecoveryCaseState.STOPPED, RecoveryCaseState.CLOSED}
)
_ACTIONABLE_STATES = frozenset(
    {RecoveryCaseState.AWAITING_DECISION, RecoveryCaseState.RETRY_ELIGIBLE}
)


class SafetyPolicy:
    """Evaluate actions against deterministic safety invariants."""

    def __init__(self, config: PolicyConfig | None = None) -> None:
        self.config = config or PolicyConfig()

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """Return a fail-closed decision for the proposed action."""

        if context.case_state in _TERMINAL_STATES:
            return self._stop(PolicyReason.CASE_TERMINAL)
        if context.transaction_status is TransactionStatus.SUCCEEDED:
            return self._stop(PolicyReason.TRANSACTION_ALREADY_SUCCEEDED)
        if context.action not in self.config.allowed_actions:
            return self._reject(PolicyReason.ACTION_NOT_PERMITTED)
        if (
            context.action is ActionType.RETRY_PAYMENT
            and context.case_state not in _ACTIONABLE_STATES
        ):
            return self._reject(PolicyReason.CASE_STATE_NOT_ACTIONABLE)
        if (
            context.action is ActionType.RETRY_PAYMENT
            and context.retry_attempt_count >= self.config.max_retry_attempts
        ):
            return PolicyDecision(
                outcome=PolicyOutcome.ESCALATE,
                reason=PolicyReason.RETRY_LIMIT_REACHED,
                policy_version=self.config.policy_version,
                should_escalate=True,
            )
        if context.action is ActionType.RETRY_PAYMENT and context.has_uncertain_attempt:
            return PolicyDecision(
                outcome=PolicyOutcome.ESCALATE,
                reason=PolicyReason.UNCERTAIN_OUTCOME_REQUIRES_VERIFICATION,
                policy_version=self.config.policy_version,
                should_escalate=True,
            )
        if context.action is ActionType.RETRY_PAYMENT and not context.idempotency_key:
            return self._reject(PolicyReason.MISSING_IDEMPOTENCY_KEY)
        if context.idempotency_key and context.idempotency_key in context.prior_idempotency_keys:
            return self._reject(PolicyReason.DUPLICATE_ATTEMPT)
        return PolicyDecision(
            outcome=PolicyOutcome.ALLOW,
            reason=PolicyReason.ALLOWED,
            policy_version=self.config.policy_version,
            retry_allowed=context.action is ActionType.RETRY_PAYMENT,
        )

    def _reject(self, reason: PolicyReason) -> PolicyDecision:
        return PolicyDecision(
            outcome=PolicyOutcome.REJECT,
            reason=reason,
            policy_version=self.config.policy_version,
        )

    def _stop(self, reason: PolicyReason) -> PolicyDecision:
        return PolicyDecision(
            outcome=PolicyOutcome.STOP,
            reason=reason,
            policy_version=self.config.policy_version,
            should_stop=True,
        )


def count_retry_attempts(statuses: Iterable[RecoveryAttemptStatus]) -> int:
    """Count attempts that consumed a payment-retry budget."""

    return sum(status is not RecoveryAttemptStatus.CANCELLED for status in statuses)
