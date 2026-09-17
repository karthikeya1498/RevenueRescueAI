"""Database integrity and transaction-boundary tests.
Author: Karthikeya
"""

from app.core.database import Base
from app.models.domain import CaseStateTransition, ProviderWebhookEvent, RecoveryEvidence
from app.repositories.webhook_events import WebhookEventRepository
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_all_new_models_are_registered_in_metadata():
    tables = set(Base.metadata.tables)
    assert "provider_webhook_events" in tables
    assert "recovery_evidence" in tables
    assert "case_state_transitions" in tables
    assert "sequence_number" in {column.name for column in CaseStateTransition.__table__.columns}


def test_webhook_idempotency_is_durable_and_payload_reuse_is_rejected():
    session = make_session()
    repo = WebhookEventRepository(session)
    first = repo.record(
        provider="razorpay",
        event_id="evt-1",
        event_type="payment.failed",
        payload_hash="hash-a",
        signature_verified=True,
        payload_safe={"event": "payment.failed"},
    )
    session.commit()
    duplicate = repo.record(
        provider="razorpay",
        event_id="evt-1",
        event_type="payment.failed",
        payload_hash="hash-a",
        signature_verified=True,
        payload_safe={"event": "payment.failed"},
    )
    reused = repo.record(
        provider="razorpay",
        event_id="evt-1",
        event_type="payment.failed",
        payload_hash="hash-b",
        signature_verified=True,
        payload_safe={"event": "payment.failed"},
    )
    assert first.accepted is True
    assert duplicate.duplicate is True and duplicate.reason == "duplicate_event_suppressed"
    assert reused.duplicate is True and reused.reason == "event_id_reused_with_different_payload"
    assert session.query(ProviderWebhookEvent).count() == 1


def test_sqlite_foreign_key_pragma_is_explicitly_supported():
    session = make_session()
    assert session.scalar(text("PRAGMA foreign_keys")) == 1


def test_evidence_rejects_negative_amount_at_database_boundary():
    session = make_session()
    evidence = RecoveryEvidence(
        intervention_id="i",
        provider_event_id="e",
        failed_transaction_id="f",
        successful_transaction_id="s",
        amount_minor=-1,
        currency="INR",
        verified_at="2026-01-01T00:00:00",
        attribution_window_hours=72,
        attribution_reason="test",
        attributable=False,
        evidence_json={},
    )
    session.add(evidence)
    try:
        session.commit()
    except Exception:
        session.rollback()
    else:
        raise AssertionError("negative evidence amount was accepted")
