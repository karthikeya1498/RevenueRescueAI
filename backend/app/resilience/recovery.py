"""Failure recovery and resilience contracts for Phase 7.

Author: Karthikeya
Architectural layer: resilience boundary.

The module preserves uncertainty instead of guessing. It produces resumable
plans and safe classifications; it does not retry a provider call itself.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID, uuid4


class FailureKind(StrEnum):
    TIMEOUT = "timeout"
    TRANSIENT_API = "transient_api"
    PERMANENT_API = "permanent_api"
    INVALID_AGENT_OUTPUT = "invalid_agent_output"
    UNCERTAIN_OUTCOME = "uncertain_outcome"
    DUPLICATE_REQUEST = "duplicate_request"
    UNKNOWN = "unknown"


class RecoveryDisposition(StrEnum):
    RETRY = "retry"
    VERIFY = "verify"
    ESCALATE = "escalate"
    STOP = "stop"


@dataclass(frozen=True)
class RetrySchedule:
    """A deterministic retry schedule with bounded exponential backoff."""

    attempt_number: int
    next_attempt_at: datetime
    delay_seconds: int
    max_attempts: int


@dataclass(frozen=True)
class FailureClassification:
    """Safe failure classification and next disposition."""

    kind: FailureKind
    disposition: RecoveryDisposition
    safe_message: str
    retryable: bool
    schedule: RetrySchedule | None = None


@dataclass(frozen=True)
class ResumeEnvelope:
    """Minimal durable checkpoint required to resume after process restart."""

    envelope_id: UUID
    case_id: UUID
    attempt_id: UUID | None
    phase: str
    idempotency_key: str
    correlation_id: str
    created_at: datetime
    payload_safe: dict[str, str]


class ResiliencePolicy:
    """Classify failures and build deterministic retry/resume plans."""

    def __init__(
        self,
        *,
        max_attempts: int = 2,
        base_delay_seconds: int = 30,
        max_delay_seconds: int = 3600,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds

    def classify(
        self,
        kind: FailureKind,
        *,
        attempt_number: int,
        now: datetime | None = None,
    ) -> FailureClassification:
        """Classify one failure without losing uncertain provider outcomes."""

        evaluated_at = now or datetime.now(timezone.utc)
        if evaluated_at.tzinfo is None:
            evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)
        if kind is FailureKind.UNCERTAIN_OUTCOME:
            return FailureClassification(
                kind=kind,
                disposition=RecoveryDisposition.VERIFY,
                safe_message=(
                    "Provider outcome is uncertain; verification is required before another action."
                ),
                retryable=False,
            )
        if kind is FailureKind.INVALID_AGENT_OUTPUT:
            return FailureClassification(
                kind=kind,
                disposition=RecoveryDisposition.ESCALATE,
                safe_message="Agent output failed validation and was not executed.",
                retryable=False,
            )
        if kind is FailureKind.PERMANENT_API:
            return FailureClassification(
                kind=kind,
                disposition=RecoveryDisposition.ESCALATE,
                safe_message="Provider rejected the request permanently.",
                retryable=False,
            )
        if kind is FailureKind.DUPLICATE_REQUEST:
            return FailureClassification(
                kind=kind,
                disposition=RecoveryDisposition.STOP,
                safe_message="Duplicate request was suppressed by idempotency protection.",
                retryable=False,
            )
        if attempt_number >= self.max_attempts:
            return FailureClassification(
                kind=kind,
                disposition=RecoveryDisposition.ESCALATE,
                safe_message="Retry limit reached; operator review is required.",
                retryable=False,
            )
        if kind in {FailureKind.TIMEOUT, FailureKind.TRANSIENT_API, FailureKind.UNKNOWN}:
            delay = min(
                self.base_delay_seconds * (2 ** max(attempt_number - 1, 0)), self.max_delay_seconds
            )
            schedule = RetrySchedule(
                attempt_number=attempt_number + 1,
                next_attempt_at=evaluated_at + timedelta(seconds=delay),
                delay_seconds=delay,
                max_attempts=self.max_attempts,
            )
            return FailureClassification(
                kind=kind,
                disposition=RecoveryDisposition.RETRY,
                safe_message="Transient failure recorded; retry may be scheduled.",
                retryable=True,
                schedule=schedule,
            )
        return FailureClassification(
            kind=kind,
            disposition=RecoveryDisposition.ESCALATE,
            safe_message="Failure requires operator review.",
            retryable=False,
        )

    @staticmethod
    def create_resume_envelope(
        *,
        case_id: UUID,
        attempt_id: UUID | None,
        phase: str,
        idempotency_key: str,
        correlation_id: str,
        payload_safe: dict[str, str] | None = None,
        created_at: datetime | None = None,
    ) -> ResumeEnvelope:
        """Create a safe checkpoint containing no credentials or raw provider data."""

        return ResumeEnvelope(
            envelope_id=uuid4(),
            case_id=case_id,
            attempt_id=attempt_id,
            phase=phase,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            created_at=created_at or datetime.now(timezone.utc),
            payload_safe=payload_safe or {},
        )
