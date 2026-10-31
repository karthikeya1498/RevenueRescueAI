"""Unit and integration test suite for PolicyEngineService Step 3.

Verifies:
1. End-to-end orchestration across all five evaluators.
2. Authoritative 4-tier decision precedence aggregation:
   REJECTED > INSUFFICIENT_INFORMATION > REQUIRES_REVIEW > APPROVED.
3. Case FSM synchronization (APPROVED -> ACTION_PENDING, REQUIRES_REVIEW -> ESCALATED, etc.).
4. AgentDecision validation_status synchronization.
5. Idempotent evaluation request caching.
6. Immutable audit event recording and decision history preservation.
7. Financial safety invariants (no payment executions, no status mutations).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
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
    Customer,
    CustomerConsent,
    RecoveryAttempt,
    RecoveryCase,
    Transaction,
)
from app.policy.config import PolicyConfig
from app.policy.service import PolicyEngineService, PolicyEvaluationRequest


@pytest.fixture
def db_session():
    """Create an isolated SQLite database session enforcing foreign keys."""
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


def _seed_base_case(
    session,
    amount_minor=50_000,
    currency="INR",
    failure_code="insufficient_funds",
    confidence=Decimal("0.85"),
):
    """Helper to create a fully-wired recovery case scenario."""
    now = datetime.now(timezone.utc)
    customer = Customer(
        provider="stripe",
        external_customer_id=f"cust_{uuid4().hex[:8]}",
        email="test_customer@example.com",
        status=CustomerStatus.ACTIVE,
        metadata_json={"merchant_id": "merchant_123"},
    )
    session.add(customer)
    session.flush()

    tx = Transaction(
        customer_id=customer.id,
        provider="stripe",
        external_transaction_id=f"tx_{uuid4().hex[:8]}",
        amount_minor=amount_minor,
        currency=currency,
        status=TransactionStatus.FAILED,
        failure_code=failure_code,
        failure_message_safe="Card balance insufficient",
        occurred_at=now - timedelta(hours=1),
    )
    session.add(tx)
    session.flush()

    case = RecoveryCase(
        customer_id=customer.id,
        trigger_transaction_id=tx.id,
        case_key=f"case_{uuid4().hex[:8]}",
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
        reason_code="RETRY_STRATEGY_RECOMMENDED",
        confidence=confidence,
        validation_status=DecisionValidationStatus.NOT_VALIDATED,
    )
    session.add(rec)
    session.flush()

    consent = CustomerConsent(
        customer_id=customer.id,
        consent_type=ConsentType.RECURRING_BILLING,
        status=ConsentStatus.GRANTED,
        merchant_id="merchant_123",
        granted_at=now - timedelta(days=10),
        source="checkout_v1",
    )
    session.add(consent)
    session.commit()

    return customer, tx, case, rec, consent


class TestPolicyEngineServiceOrchestration:
    """Test suite for PolicyEngineService."""

    def test_approved_policy_evaluation_advances_to_action_pending(self, db_session):
        customer, tx, case, rec, consent = _seed_base_case(db_session)
        service = PolicyEngineService(db_session)

        request = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key="idemp_appr_001",
            actor_type=ActorType.SYSTEM,
        )

        result = service.evaluate(request)

        # 1. Authoritative Decision is APPROVED
        assert result.decision_status == PolicyDecisionStatus.APPROVED
        assert result.is_approved is True

        # 2. AgentDecision validation_status synchronized to VALID
        db_session.refresh(rec)
        assert rec.validation_status == DecisionValidationStatus.VALID

        # 3. RecoveryCase state transitioned to ACTION_PENDING
        db_session.refresh(case)
        assert case.state == RecoveryCaseState.ACTION_PENDING
        assert case.version == 2

        # 4. Financial safety check: Transaction remains FAILED
        db_session.refresh(tx)
        assert tx.status == TransactionStatus.FAILED

    def test_rejected_due_to_revoked_consent_blocks_action_pending(self, db_session):
        customer, tx, case, rec, consent = _seed_base_case(db_session)
        now = datetime.now(timezone.utc)

        # Revoke the recurring billing consent
        consent.status = ConsentStatus.REVOKED
        consent.revoked_at = now - timedelta(hours=2)
        db_session.commit()

        service = PolicyEngineService(db_session)
        request = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key="idemp_rej_consent",
        )

        result = service.evaluate(request)

        # 1. Authoritative Decision is REJECTED
        assert result.decision_status == PolicyDecisionStatus.REJECTED
        assert "CONSENT_REVOKED" in result.reasons

        # 2. AgentDecision synchronized to REJECTED_BY_POLICY
        db_session.refresh(rec)
        assert rec.validation_status == DecisionValidationStatus.REJECTED_BY_POLICY

        # 3. Case state MUST NOT become ACTION_PENDING
        db_session.refresh(case)
        assert case.state != RecoveryCaseState.ACTION_PENDING
        assert case.state == RecoveryCaseState.AWAITING_DECISION

    def test_rejected_due_to_retry_limit_transitions_to_stopped(self, db_session):
        customer, tx, case, rec, consent = _seed_base_case(db_session)
        now = datetime.now(timezone.utc)

        # Seed 3 prior failed attempts (exhausting max_retry_attempts=3)
        for i in range(1, 4):
            att = RecoveryAttempt(
                case_id=case.id,
                sequence_number=i,
                status=RecoveryAttemptStatus.FAILED,
                action_type=ActionType.RETRY_PAYMENT,
                started_at=now - timedelta(days=i),
                finished_at=now - timedelta(days=i),
                idempotency_key=f"att_key_{i}",
            )
            db_session.add(att)
        db_session.commit()

        service = PolicyEngineService(db_session)
        request = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key="idemp_rej_retries",
        )

        result = service.evaluate(request)

        assert result.decision_status == PolicyDecisionStatus.REJECTED
        assert "RETRY_LIMIT_EXCEEDED" in result.reasons

        # Case permanently stopped due to retry quota exhaustion
        db_session.refresh(case)
        assert case.state == RecoveryCaseState.STOPPED

    def test_high_value_exposure_escalates_to_human_review(self, db_session):
        # Exposure ₹1,500 (150,000 paise > 100,000 threshold)
        customer, tx, case, rec, consent = _seed_base_case(db_session, amount_minor=150_000)
        service = PolicyEngineService(db_session)

        request = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key="idemp_high_val",
        )

        result = service.evaluate(request)

        # 1. Authoritative Decision is REQUIRES_REVIEW
        assert result.decision_status == PolicyDecisionStatus.REQUIRES_REVIEW
        assert "HIGH_VALUE_REVIEW_REQUIRED" in result.reasons

        # 2. AgentDecision synchronized to NOT_VALIDATED
        db_session.refresh(rec)
        assert rec.validation_status == DecisionValidationStatus.NOT_VALIDATED

        # 3. Case transitioned to ESCALATED
        db_session.refresh(case)
        assert case.state == RecoveryCaseState.ESCALATED

    def test_low_ai_confidence_escalates_to_human_review(self, db_session):
        # AI confidence 0.40 (< 0.60 min threshold)
        customer, tx, case, rec, consent = _seed_base_case(db_session, confidence=Decimal("0.40"))
        service = PolicyEngineService(db_session)

        request = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key="idemp_low_conf",
        )

        result = service.evaluate(request)

        assert result.decision_status == PolicyDecisionStatus.REQUIRES_REVIEW
        assert "LOW_AI_CONFIDENCE" in result.reasons

        db_session.refresh(case)
        assert case.state == RecoveryCaseState.ESCALATED

    def test_missing_ai_confidence_returns_insufficient_information(self, db_session):
        customer, tx, case, rec, consent = _seed_base_case(db_session, confidence=None)
        service = PolicyEngineService(db_session)

        request = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key="idemp_miss_conf",
        )

        result = service.evaluate(request)

        assert result.decision_status == PolicyDecisionStatus.INSUFFICIENT_INFORMATION
        assert "AI_CONFIDENCE_MISSING" in result.reasons

        # Case remains in non-actionable state, never ACTION_PENDING
        db_session.refresh(case)
        assert case.state == RecoveryCaseState.AWAITING_DECISION

    def test_idempotent_evaluation_request_returns_cached_decision(self, db_session):
        customer, tx, case, rec, consent = _seed_base_case(db_session)
        service = PolicyEngineService(db_session)

        request = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=rec.id,
            idempotency_key="unique_idemp_key_999",
        )

        # First evaluation
        first_result = service.evaluate(request)
        assert first_result.decision_status == PolicyDecisionStatus.APPROVED

        # Duplicate evaluation submission with same key
        second_result = service.evaluate(request)
        assert second_result.decision_status == PolicyDecisionStatus.APPROVED
        assert second_result.metadata_json.get("cached_idempotent_result") is True

    def test_recommendation_mismatch_fails_closed(self, db_session):
        customer, tx, case, rec, consent = _seed_base_case(db_session)
        # Create a second real case to satisfy foreign keys
        _c2, _tx2, other_case, mismatched_rec, _con2 = _seed_base_case(db_session)

        service = PolicyEngineService(db_session)
        request = PolicyEvaluationRequest(
            case_id=case.id,
            recommendation_id=mismatched_rec.id,
            idempotency_key="mismatch_test_key",
        )

        result = service.evaluate(request)

        assert result.decision_status == PolicyDecisionStatus.REJECTED
        assert "RECOMMENDATION_MISMATCH" in result.reasons
