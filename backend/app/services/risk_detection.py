"""Deterministic revenue-risk detection for Phase 3.

Author: Karthikeya
Architectural layer: risk detection service.

This module classifies persisted transaction facts only. It does not call an
LLM, contact customers, invoke payment tools, or choose a recovery action.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utc_now
from app.core.enums import RecoveryCaseState, TransactionStatus
from app.models.domain import Customer, RecoveryCase, Transaction


class RiskReason(StrEnum):
    """Stable rule identifiers used in audit records and evaluation."""

    PAYMENT_FAILED = "payment_failed"
    PAYMENT_PENDING_TOO_LONG = "payment_pending_too_long"
    PAYMENT_STATUS_UNKNOWN = "payment_status_unknown"
    TRANSACTION_ALREADY_SUCCEEDED = "transaction_already_succeeded"
    TRANSACTION_NOT_AT_RISK = "transaction_not_at_risk"
    MISSING_CUSTOMER_CONTEXT = "missing_customer_context"


class RiskSeverity(StrEnum):
    """Deterministic severity assigned to a detected risk."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass(frozen=True)
class RiskDetectionResult:
    """Immutable result of evaluating one transaction."""

    transaction_id: UUID
    is_at_risk: bool
    severity: RiskSeverity
    reason_codes: tuple[RiskReason, ...]
    detected_at: datetime
    rule_version: str
    recommended_case_state: RecoveryCaseState | None = None


@dataclass(frozen=True)
class DetectorConfig:
    """Thresholds and version for deterministic detector behavior."""

    pending_stale_after: timedelta = timedelta(hours=24)
    rule_version: str = "phase3.v1"


class RevenueRiskDetector:
    """Classify transaction risk using explicit, deterministic rules."""

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()

    def detect(
        self,
        transaction: Transaction,
        *,
        customer: Customer | None = None,
        as_of: datetime | None = None,
    ) -> RiskDetectionResult:
        """Evaluate a transaction without mutating persistence state.

        Failed transactions are immediately at risk. Pending or unknown
        transactions become at risk only when their event time is older than
        the configured threshold. Succeeded, refunded, cancelled, authorized,
        and newly-created transactions are not classified as recovery risk.
        """

        evaluated_at = as_of or utc_now()
        if evaluated_at.tzinfo is None:
            evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)

        reasons: list[RiskReason] = []
        severity = RiskSeverity.NONE

        if transaction.status is TransactionStatus.FAILED:
            reasons.append(RiskReason.PAYMENT_FAILED)
            severity = RiskSeverity.HIGH
        elif transaction.status is TransactionStatus.PENDING:
            if self._is_stale(transaction.occurred_at, evaluated_at):
                reasons.append(RiskReason.PAYMENT_PENDING_TOO_LONG)
                severity = RiskSeverity.MEDIUM
        elif transaction.status is TransactionStatus.UNKNOWN:
            reasons.append(RiskReason.PAYMENT_STATUS_UNKNOWN)
            severity = RiskSeverity.MEDIUM
        elif transaction.status is TransactionStatus.SUCCEEDED:
            reasons.append(RiskReason.TRANSACTION_ALREADY_SUCCEEDED)
        else:
            reasons.append(RiskReason.TRANSACTION_NOT_AT_RISK)

        if (
            reasons
            and reasons[0]
            in {
                RiskReason.PAYMENT_FAILED,
                RiskReason.PAYMENT_PENDING_TOO_LONG,
                RiskReason.PAYMENT_STATUS_UNKNOWN,
            }
            and customer is None
        ):
            reasons.append(RiskReason.MISSING_CUSTOMER_CONTEXT)

        at_risk = any(
            reason
            in {
                RiskReason.PAYMENT_FAILED,
                RiskReason.PAYMENT_PENDING_TOO_LONG,
                RiskReason.PAYMENT_STATUS_UNKNOWN,
            }
            for reason in reasons
        )
        return RiskDetectionResult(
            transaction_id=transaction.id,
            is_at_risk=at_risk,
            severity=severity,
            reason_codes=tuple(reasons),
            detected_at=evaluated_at,
            rule_version=self.config.rule_version,
            recommended_case_state=RecoveryCaseState.DETECTED if at_risk else None,
        )

    def _is_stale(self, occurred_at: datetime, as_of: datetime) -> bool:
        """Return whether a pending transaction exceeds the stale threshold."""

        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        return occurred_at <= as_of - self.config.pending_stale_after

    def detect_many(
        self,
        transactions: Iterable[Transaction],
        *,
        customers_by_id: dict[UUID, Customer] | None = None,
        as_of: datetime | None = None,
    ) -> list[RiskDetectionResult]:
        """Evaluate transactions in input order for deterministic batch results."""

        customers_by_id = customers_by_id or {}
        return [
            self.detect(
                transaction, customer=customers_by_id.get(transaction.customer_id), as_of=as_of
            )
            for transaction in transactions
        ]


class RiskCaseService:
    """Persist detected risks as idempotent recovery cases."""

    def __init__(self, session: Session, detector: RevenueRiskDetector | None = None) -> None:
        self.session = session
        self.detector = detector or RevenueRiskDetector()

    def detect_and_create_case(
        self,
        transaction: Transaction,
        *,
        as_of: datetime | None = None,
    ) -> tuple[RiskDetectionResult, RecoveryCase | None, bool]:
        """Detect one transaction and create at most one case for its risk event.

        Returns ``(result, case, created)``. Existing cases are returned with
        ``created=False`` so duplicate event delivery is safe and observable.
        """

        customer = self.session.get(Customer, transaction.customer_id)
        result = self.detector.detect(transaction, customer=customer, as_of=as_of)
        if not result.is_at_risk:
            return result, None, False

        case_key = self.case_key(transaction)
        existing = self.session.scalar(
            select(RecoveryCase).where(RecoveryCase.case_key == case_key)
        )
        if existing is not None:
            return result, existing, False

        detected_at = result.detected_at
        case = RecoveryCase(
            customer_id=transaction.customer_id,
            trigger_transaction_id=transaction.id,
            case_key=case_key,
            state=RecoveryCaseState.DETECTED,
            priority=self._priority(result.severity),
            opened_at=detected_at,
            last_state_changed_at=detected_at,
            version=1,
            metadata_json={
                "detector_rule_version": result.rule_version,
                "risk_severity": result.severity.value,
                "reason_codes": [reason.value for reason in result.reason_codes],
                "source": "deterministic_phase3_detector",
            },
        )
        self.session.add(case)
        self.session.flush()
        return result, case, True

    @staticmethod
    def case_key(transaction: Transaction) -> str:
        """Build the stable business key used for duplicate event protection."""

        return (
            f"{transaction.provider}:transaction:{transaction.external_transaction_id}:revenue-risk"
        )

    @staticmethod
    def _priority(severity: RiskSeverity) -> int:
        """Map severity to a deterministic queue priority."""

        return {
            RiskSeverity.HIGH: 100,
            RiskSeverity.MEDIUM: 70,
            RiskSeverity.LOW: 40,
            RiskSeverity.NONE: 0,
        }[severity]
