"""Unit tests for entity-to-DTO and DTO-to-entity mappers.

Author: Karthikeya
Architectural layer: tests / mappers.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.core.enums import (
    ActionType,
    ActorType,
    CustomerStatus,
    DecisionValidationStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.mappers import (
    AgentDecisionMapper,
    AuditEventMapper,
    CustomerMapper,
    RecoveryAttemptMapper,
    RecoveryCaseMapper,
    RecoveryEvidenceMapper,
    TransactionMapper,
)
from app.models.domain import (
    AgentDecision,
    AuditEvent,
    Customer,
    RecoveryAttempt,
    RecoveryCase,
    RecoveryEvidence,
    Transaction,
)
from app.schemas.agent_decisions import AgentDecisionCreateDTO
from app.schemas.audit_events import AuditEventCreateDTO
from app.schemas.customers import CustomerCreateDTO
from app.schemas.recovery_attempts import RecoveryAttemptCreateDTO
from app.schemas.recovery_cases import RecoveryCaseCreateDTO
from app.schemas.recovery_evidence import RecoveryEvidenceCreateDTO
from app.schemas.transactions import TransactionCreateDTO


def test_customer_mapper() -> None:
    """Verify Customer entity-to-DTO and DTO-to-entity transformations."""
    now = datetime.now(timezone.utc)
    customer_id = uuid4()
    entity = Customer(
        id=customer_id,
        provider="stripe",
        external_customer_id="cus_mapper_test",
        email="test@enterprise.com",
        display_name="Enterprise Corp",
        status=CustomerStatus.ACTIVE,
        metadata_json={"tier": "enterprise"},
    )
    entity.created_at = now
    entity.updated_at = now

    # Entity to ResponseDTO
    response = CustomerMapper.to_response(entity)
    assert response.id == customer_id
    assert response.provider == "stripe"
    assert response.email == "test@enterprise.com"
    assert response.metadata == {"tier": "enterprise"}

    # Entity to SummaryDTO
    summary = CustomerMapper.to_summary(entity)
    assert summary.id == customer_id
    assert summary.external_customer_id == "cus_mapper_test"

    # DTO to Entity
    create_dto = CustomerCreateDTO(
        provider="razorpay",
        external_customer_id="cust_rzp_99",
        display_name="Razorpay Client",
    )
    new_entity = CustomerMapper.to_entity(create_dto)
    assert new_entity.id is not None
    assert new_entity.provider == "razorpay"
    assert new_entity.display_name == "Razorpay Client"


def test_transaction_mapper() -> None:
    """Verify Transaction mapper preserves exact integer minor units."""
    now = datetime.now(timezone.utc)
    tx_id = uuid4()
    cust_id = uuid4()
    entity = Transaction(
        id=tx_id,
        customer_id=cust_id,
        provider="stripe",
        external_transaction_id="ch_mapper_001",
        amount_minor=9999,
        currency="USD",
        status=TransactionStatus.FAILED,
        failure_code="card_declined",
        failure_message_safe="Card was declined.",
        occurred_at=now,
        metadata_json={"card_brand": "visa"},
    )
    entity.created_at = now
    entity.updated_at = now

    response = TransactionMapper.to_response(entity)
    assert response.id == tx_id
    assert response.amount_minor == 9999
    assert response.currency == "USD"
    assert response.failure_code == "card_declined"

    summary = TransactionMapper.to_summary(entity)
    assert summary.id == tx_id
    assert summary.amount_minor == 9999

    create_dto = TransactionCreateDTO(
        customer_id=cust_id,
        provider="synthetic",
        external_transaction_id="tx_syn_01",
        amount_minor=4500,
        currency="EUR",
        status=TransactionStatus.FAILED,
    )
    new_tx = TransactionMapper.to_entity(create_dto)
    assert new_tx.amount_minor == 4500
    assert new_tx.currency == "EUR"
    assert new_tx.occurred_at is not None


def test_recovery_case_mapper() -> None:
    """Verify RecoveryCase mapper generates case keys and sets initial states."""
    now = datetime.now(timezone.utc)
    case_id = uuid4()
    cust_id = uuid4()
    tx_id = uuid4()

    entity = RecoveryCase(
        id=case_id,
        customer_id=cust_id,
        trigger_transaction_id=tx_id,
        case_key="CASE-TEST-001",
        state=RecoveryCaseState.DETECTED,
        priority=100,
        opened_at=now,
        last_state_changed_at=now,
        closed_at=None,
        version=1,
        metadata_json={},
    )

    response = RecoveryCaseMapper.to_response(entity)
    assert response.id == case_id
    assert response.case_key == "CASE-TEST-001"
    assert response.state == RecoveryCaseState.DETECTED

    create_dto = RecoveryCaseCreateDTO(
        customer_id=cust_id,
        trigger_transaction_id=tx_id,
        priority=50,
    )
    new_case = RecoveryCaseMapper.to_entity(create_dto)
    assert new_case.case_key.startswith("CASE-")
    assert new_case.state == RecoveryCaseState.DETECTED
    assert new_case.priority == 50


def test_recovery_attempt_mapper() -> None:
    """Verify RecoveryAttempt mapper handles sequence numbers and idempotency."""
    attempt_id = uuid4()
    case_id = uuid4()
    entity = RecoveryAttempt(
        id=attempt_id,
        case_id=case_id,
        sequence_number=1,
        status=RecoveryAttemptStatus.PLANNED,
        action_type=ActionType.RETRY_PAYMENT,
        idempotency_key="idemp_key_001",
        metadata_json={},
    )

    response = RecoveryAttemptMapper.to_response(entity)
    assert response.id == attempt_id
    assert response.sequence_number == 1
    assert response.idempotency_key == "idemp_key_001"

    create_dto = RecoveryAttemptCreateDTO(
        case_id=case_id,
        action_type=ActionType.RETRY_PAYMENT,
        idempotency_key="idemp_key_002",
    )
    new_attempt = RecoveryAttemptMapper.to_entity(create_dto, sequence_number=2)
    assert new_attempt.sequence_number == 2
    assert new_attempt.idempotency_key == "idemp_key_002"


def test_agent_decision_mapper() -> None:
    """Verify AgentDecision mapper preserves confidence and reason codes."""
    decision_id = uuid4()
    case_id = uuid4()
    entity = AgentDecision(
        id=decision_id,
        case_id=case_id,
        attempt_id=None,
        decision_version=1,
        action_type=ActionType.RETRY_PAYMENT,
        reason_code="SOFT_DECLINE_RETRYABLE",
        rationale_safe="Transient network decline.",
        confidence=Decimal("0.92"),
        raw_response_hash="hash123",
        validation_status=DecisionValidationStatus.VALID,
    )

    response = AgentDecisionMapper.to_response(entity)
    assert response.id == decision_id
    assert response.confidence == Decimal("0.92")
    assert response.reason_code == "SOFT_DECLINE_RETRYABLE"

    create_dto = AgentDecisionCreateDTO(
        case_id=case_id,
        action_type=ActionType.STOP,
        reason_code="HARD_DECLINE_STOLEN_CARD",
        confidence=Decimal("0.99"),
    )
    new_decision = AgentDecisionMapper.to_entity(create_dto, decision_version=2)
    assert new_decision.decision_version == 2
    assert new_decision.confidence == Decimal("0.99")


def test_audit_event_mapper() -> None:
    """Verify AuditEvent mapper."""
    event_id = uuid4()
    case_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = AuditEvent(
        id=event_id,
        case_id=case_id,
        event_type="TEST_EVENT",
        from_state=RecoveryCaseState.DETECTED,
        to_state=RecoveryCaseState.ACTION_PENDING,
        actor_type=ActorType.OPERATOR,
        actor_id="admin@enterprise.com",
        correlation_id="corr_123",
        event_time=now,
        payload_safe={"action": "approved"},
        sequence_number=1,
    )

    response = AuditEventMapper.to_response(entity)
    assert response.id == event_id
    assert response.event_type == "TEST_EVENT"
    assert response.from_state == RecoveryCaseState.DETECTED

    create_dto = AuditEventCreateDTO(
        case_id=case_id,
        event_type="STATE_CHANGE",
        actor_type=ActorType.SYSTEM,
        correlation_id="corr_456",
        from_state=RecoveryCaseState.ACTION_PENDING,
        to_state=RecoveryCaseState.RECOVERED,
    )
    new_event = AuditEventMapper.to_entity(create_dto, sequence_number=2)
    assert new_event.sequence_number == 2
    assert new_event.correlation_id == "corr_456"


def test_recovery_evidence_mapper() -> None:
    """Verify RecoveryEvidence mapper."""
    ev_id = uuid4()
    now = datetime.now(timezone.utc)
    entity = RecoveryEvidence(
        id=ev_id,
        intervention_id="int_01",
        provider_event_id="evt_01",
        failed_transaction_id="tx_fail",
        successful_transaction_id="tx_success",
        amount_minor=10000,
        currency="USD",
        verified_at=now,
        attribution_window_hours=72,
        attribution_reason="settled_after_retry",
        attributable=True,
        evidence_json={"provider": "stripe"},
    )
    entity.created_at = now
    entity.updated_at = now

    response = RecoveryEvidenceMapper.to_response(entity)
    assert response.id == ev_id
    assert response.amount_minor == 10000
    assert response.attributable is True

    create_dto = RecoveryEvidenceCreateDTO(
        intervention_id="int_02",
        provider_event_id="evt_02",
        failed_transaction_id="tx_f",
        successful_transaction_id="tx_s",
        amount_minor=5000,
        currency="EUR",
        attribution_reason="reason_test",
        attributable=False,
    )
    new_ev = RecoveryEvidenceMapper.to_entity(create_dto)
    assert new_ev.amount_minor == 5000
    assert new_ev.currency == "EUR"
    assert new_ev.attributable is False
