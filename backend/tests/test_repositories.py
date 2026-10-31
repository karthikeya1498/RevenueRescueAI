"""Unit tests for relational domain repositories and data integrity constraints.

Author: Karthikeya
Architectural layer: test suite.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import (
    ActionType,
    ActorType,
    CustomerStatus,
    DecisionValidationStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.models.domain import (
    Customer,
    RecoveryAttempt,
    RecoveryCase,
    RecoveryEvidence,
    Transaction,
)
from app.repositories import (
    AgentDecisionRepository,
    AuditEventRepository,
    CustomerRepository,
    RecoveryAttemptRepository,
    RecoveryCaseRepository,
    RecoveryEvidenceRepository,
    TransactionRepository,
)


@pytest.fixture
def db_session():
    """Create an isolated, in-memory SQLite database session enforcing foreign keys."""
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_customer_repository_crud_and_query(db_session):
    """Customer repository persists and queries customers correctly."""
    repo = CustomerRepository(db_session)
    cust = Customer(
        id=uuid4(),
        provider="stripe",
        external_customer_id="cus_repo_test_1",
        email="test@example.com",
        display_name="Acme Corp",
        status=CustomerStatus.ACTIVE,
        metadata_json={},
    )
    repo.save(cust)
    db_session.commit()

    found_by_id = repo.find_by_id(cust.id)
    assert found_by_id is not None
    assert found_by_id.email == "test@example.com"

    found_by_ext = repo.find_by_external_id("stripe", "cus_repo_test_1")
    assert found_by_ext is not None
    assert found_by_ext.id == cust.id

    customers = repo.list_customers(status=CustomerStatus.ACTIVE)
    assert len(customers) == 1


def test_transaction_repository_and_foreign_key_protection(db_session):
    """Transactions require valid customer and enforce non-negative amount constraint."""
    cust_repo = CustomerRepository(db_session)
    tx_repo = TransactionRepository(db_session)

    cust = Customer(
        id=uuid4(),
        provider="stripe",
        external_customer_id="cus_tx_test",
        status=CustomerStatus.ACTIVE,
    )
    cust_repo.save(cust)
    db_session.commit()

    tx = Transaction(
        id=uuid4(),
        customer_id=cust.id,
        provider="stripe",
        external_transaction_id="ch_tx_001",
        amount_minor=5000,
        currency="USD",
        status=TransactionStatus.FAILED,
        failure_code="insufficient_funds",
        occurred_at=datetime.now(timezone.utc),
    )
    tx_repo.save(tx)
    db_session.commit()

    found_tx = tx_repo.find_by_external_id("stripe", "ch_tx_001")
    assert found_tx is not None
    assert found_tx.amount_minor == 5000

    # Test foreign key enforcement (invalid customer_id)
    invalid_tx = Transaction(
        id=uuid4(),
        customer_id=uuid4(),  # Non-existent customer
        provider="stripe",
        external_transaction_id="ch_tx_invalid",
        amount_minor=1000,
        currency="USD",
        status=TransactionStatus.FAILED,
        occurred_at=datetime.now(timezone.utc),
    )
    tx_repo.save(invalid_tx)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_recovery_case_repository_and_counting(db_session):
    """Recovery cases persist and allow state-based queries and counting."""
    cust_repo = CustomerRepository(db_session)
    tx_repo = TransactionRepository(db_session)
    case_repo = RecoveryCaseRepository(db_session)

    cust = Customer(id=uuid4(), provider="stripe", external_customer_id="cus_case_test")
    cust_repo.save(cust)
    tx = Transaction(
        id=uuid4(),
        customer_id=cust.id,
        provider="stripe",
        external_transaction_id="ch_case_tx",
        amount_minor=12000,
        currency="USD",
        status=TransactionStatus.FAILED,
        occurred_at=datetime.now(timezone.utc),
    )
    tx_repo.save(tx)
    db_session.commit()

    now = datetime.now(timezone.utc)
    case = RecoveryCase(
        id=uuid4(),
        customer_id=cust.id,
        trigger_transaction_id=tx.id,
        case_key="case_key_001",
        state=RecoveryCaseState.DETECTED,
        priority=100,
        opened_at=now,
        last_state_changed_at=now,
    )
    case_repo.save(case)
    db_session.commit()

    found_case = case_repo.find_by_case_key("case_key_001")
    assert found_case is not None
    assert found_case.id == case.id

    assert case_repo.count_by_state(RecoveryCaseState.DETECTED) == 1
    assert case_repo.count_by_state(RecoveryCaseState.RECOVERED) == 0


def test_recovery_attempt_idempotency_and_sequence_numbering(db_session):
    """Recovery attempts enforce monotonic sequence numbering and unique idempotency keys."""
    cust_repo = CustomerRepository(db_session)
    tx_repo = TransactionRepository(db_session)
    case_repo = RecoveryCaseRepository(db_session)
    attempt_repo = RecoveryAttemptRepository(db_session)

    cust = Customer(id=uuid4(), provider="stripe", external_customer_id="cus_att_test")
    cust_repo.save(cust)
    tx = Transaction(
        id=uuid4(),
        customer_id=cust.id,
        provider="stripe",
        external_transaction_id="ch_att_tx",
        amount_minor=4500,
        currency="USD",
        status=TransactionStatus.FAILED,
        occurred_at=datetime.now(timezone.utc),
    )
    tx_repo.save(tx)
    now = datetime.now(timezone.utc)
    case = RecoveryCase(
        id=uuid4(),
        customer_id=cust.id,
        trigger_transaction_id=tx.id,
        case_key="case_key_att",
        state=RecoveryCaseState.ACTION_PENDING,
        opened_at=now,
        last_state_changed_at=now,
    )
    case_repo.save(case)
    db_session.commit()

    # Sequence 1
    seq1 = attempt_repo.get_next_sequence_number(case.id)
    assert seq1 == 1
    att1 = RecoveryAttempt(
        id=uuid4(),
        case_id=case.id,
        sequence_number=seq1,
        status=RecoveryAttemptStatus.PLANNED,
        action_type=ActionType.RETRY_PAYMENT,
        idempotency_key="idemp_case_001_att_1",
    )
    attempt_repo.save(att1)
    db_session.commit()

    # Sequence 2
    seq2 = attempt_repo.get_next_sequence_number(case.id)
    assert seq2 == 2

    # Duplicate idempotency key must be rejected
    duplicate_att = RecoveryAttempt(
        id=uuid4(),
        case_id=case.id,
        sequence_number=seq2,
        status=RecoveryAttemptStatus.PLANNED,
        action_type=ActionType.RETRY_PAYMENT,
        idempotency_key="idemp_case_001_att_1",  # Same key
    )
    attempt_repo.save(duplicate_att)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_audit_event_repository_records_chronological_trail(db_session):
    """Audit events record monotonic sequence numbers and provide immutable audit trails."""
    cust_repo = CustomerRepository(db_session)
    tx_repo = TransactionRepository(db_session)
    case_repo = RecoveryCaseRepository(db_session)
    audit_repo = AuditEventRepository(db_session)

    cust = Customer(id=uuid4(), provider="stripe", external_customer_id="cus_audit_test")
    cust_repo.save(cust)
    tx = Transaction(
        id=uuid4(),
        customer_id=cust.id,
        provider="stripe",
        external_transaction_id="ch_audit_tx",
        amount_minor=9900,
        currency="USD",
        status=TransactionStatus.FAILED,
        occurred_at=datetime.now(timezone.utc),
    )
    tx_repo.save(tx)
    now = datetime.now(timezone.utc)
    case = RecoveryCase(
        id=uuid4(),
        customer_id=cust.id,
        trigger_transaction_id=tx.id,
        case_key="case_key_audit",
        state=RecoveryCaseState.DETECTED,
        opened_at=now,
        last_state_changed_at=now,
    )
    case_repo.save(case)
    db_session.commit()

    evt1 = audit_repo.record(
        case_id=case.id,
        event_type="CASE_DETECTED",
        actor_type=ActorType.SYSTEM,
        correlation_id="corr_test_001",
        payload_safe={"event": "payment_failure_ingested"},
        to_state=RecoveryCaseState.DETECTED,
    )
    db_session.commit()
    assert evt1.sequence_number == 1

    evt2 = audit_repo.record(
        case_id=case.id,
        event_type="POLICY_APPROVED",
        actor_type=ActorType.SYSTEM,
        correlation_id="corr_test_001",
        payload_safe={"rules_passed": ["MAX_RETRIES"]},
        from_state=RecoveryCaseState.DETECTED,
        to_state=RecoveryCaseState.ACTION_PENDING,
    )
    db_session.commit()
    assert evt2.sequence_number == 2

    trail = audit_repo.find_by_case(case.id)
    assert len(trail) == 2
    assert trail[0].sequence_number == 1
    assert trail[1].sequence_number == 2


def test_recovery_evidence_repository_verifies_settlement(db_session):
    """Recovery evidence preserves verified banking settlement details and enforces constraints."""
    repo = RecoveryEvidenceRepository(db_session)
    now = datetime.now(timezone.utc)
    evidence = RecoveryEvidence(
        id=uuid4(),
        intervention_id="int_001",
        provider_event_id="evt_settle_001",
        failed_transaction_id="tx_failed_99",
        successful_transaction_id="tx_success_100",
        amount_minor=4500,
        currency="USD",
        verified_at=now,
        attribution_window_hours=72,
        attribution_reason="exact_amount_and_token_match_within_72h",
        attributable=True,
        evidence_json={"provider_status": "succeeded"},
    )
    repo.save(evidence)
    db_session.commit()

    found = repo.find_by_provider_event_id("evt_settle_001")
    assert found is not None
    assert found.amount_minor == 4500
    assert found.attributable is True
