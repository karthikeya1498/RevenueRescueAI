"""Tests for deterministic Phase 3 revenue-risk detection.

Author: Karthikeya
"""

from datetime import datetime, timedelta, timezone

from app.core.database import Base
from app.core.enums import RecoveryCaseState, TransactionStatus
from app.models.domain import Transaction
from app.services.risk_detection import (
    DetectorConfig,
    RevenueRiskDetector,
    RiskCaseService,
    RiskReason,
    RiskSeverity,
)
from app.services.seed_service import build_synthetic_dataset
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

NOW = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)


def make_session():
    """Create an isolated in-memory database for detector tests."""

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_failed_payment_is_high_risk() -> None:
    """A failed payment is immediately classified as revenue at risk."""

    fixture = build_synthetic_dataset(42)
    detector = RevenueRiskDetector()

    result = detector.detect(fixture.transactions[0], customer=fixture.customers[0], as_of=NOW)

    assert result.is_at_risk is True
    assert result.severity is RiskSeverity.HIGH
    assert result.reason_codes == (RiskReason.PAYMENT_FAILED,)
    assert result.recommended_case_state is RecoveryCaseState.DETECTED


def test_pending_payment_is_risk_only_after_stale_threshold() -> None:
    """A recent pending payment is not risk, while an old one is medium risk."""

    fixture = build_synthetic_dataset(42)
    transaction = fixture.transactions[2]
    detector = RevenueRiskDetector(DetectorConfig(pending_stale_after=timedelta(hours=24)))

    recent_as_of = transaction.occurred_at + timedelta(hours=12)
    recent = detector.detect(transaction, customer=fixture.customers[2], as_of=recent_as_of)
    stale = detector.detect(
        transaction, customer=fixture.customers[2], as_of=recent_as_of + timedelta(days=2)
    )

    assert recent.is_at_risk is False
    assert stale.is_at_risk is True
    assert stale.severity is RiskSeverity.MEDIUM
    assert stale.reason_codes == (RiskReason.PAYMENT_PENDING_TOO_LONG,)


def test_unknown_payment_is_medium_risk() -> None:
    """An unknown provider status is preserved as a detectable risk."""

    fixture = build_synthetic_dataset(42)
    fixture.transactions[0].status = TransactionStatus.UNKNOWN

    result = RevenueRiskDetector().detect(
        fixture.transactions[0], customer=fixture.customers[0], as_of=NOW
    )

    assert result.is_at_risk is True
    assert result.severity is RiskSeverity.MEDIUM
    assert RiskReason.PAYMENT_STATUS_UNKNOWN in result.reason_codes


def test_succeeded_payment_is_protected_from_recovery_risk() -> None:
    """A succeeded transaction must never create a recovery case."""

    fixture = build_synthetic_dataset(42)
    fixture.transactions[0].status = TransactionStatus.SUCCEEDED

    result = RevenueRiskDetector().detect(
        fixture.transactions[0], customer=fixture.customers[0], as_of=NOW
    )

    assert result.is_at_risk is False
    assert result.severity is RiskSeverity.NONE
    assert result.reason_codes == (RiskReason.TRANSACTION_ALREADY_SUCCEEDED,)


def test_missing_customer_context_is_reported_without_changing_detection() -> None:
    """Missing context is an additional reason, not an AI inference or action."""

    fixture = build_synthetic_dataset(42)
    result = RevenueRiskDetector().detect(fixture.transactions[0], customer=None, as_of=NOW)

    assert result.is_at_risk is True
    assert RiskReason.MISSING_CUSTOMER_CONTEXT in result.reason_codes


def test_batch_detection_preserves_input_order() -> None:
    """Batch detection is deterministic and preserves transaction ordering."""

    fixture = build_synthetic_dataset(42)
    results = RevenueRiskDetector().detect_many(
        fixture.transactions,
        customers_by_id={customer.id: customer for customer in fixture.customers},
        as_of=NOW,
    )

    assert [result.transaction_id for result in results] == [
        transaction.id for transaction in fixture.transactions
    ]


def test_case_creation_is_idempotent_for_duplicate_events() -> None:
    """Repeated delivery of one failed transaction creates one case only."""

    session = make_session()
    fixture = build_synthetic_dataset(42)
    session.add_all(fixture.customers + fixture.transactions)
    session.flush()
    transaction = session.scalar(
        select(Transaction).where(Transaction.id == fixture.transactions[0].id)
    )
    assert transaction is not None

    service = RiskCaseService(session)
    first_result, first_case, first_created = service.detect_and_create_case(transaction, as_of=NOW)
    second_result, second_case, second_created = service.detect_and_create_case(
        transaction, as_of=NOW
    )

    assert first_result.is_at_risk is True
    assert second_result.is_at_risk is True
    assert first_created is True
    assert second_created is False
    assert first_case is second_case
    assert session.query(type(first_case)).count() == 1
