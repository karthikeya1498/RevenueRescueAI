"""Persistence and synthetic-fixture tests for Phase 2.

Author: Karthikeya
"""

from app.core.database import Base
from app.core.enums import TransactionStatus
from app.models.domain import Customer, RecoveryCase, Transaction
from app.services.seed_service import build_synthetic_dataset, seed_synthetic_data
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


def make_session():
    """Create a fresh in-memory SQLite session for one test."""

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_fixture_generation_is_deterministic() -> None:
    """The same seed produces stable identifiers and business keys."""

    first = build_synthetic_dataset(seed=7)
    second = build_synthetic_dataset(seed=7)

    assert [item.id for item in first.customers] == [item.id for item in second.customers]
    assert [item.case_key for item in first.cases] == [item.case_key for item in second.cases]
    assert first.transactions[0].amount_minor == 4999


def test_fixture_persists_related_recovery_data() -> None:
    """Synthetic customers, transactions, cases, attempts, decisions, and audits persist together.
    """

    session = make_session()
    dataset = seed_synthetic_data(session, seed=42)
    session.commit()

    assert (
        session.scalar(select(Customer).where(Customer.id == dataset.customers[0].id)) is not None
    )
    assert (
        session.scalar(select(Transaction).where(Transaction.id == dataset.transactions[0].id))
        is not None
    )
    case = session.scalar(select(RecoveryCase).where(RecoveryCase.id == dataset.cases[2].id))
    assert case is not None
    assert len(case.attempts) == 1
    assert len(case.decisions) == 1
    assert len(case.audit_events) == 1


def test_external_transaction_identity_is_unique() -> None:
    """A provider event cannot create two transaction records."""

    session = make_session()
    seed_synthetic_data(session, seed=42)
    session.commit()
    fixture = build_synthetic_dataset(42)
    duplicate = Transaction(
        customer_id=fixture.customers[0].id,
        provider="synthetic",
        external_transaction_id="synthetic_txn_001",
        amount_minor=1,
        currency="INR",
        status=TransactionStatus.FAILED,
        occurred_at=fixture.transactions[0].occurred_at,
    )
    session.add(duplicate)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    else:
        raise AssertionError("duplicate provider transaction was accepted")
