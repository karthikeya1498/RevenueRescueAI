"""Tests for the Phase 7 resilient controlled-call executor.

Author: Karthikeya
"""

import time

from app.resilience.executor import ResilientExecutor
from app.resilience.recovery import FailureKind, RecoveryDisposition, ResiliencePolicy


def test_successful_operation_returns_value() -> None:
    """A successful controlled operation returns a value with no failure classification."""

    result = ResilientExecutor().run(lambda: {"provider": "synthetic"}, attempt_number=1)

    assert result.succeeded is True
    assert result.value == {"provider": "synthetic"}
    assert result.classification is None


def test_timeout_becomes_retryable_classification() -> None:
    """A timeout is not treated as a success or silently retried in place."""

    def slow_operation():
        time.sleep(0.05)
        return "late"

    result = ResilientExecutor(ResiliencePolicy(base_delay_seconds=1)).run(
        slow_operation, attempt_number=1, timeout_seconds=0.001
    )

    assert result.succeeded is False
    assert result.classification is not None
    assert result.classification.kind is FailureKind.TIMEOUT
    assert result.classification.disposition is RecoveryDisposition.RETRY


def test_connection_failure_becomes_transient_api_failure() -> None:
    """Connection errors become a scheduled transient API recovery path."""

    result = ResilientExecutor().run(
        lambda: (_ for _ in ()).throw(ConnectionError("network")), attempt_number=1
    )

    assert result.classification is not None
    assert result.classification.kind is FailureKind.TRANSIENT_API
    assert result.classification.retryable is True


def test_value_error_becomes_permanent_api_failure() -> None:
    """Provider validation errors escalate rather than retrying blindly."""

    result = ResilientExecutor().run(
        lambda: (_ for _ in ()).throw(ValueError("invalid request")), attempt_number=1
    )

    assert result.classification is not None
    assert result.classification.kind is FailureKind.PERMANENT_API
    assert result.classification.disposition is RecoveryDisposition.ESCALATE


def test_uncertain_result_requires_verification() -> None:
    """Ambiguous outcomes are preserved and routed to verification."""

    result = ResilientExecutor().uncertain(attempt_number=1)

    assert result.classification is not None
    assert result.classification.kind is FailureKind.UNCERTAIN_OUTCOME
    assert result.classification.disposition is RecoveryDisposition.VERIFY
    assert result.classification.retryable is False
