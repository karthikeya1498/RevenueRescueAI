"""Comprehensive Automated Test Suite for Phase 2.8: AI-Powered Recovery Intelligence Engine.

Author: Karthikeya
Architectural layer: Unit, Integration, and Financial Safety Test Suite.

Verifies:
1. Failure Analysis: Accurate categorization of normalized failure events and diagnostics.
2. Risk Assessment: Transparent 0-100 risk scoring, bands (LOW, MEDIUM, HIGH), and action limits.
3. Probability Estimation: Bounded recovery probabilities [0.0100, 0.9900] and model adapter contract.
4. Strategy Selection: Expected-value ranking, policy filtering, exhausted attempt protection, and terminal case halt.
5. Factual Explainability: Evidence-backed rationales without hallucination.
6. Intelligence Orchestration: Persistence as AgentDecision (NOT_VALIDATED), audit logging, and FSM transition.
7. REST APIs: POST recommendations, GET latest, GET history, dry-run decision-preview, RBAC enforcement.
8. Financial Safety: Zero mutations to payment status, no unauthorized retries, and no revenue fabrication.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import (
    ActionType,
    ActorType,
    CustomerStatus,
    DecisionValidationStatus,
    RecoveryCaseState,
    TransactionStatus,
    UserRole,
    UserStatus,
)
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.domain import AgentDecision, AuditEvent, Customer, RecoveryCase, Transaction, User
from app.schemas.agent_decisions import DecisionPreviewRequestDTO
from app.services.intelligence.explanation_service import ExplanationService
from app.services.intelligence.failure_analyzer import FailureAnalyzer
from app.services.intelligence.model_adapter import RecoveryEstimatorAdapter
from app.services.intelligence.orchestrator import IntelligenceOrchestrator
from app.services.intelligence.probability_estimator import LogisticRecoveryEstimator
from app.services.intelligence.risk_assessor import RiskAssessor
from app.services.intelligence.strategy_catalog import RecoveryStrategy, StrategyCatalog
from app.services.intelligence.strategy_selector import StrategySelector


# ==============================================================================
# Fixtures & Setup
# ==============================================================================

@pytest.fixture
def db_session():
    """Create an isolated, in-memory SQLite database session enforcing foreign keys."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

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


