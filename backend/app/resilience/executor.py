"""Resilient execution wrapper for controlled tools.

Author: Karthikeya
Architectural layer: resilience boundary.

The wrapper executes one already-authorized callable, applies a timeout, and
returns a classification. It never repeats a side-effecting call internally.
A caller may schedule a new attempt only after policy and idempotency checks.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Callable, TypeVar

from app.resilience.recovery import (
    FailureClassification,
    FailureKind,
    ResiliencePolicy,
)

T = TypeVar("T")


@dataclass(frozen=True)
class ExecutionResult:
    """Safe result envelope for one controlled call."""

    value: T | None
    classification: FailureClassification | None

    @property
    def succeeded(self) -> bool:
        """Return true only when the callable completed without classification."""

        return self.classification is None


class ResilientExecutor:
    """Apply timeout and failure classification to one authorized callable."""

    def __init__(self, policy: ResiliencePolicy | None = None) -> None:
        self.policy = policy or ResiliencePolicy()

    def run(
        self,
        operation: Callable[[], T],
        *,
        attempt_number: int,
        timeout_seconds: float = 5.0,
    ) -> ExecutionResult:
        """Run once and fail safely on timeout or classified exceptions."""

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(operation)
                return ExecutionResult(
                    value=future.result(timeout=timeout_seconds),
                    classification=None,
                )
        except FutureTimeoutError:
            return ExecutionResult(
                value=None,
                classification=self.policy.classify(
                    FailureKind.TIMEOUT, attempt_number=attempt_number
                ),
            )
        except (TimeoutError, ConnectionError):
            return ExecutionResult(
                value=None,
                classification=self.policy.classify(
                    FailureKind.TRANSIENT_API, attempt_number=attempt_number
                ),
            )
        except ValueError:
            return ExecutionResult(
                value=None,
                classification=self.policy.classify(
                    FailureKind.PERMANENT_API, attempt_number=attempt_number
                ),
            )
        except Exception:
            return ExecutionResult(
                value=None,
                classification=self.policy.classify(
                    FailureKind.UNKNOWN, attempt_number=attempt_number
                ),
            )

    def uncertain(self, *, attempt_number: int) -> ExecutionResult[None]:
        """Represent an ambiguous provider outcome without guessing success."""

        return ExecutionResult(
            value=None,
            classification=self.policy.classify(
                FailureKind.UNCERTAIN_OUTCOME, attempt_number=attempt_number
            ),
        )
