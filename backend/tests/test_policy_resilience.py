"""Phase 6 safety and Phase 7 resilience tests.

Author: Karthikeya
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.core.enums import ActionType, RecoveryAttemptStatus, RecoveryCaseState, TransactionStatus
from app.policy.safety import (
    PolicyContext,
    PolicyOutcome,
    PolicyReason,
    SafetyPolicy,
    count_retry_attempts,
)
from app.resilience.recovery import (
    FailureKind,
    RecoveryDisposition,
    ResiliencePolicy,
)

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


def retry_context(**overrides) -> PolicyContext:
    """Create an actionable payment-retry context."""

    values = {
        "case_state": RecoveryCaseState.RETRY_ELIGIBLE,
        "transaction_status": TransactionStatus.FAILED,
        "action": ActionType.RETRY_PAYMENT,
        "retry_attempt_count": 0,
        "idempotency_key": "case-1-attempt-1",
    }
    values.update(overrides)
    return PolicyContext(**values)


def test_retry_is_allowed_with_budget_and_unique_idempotency_key() -> None:
    """A bounded retry with a new key is allowed."""

    decision = SafetyPolicy().evaluate(retry_context())

    assert decision.outcome is PolicyOutcome.ALLOW
    assert decision.retry_allowed is True
    assert decision.reason is PolicyReason.ALLOWED


def test_retry_limit_escalates_instead_of_retrying() -> None:
    """The policy escalates once the retry budget is exhausted."""

    decision = SafetyPolicy().evaluate(retry_context(retry_attempt_count=2))

    assert decision.outcome is PolicyOutcome.ESCALATE
    assert decision.should_escalate is True
    assert decision.reason is PolicyReason.RETRY_LIMIT_REACHED


def test_terminal_case_stops_any_action() -> None:
    """Recovered, stopped, and closed cases cannot be acted on again."""

    decision = SafetyPolicy().evaluate(retry_context(case_state=RecoveryCaseState.RECOVERED))

    assert decision.outcome is PolicyOutcome.STOP
    assert decision.should_stop is True
    assert decision.reason is PolicyReason.CASE_TERMINAL


def test_succeeded_transaction_is_protected() -> None:
    """A successful transaction always wins over a retry proposal."""

    decision = SafetyPolicy().evaluate(
        retry_context(transaction_status=TransactionStatus.SUCCEEDED)
    )

    assert decision.outcome is PolicyOutcome.STOP
    assert decision.reason is PolicyReason.TRANSACTION_ALREADY_SUCCEEDED


def test_duplicate_idempotency_key_is_rejected() -> None:
    """A previously used idempotency key cannot be replayed."""

    decision = SafetyPolicy().evaluate(
        retry_context(prior_idempotency_keys=frozenset({"case-1-attempt-1"}))
    )

    assert decision.outcome is PolicyOutcome.REJECT
    assert decision.reason is PolicyReason.DUPLICATE_ATTEMPT


def test_uncertain_attempt_escalates_for_verification() -> None:
    """An uncertain provider result prevents an immediate second retry."""

    decision = SafetyPolicy().evaluate(retry_context(has_uncertain_attempt=True))

    assert decision.outcome is PolicyOutcome.ESCALATE
    assert decision.reason is PolicyReason.UNCERTAIN_OUTCOME_REQUIRES_VERIFICATION


def test_retry_count_excludes_cancelled_attempts() -> None:
    """Cancelled plans do not consume a retry budget."""

    assert (
        count_retry_attempts(
            [
                RecoveryAttemptStatus.FAILED,
                RecoveryAttemptStatus.CANCELLED,
                RecoveryAttemptStatus.UNCERTAIN,
            ]
        )
        == 2
    )


def test_timeout_gets_bounded_exponential_retry_schedule() -> None:
    """Timeouts receive deterministic backoff while budget remains."""

    policy = ResiliencePolicy(max_attempts=3, base_delay_seconds=30)
    classification = policy.classify(FailureKind.TIMEOUT, attempt_number=1, now=NOW)

    assert classification.disposition is RecoveryDisposition.RETRY
    assert classification.retryable is True
    assert classification.schedule is not None
    assert classification.schedule.delay_seconds == 30
    assert classification.schedule.next_attempt_at == datetime(
        2026, 3, 1, 12, 0, 30, tzinfo=timezone.utc
    )


def test_transient_api_failure_escalates_after_limit() -> None:
    """Transient failures escalate once no retry budget remains."""

    classification = ResiliencePolicy(max_attempts=2).classify(
        FailureKind.TRANSIENT_API, attempt_number=2, now=NOW
    )

    assert classification.disposition is RecoveryDisposition.ESCALATE
    assert classification.retryable is False


def test_uncertain_outcome_requires_verification_not_retry() -> None:
    """Uncertainty is preserved and routed to verification."""

    classification = ResiliencePolicy().classify(FailureKind.UNCERTAIN_OUTCOME, attempt_number=1)

    assert classification.disposition is RecoveryDisposition.VERIFY
    assert classification.retryable is False


def test_invalid_agent_output_escalates_without_execution() -> None:
    """Malformed agent output is never treated as a provider retry failure."""

    classification = ResiliencePolicy().classify(FailureKind.INVALID_AGENT_OUTPUT, attempt_number=1)

    assert classification.disposition is RecoveryDisposition.ESCALATE
    assert "not executed" in classification.safe_message


def test_resume_envelope_contains_safe_checkpoint() -> None:
    """A restart checkpoint carries correlation and idempotency data only."""

    case_id = uuid4()
    envelope = ResiliencePolicy.create_resume_envelope(
        case_id=case_id,
        attempt_id=None,
        phase="verification_pending",
        idempotency_key="case-1-attempt-1",
        correlation_id="corr-1",
        payload_safe={"provider_status": "unknown"},
        created_at=NOW,
    )

    assert envelope.case_id == case_id
    assert envelope.phase == "verification_pending"
    assert envelope.payload_safe == {"provider_status": "unknown"}
    assert not hasattr(envelope, "credentials")