@pytest.fixture
def client(db_session):
    """FastAPI test client with database dependency override."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def operator_token(db_session):
    """Create an active operator user and return JWT bearer token."""
    user = User(
        id=uuid4(),
        email="operator.intel@revenuerescue.ai",
        name="Intelligence Operator",
        password_hash=hash_password("OperatorPass123!"),
        role=UserRole.OPERATOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(user_id=user.id, email=user.email, role=UserRole.OPERATOR)


@pytest.fixture
def auditor_token(db_session):
    """Create a compliance auditor user and return JWT bearer token."""
    user = User(
        id=uuid4(),
        email="auditor.intel@revenuerescue.ai",
        name="Compliance Auditor",
        password_hash=hash_password("AuditorPass123!"),
        role=UserRole.AUDITOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(user_id=user.id, email=user.email, role=UserRole.AUDITOR)


@pytest.fixture
def ingestor_token(db_session):
    """Create a webhook ingestor user without case recommendation rights."""
    user = User(
        id=uuid4(),
        email="ingestor.service@revenuerescue.ai",
        name="Webhook Ingestor",
        password_hash=hash_password("IngestorPass123!"),
        role=UserRole.INGESTOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(user_id=user.id, email=user.email, role=UserRole.INGESTOR)


@pytest.fixture
def sample_case(db_session) -> RecoveryCase:
    """Create a sample recovery case in DETECTED state with associated customer and transaction."""
    customer = Customer(
        id=uuid4(),
        provider="synthetic",
        external_customer_id="cust_intel_001",
        email="customer@example.com",
        display_name="Acme Corp",
        status=CustomerStatus.ACTIVE,
        metadata_json={"success_rate": 0.85, "has_alternate_method": True},
    )
    db_session.add(customer)

    now = datetime.now(timezone.utc)
    txn = Transaction(
        id=uuid4(),
        customer_id=customer.id,
        provider="synthetic",
        external_transaction_id="txn_intel_fail_001",
        amount_minor=12500,  # $125.00
        currency="USD",
        status=TransactionStatus.FAILED,
        failure_code="insufficient_funds",
        failure_message_safe="Card balance insufficient for recurring charge",
        occurred_at=now,
        metadata_json={"is_subscription": True},
    )
    db_session.add(txn)

    case = RecoveryCase(
        id=uuid4(),
        customer_id=customer.id,
        trigger_transaction_id=txn.id,
        case_key=f"REC-{txn.external_transaction_id}",
        state=RecoveryCaseState.DETECTED,
        priority=350,
        opened_at=now,
        last_state_changed_at=now,
        version=1,
        metadata_json={"is_subscription": True},
    )
    db_session.add(case)
    db_session.commit()
    return case


# ==============================================================================
# 1. Failure Analysis Unit Tests
# ==============================================================================

def test_failure_analyzer_insufficient_funds() -> None:
    analyzer = FailureAnalyzer()
    result = analyzer.analyze(code="insufficient_funds", message="Not enough balance")
    assert result.failure_category == "insufficient_funds"
    assert result.retryable is True
    assert result.confidence >= Decimal("0.9000")
    assert "cooling period" in result.explanation.lower()


def test_failure_analyzer_expired_card() -> None:
    analyzer = FailureAnalyzer()
    result = analyzer.analyze(code="card_expired", message="Card validity date expired")
    assert result.failure_category == "expired_card"
    assert result.retryable is False
    assert result.confidence >= Decimal("0.9000")


def test_failure_analyzer_authentication_required() -> None:
    analyzer = FailureAnalyzer()
    result = analyzer.analyze(code="authentication_required", message="3DS challenge failed")
    assert result.failure_category == "authentication_required"
    assert result.retryable is True


def test_failure_analyzer_bank_decline() -> None:
    analyzer = FailureAnalyzer()
    result = analyzer.analyze(code="do_not_honor", message="Issuer declined transaction")
    assert result.failure_category == "bank_decline"
    assert result.retryable is True


def test_failure_analyzer_provider_timeout() -> None:
    analyzer = FailureAnalyzer()
    result = analyzer.analyze(code="network_timeout", message="Gateway timeout communicating with processor")
    assert result.failure_category == "provider_timeout"
    assert result.retryable is True


def test_failure_analyzer_fraud_suspected() -> None:
    analyzer = FailureAnalyzer()
    result = analyzer.analyze(code="fraud_suspected", message="Blocked by risk engine score 92")
    assert result.failure_category == "fraud_suspected"
    assert result.retryable is False


def test_failure_analyzer_unknown_code_and_missing_values() -> None:
    analyzer = FailureAnalyzer()
    res1 = analyzer.analyze(code="ERR_RANDOM_999", message=None)
    assert res1.failure_category == "unknown_failure"
    assert res1.retryable is False
    assert res1.confidence <= Decimal("0.6000")

    res2 = analyzer.analyze(code=None, message=None)
    assert res2.failure_category == "unknown_failure"
    assert res2.retryable is False


# ==============================================================================
# 2. Risk Assessment Unit Tests
# ==============================================================================

def test_risk_assessor_low_risk() -> None:
    assessor = RiskAssessor()
    res = assessor.assess(
        failure_category="insufficient_funds",
        amount_minor=2500,  # $25.00
        prior_attempts=0,
        is_subscription=True,
    )
    assert res.score < 31
    assert res.band == "low"
    assert res.action_limit == "automatic"


def test_risk_assessor_medium_risk() -> None:
    assessor = RiskAssessor()
    res = assessor.assess(
        failure_category="bank_decline",
        amount_minor=120000,  # $1,200.00
        prior_attempts=2,
    )
    assert 30 <= res.score <= 70
    assert res.band == "medium"
    assert res.action_limit == "human_approval"


def test_risk_assessor_high_risk_fraud_and_restricted() -> None:
    assessor = RiskAssessor()
    res = assessor.assess(
        failure_category="fraud_suspected",
        amount_minor=500000,  # $5,000.00
        prior_attempts=4,
        unusual_velocity=True,
        customer_restricted=True,
    )
    assert res.score >= 71
    assert res.score <= 100
    assert res.band == "high"
    assert res.action_limit == "block"


# ==============================================================================
# 3. Probability Estimator & Adapter Contract Tests
# ==============================================================================

def test_logistic_estimator_probability_bounds() -> None:
    estimator = LogisticRecoveryEstimator()

    p_low = estimator.estimate_recovery_probability(
        action_type=ActionType.STOP,
        failure_category="fraud_suspected",
        is_retryable=False,
        amount_minor=500000,
        prior_attempts=5,
        risk_score=95,
    )
    assert Decimal("0.0100") <= p_low <= Decimal("0.9900")

    p_high = estimator.estimate_recovery_probability(
        action_type=ActionType.RETRY_PAYMENT,
        failure_category="insufficient_funds",
        is_retryable=True,
        amount_minor=2000,
        prior_attempts=0,
        customer_success_rate=0.95,
        risk_score=10,
    )
    assert Decimal("0.0100") <= p_high <= Decimal("0.9900")
    assert p_high > p_low


def test_custom_estimator_adapter_contract() -> None:
    class MockAdapter(RecoveryEstimatorAdapter):
        @property
        def model_version(self) -> str:
            return "mock-ml-v2"

        def estimate_recovery_probability(self, **kwargs) -> Decimal:
            return Decimal("0.7777")

        def get_model_metadata(self) -> dict:
            return {"type": "mock_random_forest"}

    adapter = MockAdapter()
    assert adapter.get_model_version() == "mock-ml-v2"
    p = adapter.estimate_recovery_probability(
        action_type=ActionType.RETRY_PAYMENT,
        failure_category="insufficient_funds",
        is_retryable=True,
        amount_minor=1000,
        prior_attempts=0,
    )
    assert p == Decimal("0.7777")


# ==============================================================================
# 4. Strategy Selector Unit Tests
# ==============================================================================

def test_strategy_selector_insufficient_funds_recommends_retry() -> None:
    analyzer = FailureAnalyzer()
    assessor = RiskAssessor()
    selector = StrategySelector(estimator=LogisticRecoveryEstimator())

    failure = analyzer.analyze(code="insufficient_funds")
    risk = assessor.assess(failure_category=failure.category, amount_minor=5000, prior_attempts=0)

    result = selector.select_strategy(
        amount_minor=5000,
        failure=failure,
        risk=risk,
        prior_attempts=0,
    )
    assert result.selected_strategy == RecoveryStrategy.RETRY_LATER
    assert result.action_type == ActionType.RETRY_PAYMENT
    assert result.expected_value_minor > 0


def test_strategy_selector_expired_card_recommends_update_payment_method() -> None:
    analyzer = FailureAnalyzer()
    assessor = RiskAssessor()
    selector = StrategySelector(estimator=LogisticRecoveryEstimator())

    failure = analyzer.analyze(code="card_expired")
    risk = assessor.assess(failure_category=failure.category, amount_minor=5000, prior_attempts=0)

    result = selector.select_strategy(
        amount_minor=5000,
        failure=failure,
        risk=risk,
        prior_attempts=0,
    )
    assert result.selected_strategy == RecoveryStrategy.UPDATE_PAYMENT_METHOD
    assert result.action_type == ActionType.SEND_REMINDER


def test_strategy_selector_terminal_case_halts_recovery() -> None:
    analyzer = FailureAnalyzer()
    assessor = RiskAssessor()
    selector = StrategySelector(estimator=LogisticRecoveryEstimator())

    failure = analyzer.analyze(code="insufficient_funds")
    risk = assessor.assess(failure_category=failure.category, amount_minor=5000, prior_attempts=0)

    result = selector.select_strategy(
        amount_minor=5000,
        failure=failure,
        risk=risk,
        prior_attempts=0,
        is_case_terminal=True,
    )
    assert result.selected_strategy == RecoveryStrategy.NO_ACTION
    assert result.action_type == ActionType.STOP
    assert result.confidence == Decimal("1.0000")
    assert result.expected_value_minor == 0


def test_strategy_selector_exhausted_attempts_blocks_retry() -> None:
    analyzer = FailureAnalyzer()
    assessor = RiskAssessor()
    selector = StrategySelector(estimator=LogisticRecoveryEstimator())

    failure = analyzer.analyze(code="insufficient_funds")
    risk = assessor.assess(failure_category=failure.category, amount_minor=5000, prior_attempts=4)

    result = selector.select_strategy(
        amount_minor=5000,
        failure=failure,
        risk=risk,
        prior_attempts=4,
    )
    assert result.selected_strategy != RecoveryStrategy.RETRY_LATER
    retry_cand = next(c for c in result.candidates if c.strategy == RecoveryStrategy.RETRY_LATER)
    assert retry_cand.permitted is False
    assert any("quota" in r.lower() for r in retry_cand.reasons)


# ==============================================================================
# 5. Explanation Service Unit Tests
# ==============================================================================

def test_explanation_service_generates_verifiable_evidence() -> None:
    analyzer = FailureAnalyzer()
    assessor = RiskAssessor()
    failure = analyzer.analyze(code="insufficient_funds", message="Balance error")
    risk = assessor.assess(failure_category=failure.category, amount_minor=7500, prior_attempts=1)

    exp = ExplanationService.generate_explanation(
        strategy=RecoveryStrategy.RETRY_LATER,
        failure=failure,
        risk=risk,
        amount_minor=7500,
        currency="USD",
        prior_attempts=1,
        model_version="deterministic-logistic-v1",
    )
    assert "retry" in exp.summary.lower()
    assert any("USD 75.00" in ev for ev in exp.supporting_evidence)
    assert any("INSUFFICIENT_FUNDS" in ev for ev in exp.supporting_evidence)
    assert len(exp.limitations) > 0


# ==============================================================================
# 6. Intelligence Orchestrator Integration Tests
# ==============================================================================

def test_orchestrator_generates_and_persists_recommendation(db_session, sample_case) -> None:
    orchestrator = IntelligenceOrchestrator(db_session)

    rec = orchestrator.generate_recommendation(sample_case.id, current_user_id="operator_007")

    assert rec.case_id == sample_case.id
    assert rec.decision_version == 1
    assert rec.recommended_strategy == "RETRY_LATER"
    assert rec.action_type == ActionType.RETRY_PAYMENT
    assert rec.validation_status == DecisionValidationStatus.NOT_VALIDATED
    assert rec.confidence is not None and rec.confidence > 0
    assert len(rec.candidate_strategies) > 0

    # Verify AgentDecision persistence
    dec = orchestrator.decision_repo.find_latest_by_case(sample_case.id)
    assert dec is not None
    assert dec.decision_version == 1
    assert dec.action_type == ActionType.RETRY_PAYMENT
    assert dec.validation_status == DecisionValidationStatus.NOT_VALIDATED

    # Verify Audit Event recorded
    audit_events = orchestrator.audit_repo.find_by_case(sample_case.id)
    rec_event = next((e for e in audit_events if e.event_type == "RECOMMENDATION_GENERATED"), None)
    assert rec_event is not None
    assert rec_event.actor_id == "operator_007"
    assert rec_event.correlation_id == str(dec.id)

    # Verify State Transition DETECTED -> AWAITING_DECISION
    assert sample_case.state == RecoveryCaseState.AWAITING_DECISION

    # Second generation increments version
    rec2 = orchestrator.generate_recommendation(sample_case.id, current_user_id="operator_007")
    assert rec2.decision_version == 2
    assert rec2.id != rec.id


def test_orchestrator_history_and_latest_retrieval(db_session, sample_case) -> None:
    orchestrator = IntelligenceOrchestrator(db_session)
    rec1 = orchestrator.generate_recommendation(sample_case.id)
    rec2 = orchestrator.generate_recommendation(sample_case.id)

    latest = orchestrator.get_latest_recommendation(sample_case.id)
    assert latest is not None
    assert latest.decision_version == 2
    assert latest.id == rec2.id

    history = orchestrator.get_recommendation_history(sample_case.id)
    assert len(history) == 2
    assert history[0].decision_version == 1
    assert history[1].decision_version == 2


def test_orchestrator_dry_run_simulation_preview(db_session) -> None:
    orchestrator = IntelligenceOrchestrator(db_session)
    preview_req = DecisionPreviewRequestDTO(
        amount_minor=4500,
        currency="USD",
        failure_code="card_expired",
        failure_message="Validity period ended",
        prior_attempts=0,
        customer_success_rate=0.7,
        alternate_method_available=True,
    )
    rec = orchestrator.preview_recommendation(preview_req)
    assert rec.recommended_strategy == "UPDATE_PAYMENT_METHOD"
    assert rec.action_type == ActionType.SEND_REMINDER
    assert rec.validation_status == DecisionValidationStatus.NOT_VALIDATED


# ==============================================================================
# 7. REST API Endpoints & RBAC Security Tests
# ==============================================================================

def test_api_generate_recommendation_operator_success(client, sample_case, operator_token) -> None:
    headers = {"Authorization": f"Bearer {operator_token}"}
    response = client.post(f"/api/v1/cases/{sample_case.id}/recommendations", headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["case_id"] == str(sample_case.id)
    assert data["recommended_strategy"] == "RETRY_LATER"
    assert data["validation_status"] == "not_validated"
    assert data["risk_band"] in ("low", "medium", "high")


def test_api_get_latest_and_history_recommendation(client, sample_case, operator_token, auditor_token) -> None:
    op_headers = {"Authorization": f"Bearer {operator_token}"}
    aud_headers = {"Authorization": f"Bearer {auditor_token}"}

    # Generate first
    client.post(f"/api/v1/cases/{sample_case.id}/recommendations", headers=op_headers)

    # Auditor retrieves latest
    res_latest = client.get(f"/api/v1/cases/{sample_case.id}/recommendations/latest", headers=aud_headers)
    assert res_latest.status_code == 200
    assert res_latest.json()["case_id"] == str(sample_case.id)

    # Auditor retrieves history
    res_hist = client.get(f"/api/v1/cases/{sample_case.id}/recommendations", headers=aud_headers)
    assert res_hist.status_code == 200
    assert len(res_hist.json()) == 1


def test_api_recommendation_unauthorized_and_forbidden(client, sample_case, ingestor_token) -> None:
    # 401 Unauthorized when missing token
    res_unauth = client.post(f"/api/v1/cases/{sample_case.id}/recommendations")
    assert res_unauth.status_code == 401

    # 403 Forbidden for Ingestor role
    res_forbid = client.post(
        f"/api/v1/cases/{sample_case.id}/recommendations",
        headers={"Authorization": f"Bearer {ingestor_token}"},
    )
    assert res_forbid.status_code == 403


def test_api_nonexistent_case_returns_404(client, operator_token) -> None:
    random_id = uuid4()
    headers = {"Authorization": f"Bearer {operator_token}"}
    res = client.post(f"/api/v1/cases/{random_id}/recommendations", headers=headers)
    assert res.status_code == 404


def test_api_decision_preview_dry_run(client) -> None:
    payload = {
        "amount_minor": 9999,
        "currency": "EUR",
        "failure_code": "card_expired",
        "failure_message": "Card past expiry",
        "prior_attempts": 0,
        "customer_success_rate": 0.5,
        "alternate_method_available": True,
        "unusual_velocity": False,
        "customer_restricted": False,
    }
    response = client.post("/api/v1/recovery/decision-preview", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "decision_preview"
    assert data["recommendation"]["action"] in ("send_reminder", "retry_payment", "request_operator_review", "stop")


# ==============================================================================
# 8. Financial Safety & Immutability Invariant Tests
# ==============================================================================

def test_financial_safety_recommendation_never_mutates_payment(db_session, sample_case) -> None:
    """Critical verification: AI recommendation generation must NEVER mutate authoritative payment records."""
    orchestrator = IntelligenceOrchestrator(db_session)

    txn_before = sample_case.trigger_transaction
    assert txn_before.status == TransactionStatus.FAILED

    rec = orchestrator.generate_recommendation(sample_case.id)
    assert rec.recommended_strategy == "RETRY_LATER"

    # Verify authoritative transaction status remains strictly FAILED
    db_session.refresh(txn_before)
    assert txn_before.status == TransactionStatus.FAILED

    # Verify no recovery attempt was executed
    assert len(sample_case.attempts) == 0

    # Verify policy validation remains pending
    dec = orchestrator.decision_repo.find_latest_by_case(sample_case.id)
    assert dec.validation_status == DecisionValidationStatus.NOT_VALIDATED
