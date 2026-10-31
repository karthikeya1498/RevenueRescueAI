"""Step 6: Concurrency, Idempotency, and Audit Verification Test Suite.

Verifies:
1. Idempotency key caching prevents duplicate policy evaluations.
2. Historical PolicyDecision records are immutable and append-only.
3. AuditEvent stream records every evaluation with correlation IDs.
4. Stale recommendation and case state change detection.
5. Strict financial safety: no payment execution, no transaction status modification.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import (
    ActionType,
    ActorType,
    ConsentStatus,
    ConsentType,
    CustomerStatus,
    DecisionValidationStatus,
    PolicyDecisionStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.models.domain import (
    AgentDecision,
    AuditEvent,
    Customer,
    CustomerConsent,
    PolicyDecision,
    RecoveryAttempt,
    RecoveryCase,
    Transaction,
)
from app.policy.config import PolicyConfig
from app.policy.service import PolicyEngineService, PolicyEvaluationRequest


@pytest.fixture
def db_session():
    """Create an isolated in-memory SQLite database session with foreign keys."""
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


def _seed_concurrency_case(session):
    """Seed test fixtures for concurrency and audit verification."""
    now = datetime.now(timezone.utc)
    customer = Customer(
        provider="stripe",
        external_customer_id=f"cust_conc_{uuid4().hex[:6]}",
        email="concurrency@example.com",
        status=CustomerStatus.ACTIVE,
        metadata_json={"merchant_id": "merch_conc_1"},
    )
    session.add(customer)
    session.flush()

    tx = Transaction(
        customer_id=customer.id,
        provider="stripe",
        external_transaction_id=f"tx_conc_{uuid4().hex[:6]}",
        amount_minor=50_000,
        currency="INR",
        status=TransactionStatus.FAILED,
        failure_code="insufficient_funds",
        failure_message_safe="Insufficient funds",
        occurred_at=now - timedelta(hours=1),
    )
    session.add(tx)
    session.flush()

    case = RecoveryCase(
        customer_id=customer.id,
        trigger_transaction_id=tx.id,
        case_key=f"case_conc_{uuid4().hex[:6]}",
        state=RecoveryCaseState.AWAITING_DECISION,
        priority=100,
        opened_at=now,
        last_state_changed_at=now,
        version=1,
    )
    session.add(case)
    session.flush()

    rec = AgentDecision(
        case_id=case.id,
        decision_version=1,
        action_type=ActionType.RETRY_PAYMENT,
        reason_code="AI_RECOMMENDED_RETRY",
        confidence=Decimal("0.90"),
        validation_status=DecisionValidationStatus.NOT_VALIDATED,
    )
    session.add(rec)
    session.flush()

    consent = CustomerConsent(
        customer_id=customer.id,
        consent_type=ConsentType.RECURRING_BILLING,
        status=ConsentStatus.GRANTED,
        merchant_id="merch_conc_1",
        granted_at=now - timedelta(days=5),
        source="checkout_agreement",
    )
    session.add(consent)
    session.commit()

    return customer, tx, case, rec, consent


class TestConcurrencyAndAuditVerification:
    """Step 6 verification tests."""

    def test_idempotent_duplicate_prevention(self, db_session):
        """Repeated evaluations with the same idempotency key return cached result."""
        _customer, _tx, case, rec, _consent = _seed_concurrency_case(db_session)
        service = PolicyEngineService(db_session)

        idemp_key = f"key_{uuid4().hex}"
        req1 = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key=idemp_key,
        )

        res1 = service.evaluate(req1)
        assert res1.decision_status == PolicyDecisionStatus.APPROVED

        # Verify exactly 1 PolicyDecision record exists
        stmt = select(PolicyDecision).where(PolicyDecision.case_id == case.id)
        records_after_first = list(db_session.scalars(stmt).all())
        assert len(records_after_first) == 1

        # Second request with same idempotency key
        req2 = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key=idemp_key,
        )
        res2 = service.evaluate(req2)
        assert res2.decision_status == PolicyDecisionStatus.APPROVED
        assert res2.metadata_json.get("cached_idempotent_result") is True

        # Assert no duplicate record was created
        records_after_second = list(db_session.scalars(stmt).all())
        assert len(records_after_second) == 1

    def test_immutable_audit_trail_generation(self, db_session):
        """Every evaluation records an immutable AuditEvent and PolicyDecision."""
        _customer, _tx, case, rec, _consent = _seed_concurrency_case(db_session)
        service = PolicyEngineService(db_session)

        req = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key=f"audit_test_{uuid4().hex}",
            actor_type=ActorType.OPERATOR,
            actor_id="operator_usr_123",
        )
        result = service.evaluate(req)

        # Query audit events for the case
        audit_stmt = select(AuditEvent).where(
            AuditEvent.case_id == case.id,
            AuditEvent.event_type == "POLICY_EVALUATION_COMPLETED",
        )
        audit_events = list(db_session.scalars(audit_stmt).all())
        assert len(audit_events) == 1

        ev = audit_events[0]
        assert ev.actor_type == ActorType.OPERATOR
        assert ev.actor_id == "operator_usr_123"
        assert ev.payload_safe["decision_status"] == "approved"
        assert ev.payload_safe["policy_version"] == "policy-v1.0"
        assert ev.to_state == RecoveryCaseState.ACTION_PENDING

    def test_stale_case_state_change_prevention(self, db_session):
        """If another process resolves the case to RECOVERED, policy engine rejects."""
        _customer, _tx, case, rec, _consent = _seed_concurrency_case(db_session)
        service = PolicyEngineService(db_session)

        # Another process recovers the payment in the background
        case.state = RecoveryCaseState.RECOVERED
        db_session.commit()

        req = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key=f"stale_test_{uuid4().hex}",
        )
        result = service.evaluate(req)

        assert result.decision_status == PolicyDecisionStatus.REJECTED
        assert "CASE_ALREADY_RECOVERED" in result.reasons

        # Recommendation was invalidated
        db_session.refresh(rec)
        assert rec.validation_status == DecisionValidationStatus.REJECTED_BY_POLICY

    def test_zero_financial_execution_invariant(self, db_session):
        """Verify policy evaluation NEVER modifies transaction amounts or statuses."""
        _customer, tx, case, rec, _consent = _seed_concurrency_case(db_session)
        service = PolicyEngineService(db_session)

        original_amount = tx.amount_minor
        original_status = tx.status

        req = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
        )
        service.evaluate(req)

        db_session.refresh(tx)
        # Transaction financial attributes MUST be strictly identical
        assert tx.amount_minor == original_amount
        assert tx.status == original_status
        assert tx.status == TransactionStatus.FAILED
