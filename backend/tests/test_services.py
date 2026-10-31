"""Unit and integration tests for application service layer.

Author: Karthikeya
Architectural layer: test suite / services.
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import ActorType, CustomerStatus, RecoveryCaseState, TransactionStatus
from app.core.errors import (
    DuplicateEntityException,
    EntityNotFoundException,
    InvalidStateTransitionException,
)
from app.schemas.audit_events import AuditEventCreateDTO
from app.schemas.customers import CustomerCreateDTO, CustomerUpdateDTO
from app.schemas.recovery_cases import CaseStateTransitionDTO, RecoveryCaseCreateDTO
from app.schemas.transactions import TransactionCreateDTO
from app.services.audit_service import AuditService
from app.services.customer_service import CustomerService
from app.services.recovery_case_service import RecoveryCaseService
from app.services.transaction_service import TransactionService


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


def test_customer_service_crud_and_duplicates(db_session) -> None:
    """Test customer service creation, duplicate prevention, and updates."""
    service = CustomerService(db_session)

    # 1. Create customer
    dto = CustomerCreateDTO(
        provider="stripe",
        external_customer_id="cus_service_01",
        email="corp@acme.com",
        display_name="Acme Corp",
    )
    created = service.create_customer(dto)
    assert created.id is not None
    assert created.external_customer_id == "cus_service_01"
    assert created.email == "corp@acme.com"

    # 2. Duplicate detection
    with pytest.raises(DuplicateEntityException) as exc_info:
        service.create_customer(dto)
    assert "already exists" in str(exc_info.value.message)

    # 3. Retrieve by ID
    retrieved = service.get_customer(created.id)
    assert retrieved.id == created.id

    # 4. Retrieve by external ID
    by_ext = service.get_by_external_id("stripe", "cus_service_01")
    assert by_ext.id == created.id

    # 5. Missing customer raises EntityNotFoundException
    with pytest.raises(EntityNotFoundException):
        service.get_customer(uuid4())

    # 6. Update customer
    updated = service.update_customer(
        created.id,
        CustomerUpdateDTO(display_name="Acme International", status=CustomerStatus.RESTRICTED),
    )
    assert updated.display_name == "Acme International"
    assert updated.status == CustomerStatus.RESTRICTED

    # 7. Paginated list
    page = service.list_customers(page=1, size=10)
    assert page.pagination.total == 1
    assert len(page.items) == 1


def test_transaction_service_and_referential_checks(db_session) -> None:
    """Test transaction recording, customer referential integrity, and pagination."""
    cust_service = CustomerService(db_session)
    tx_service = TransactionService(db_session)

    # Missing customer rejected
    with pytest.raises(EntityNotFoundException) as exc_info:
        tx_service.record_transaction(
            TransactionCreateDTO(
                customer_id=uuid4(),
                provider="stripe",
                external_transaction_id="ch_no_cust",
                amount_minor=5000,
                currency="USD",
                status=TransactionStatus.FAILED,
            )
        )
    assert "Customer" in exc_info.value.message

    # Create real customer
    customer = cust_service.create_customer(
        CustomerCreateDTO(
            provider="stripe",
            external_customer_id="cus_tx_test",
            display_name="TX Customer",
        )
    )

    # Record valid transaction
    tx_dto = TransactionCreateDTO(
        customer_id=customer.id,
        provider="stripe",
        external_transaction_id="ch_valid_001",
        amount_minor=12999,
        currency="USD",
        status=TransactionStatus.FAILED,
        failure_code="card_velocity_exceeded",
    )
    recorded = tx_service.record_transaction(tx_dto)
    assert recorded.id is not None
    assert recorded.amount_minor == 12999

    # Duplicate external ID rejected
    with pytest.raises(DuplicateEntityException):
        tx_service.record_transaction(tx_dto)

    # Retrieve by ID and external ID
    assert tx_service.get_transaction(recorded.id).id == recorded.id
    assert tx_service.get_by_external_id("stripe", "ch_valid_001").id == recorded.id

    # Paginate customer transactions
    paginated = tx_service.list_transactions_for_customer(customer.id, page=1, size=10)
    assert paginated.pagination.total == 1
    assert paginated.items[0].id == recorded.id


def test_recovery_case_service_lifecycle_and_state_machine(db_session) -> None:
    """Test recovery case creation, audit trail generation, and legal state transitions."""
    cust_service = CustomerService(db_session)
    tx_service = TransactionService(db_session)
    case_service = RecoveryCaseService(db_session)
    audit_service = AuditService(db_session)

    # Setup Customer and Failed Transaction
    customer = cust_service.create_customer(
        CustomerCreateDTO(
            provider="stripe",
            external_customer_id="cus_case_test",
        )
    )
    transaction = tx_service.record_transaction(
        TransactionCreateDTO(
            customer_id=customer.id,
            provider="stripe",
            external_transaction_id="ch_case_trigger",
            amount_minor=7500,
            currency="USD",
            status=TransactionStatus.FAILED,
        )
    )

    # Create case
    case = case_service.create_case(
        RecoveryCaseCreateDTO(
            customer_id=customer.id,
            trigger_transaction_id=transaction.id,
            priority=50,
        )
    )
    assert case.id is not None
    assert case.state == RecoveryCaseState.DETECTED
    assert case.priority == 50

    # Verify CASE_OPENED audit event was automatically written
    audit_trail = audit_service.get_audit_trail_for_case(case.id)
    assert len(audit_trail) == 1
    assert audit_trail[0].event_type == "CASE_OPENED"
    assert audit_trail[0].to_state == RecoveryCaseState.DETECTED

    # Prevent duplicate case for same trigger transaction
    with pytest.raises(DuplicateEntityException):
        case_service.create_case(
            RecoveryCaseCreateDTO(
                customer_id=customer.id,
                trigger_transaction_id=transaction.id,
            )
        )

    # Transition 1: DETECTED -> ACTION_PENDING
    transition1 = CaseStateTransitionDTO(
        to_state=RecoveryCaseState.ACTION_PENDING,
        reason_code="POLICY_EVALUATION_PASSED",
        actor_type=ActorType.SYSTEM,
        correlation_id="corr_test_001",
    )
    updated_case1 = case_service.transition_state(case.id, transition1)
    assert updated_case1.state == RecoveryCaseState.ACTION_PENDING
    assert updated_case1.version == 2

    # Verify audit trail now has 2 events
    audit_trail = audit_service.get_audit_trail_for_case(case.id)
    assert len(audit_trail) == 2
    assert audit_trail[1].event_type == "STATE_TRANSITION"
    assert audit_trail[1].from_state == RecoveryCaseState.DETECTED
    assert audit_trail[1].to_state == RecoveryCaseState.ACTION_PENDING

    # Identity transition (same state) must be rejected
    with pytest.raises(InvalidStateTransitionException):
        case_service.transition_state(case.id, transition1)

    # Transition 2: ACTION_PENDING -> RECOVERED (terminal state)
    transition2 = CaseStateTransitionDTO(
        to_state=RecoveryCaseState.RECOVERED,
        reason_code="PAYMENT_VERIFIED",
        actor_type=ActorType.SYSTEM,
        correlation_id="corr_test_002",
    )
    terminal_case = case_service.transition_state(case.id, transition2)
    assert terminal_case.state == RecoveryCaseState.RECOVERED
    assert terminal_case.closed_at is not None

    # Transition from terminal state must be rejected
    with pytest.raises(InvalidStateTransitionException):
        case_service.transition_state(
            case.id,
            CaseStateTransitionDTO(
                to_state=RecoveryCaseState.DETECTED,
                reason_code="ILLEGAL_REOPEN",
                actor_type=ActorType.OPERATOR,
                correlation_id="corr_illegal",
            ),
        )


def test_audit_service_correlation_and_sequencing(db_session) -> None:
    """Test append-only audit trail service monotonic sequence numbers and correlation queries."""
    cust_service = CustomerService(db_session)
    tx_service = TransactionService(db_session)
    case_service = RecoveryCaseService(db_session)
    audit_service = AuditService(db_session)

    customer = cust_service.create_customer(
        CustomerCreateDTO(provider="stripe", external_customer_id="cus_audit_test")
    )
    tx = tx_service.record_transaction(
        TransactionCreateDTO(
            customer_id=customer.id,
            provider="stripe",
            external_transaction_id="ch_audit_tx",
            amount_minor=1000,
            currency="USD",
            status=TransactionStatus.FAILED,
        )
    )
    case = case_service.create_case(
        RecoveryCaseCreateDTO(customer_id=customer.id, trigger_transaction_id=tx.id)
    )

    # Initial audit event is sequence 1 (from create_case)
    event1 = audit_service.record_event(
        AuditEventCreateDTO(
            case_id=case.id,
            event_type="CUSTOM_OPERATOR_NOTE",
            actor_type=ActorType.OPERATOR,
            actor_id="operator_bob",
            correlation_id="corr_shared_xyz",
            payload_safe={"note": "Reviewing customer account history"},
        )
    )
    assert event1.sequence_number == 2

    # Query by correlation ID
    by_corr = audit_service.get_events_by_correlation_id("corr_shared_xyz")
    assert len(by_corr) == 1
    assert by_corr[0].actor_id == "operator_bob"
