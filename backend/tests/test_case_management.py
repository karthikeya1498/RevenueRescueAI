"""Comprehensive automated test suite for Phase 2.7: Recovery Case Management Engine.

Author: Karthikeya
Architectural layer: integration & unit test suite.

Verifies:
1. Automatic case creation from eligible revenue-risk events.
2. Case matching, deduplication, and single-case-per-problem invariants.
3. Payment success auto-resolution and terminal state immutability.
4. Deterministic operational queue prioritization (1-1000) and explainability.
5. Independent revenue risk classification (HIGH, MEDIUM, LOW).
6. Finite-state machine transitions, validation, and audit recording.
7. REST APIs (Listing, Detail, Patch, Transition, History, Events).
8. RBAC security enforcement and forbidden role rejections.
9. Dashboard integration with truthful financial calculations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import (
    ActorType,
    CanonicalEventType,
    CustomerStatus,
    RecoveryCaseState,
    RiskTier,
    TransactionStatus,
    UserRole,
    UserStatus,
)
from app.core.errors import (
    EntityNotFoundException,
    InvalidStateTransitionException,
)
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.domain import Customer, RecoveryCase, Transaction, User
from app.schemas.events import CanonicalEventDTO, EventIngestRequestDTO
from app.schemas.recovery_cases import (
    CaseStateTransitionDTO,
    RecoveryCaseCreateDTO,
    RecoveryCaseUpdateDTO,
)
from app.services.case_prioritizer import CasePrioritizer
from app.services.case_risk_classifier import CaseRiskClassifier
from app.services.dashboard_service import DashboardService
from app.services.event_service import EventService
from app.services.event_to_case_engine import EventToCaseEngine
from app.services.recovery_case_service import RecoveryCaseService


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
    """Create an active operator user and issue an access token."""
    user = User(
        id=uuid4(),
        email="operator@revenuerescue.ai",
        name="Test Operator",
        password_hash=hash_password("OperatorPass123!"),
        role=UserRole.OPERATOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(user_id=user.id, email=user.email, role=UserRole.OPERATOR)


@pytest.fixture
def auditor_token(db_session):
    """Create an active auditor user and issue an access token."""
    user = User(
        id=uuid4(),
        email="auditor@revenuerescue.ai",
        name="Test Auditor",
        password_hash=hash_password("AuditorPass123!"),
        role=UserRole.AUDITOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(user_id=user.id, email=user.email, role=UserRole.AUDITOR)


@pytest.fixture
def ingestor_token(db_session):
    """Create an active ingestor user and issue an access token."""
    user = User(
        id=uuid4(),
        email="ingestor@revenuerescue.ai",
        name="Test Ingestor",
        password_hash=hash_password("IngestorPass123!"),
        role=UserRole.INGESTOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(user_id=user.id, email=user.email, role=UserRole.INGESTOR)


# ==============================================================================
# SECTION A: Automatic Case Creation Tests
# ==============================================================================

def test_payment_failed_automatically_creates_case(db_session):
    """A valid PAYMENT_FAILED event creates a structured RecoveryCase in DETECTED state."""
    event_service = EventService(db_session)
    now = datetime.now(timezone.utc)

    req = EventIngestRequestDTO(
        event_id="evt_fail_101",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-1001",
        payment_reference="PAY-2001",
        amount_minor=249900,  # ₹2,499.00
        currency="INR",
        failure_code="insufficient_funds",
        failure_message="Card has insufficient funds",
        occurred_at=now,
    )

    response = event_service.ingest_canonical_event(req)
    assert response.accepted is True
    assert response.duplicate is False
    assert response.case_id is not None
    assert response.case_key == "CASE-TX-stripe-PAY-2001"

    # Query created case
    case_service = RecoveryCaseService(db_session)
    case = case_service.get_case(UUID(response.case_id))
    assert case.state == RecoveryCaseState.DETECTED
    assert case.case_key == "CASE-TX-stripe-PAY-2001"
    assert case.priority > 0
    assert case.metadata["risk_tier"] in ("high", "medium", "low")
    assert case.metadata["source_event_id"] == "evt_fail_101"

    # Verify audit event and state transition
    timeline = case_service.get_case_timeline(UUID(response.case_id))
    assert len(timeline) >= 1
    assert timeline[0].event_type == "CASE_OPENED"
    assert timeline[0].to_state == RecoveryCaseState.DETECTED


def test_subscription_payment_failed_creates_case_with_billing_period(db_session):
    """SUBSCRIPTION_PAYMENT_FAILED maps to a billing-period qualified case key."""
    event_service = EventService(db_session)
    now = datetime.now(timezone.utc)

    req = EventIngestRequestDTO(
        event_id="evt_sub_fail_202",
        event_type=CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-SUB-99",
        subscription_reference="sub_prod_premium",
        amount_minor=500000,  # $5,000.00
        currency="USD",
        failure_code="card_expired",
        failure_message="Card expired",
        occurred_at=now,
        metadata={"billing_period": "2026-10"},
    )

    response = event_service.ingest_canonical_event(req)
    assert response.accepted is True
    assert response.case_id is not None
    assert response.case_key == "CASE-SUB-sub_prod_premium-2026-10"

    case = RecoveryCaseService(db_session).get_case(UUID(response.case_id))
    assert case.metadata["risk_tier"] == "high"  # High exposure + expired card on sub
    assert case.priority <= 100  # High exposure escalates priority (lower integer)


def test_checkout_abandoned_and_invoice_overdue_create_cases(db_session):
    """CHECKOUT_ABANDONED and INVOICE_OVERDUE events create appropriate cases."""
    event_service = EventService(db_session)

    # 1. Checkout Abandoned
    chk_req = EventIngestRequestDTO(
        event_id="evt_chk_301",
        event_type=CanonicalEventType.CHECKOUT_ABANDONED.value,
        provider="stripe",
        customer_reference="CUST-CHK-1",
        checkout_session_id="cs_test_abc123",
        amount_minor=12000,
        currency="USD",
        occurred_at=datetime.now(timezone.utc),
    )
    chk_res = event_service.ingest_canonical_event(chk_req)
    assert chk_res.case_key == "CASE-CHK-cs_test_abc123"

    # 2. Invoice Overdue
    inv_req = EventIngestRequestDTO(
        event_id="evt_inv_302",
        event_type=CanonicalEventType.INVOICE_OVERDUE.value,
        provider="stripe",
        customer_reference="CUST-INV-1",
        invoice_reference="in_enterprise_889",
        amount_minor=1500000,
        currency="USD",
        occurred_at=datetime.now(timezone.utc),
    )
    inv_res = event_service.ingest_canonical_event(inv_req)
    assert inv_res.case_key == "CASE-INV-in_enterprise_889"


# ==============================================================================
# SECTION B: Case Matching, Deduplication & Resolution Tests
# ==============================================================================

def test_exact_duplicate_event_does_not_create_duplicate_case(db_session):
    """Identical duplicate events are suppressed; no second case is created."""
    event_service = EventService(db_session)
    now = datetime.now(timezone.utc)

    req = EventIngestRequestDTO(
        event_id="evt_dup_test_1",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-DUP",
        payment_reference="PAY-DUP-1",
        amount_minor=5000,
        currency="USD",
        failure_code="insufficient_funds",
        occurred_at=now,
    )

    res1 = event_service.ingest_canonical_event(req)
    assert res1.duplicate is False
    first_case_id = res1.case_id

    # Ingest identical event again
    res2 = event_service.ingest_canonical_event(req)
    assert res2.duplicate is True
    assert res2.status == "DUPLICATE"

    # Verify only 1 recovery case exists in database
    all_cases = db_session.query(RecoveryCase).all()
    assert len(all_cases) == 1
    assert str(all_cases[0].id) == first_case_id


def test_subsequent_failure_event_updates_existing_case(db_session):
    """A subsequent failure event for the same payment reference updates the open case."""
    event_service = EventService(db_session)
    base_time = datetime.now(timezone.utc) - timedelta(hours=2)

    # Event 1: Initial failure
    req1 = EventIngestRequestDTO(
        event_id="evt_multi_1",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-MULTI",
        payment_reference="PAY-MULTI-1",
        amount_minor=75000,
        currency="USD",
        failure_code="insufficient_funds",
        occurred_at=base_time,
    )
    res1 = event_service.ingest_canonical_event(req1)
    case_id = UUID(res1.case_id)

    # Event 2: Subsequent failure on same payment intent (different event ID)
    req2 = EventIngestRequestDTO(
        event_id="evt_multi_2",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-MULTI",
        payment_reference="PAY-MULTI-1",
        amount_minor=75000,
        currency="USD",
        failure_code="card_declined",
        occurred_at=base_time + timedelta(minutes=30),
    )
    res2 = event_service.ingest_canonical_event(req2)
    assert res2.duplicate is False
    assert res2.case_id == str(case_id)

    # Verify only 1 case exists, but failure_count is 2
    case = RecoveryCaseService(db_session).get_case(case_id)
    assert case.metadata["failure_count"] == 2
    assert case.metadata["latest_failure_event_id"] == "evt_multi_2"

    timeline = RecoveryCaseService(db_session).get_case_timeline(case_id)
    event_types = [t.event_type for t in timeline]
    assert "CASE_OPENED" in event_types
    assert "CASE_UPDATED" in event_types


def test_different_payments_for_same_customer_create_separate_cases(db_session):
    """Distinct payment failures for the same customer generate independent recovery cases."""
    event_service = EventService(db_session)
    now = datetime.now(timezone.utc)

    req1 = EventIngestRequestDTO(
        event_id="evt_sep_1",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-COMMON",
        payment_reference="PAY-INV-101",
        amount_minor=10000,
        currency="USD",
        failure_code="insufficient_funds",
        occurred_at=now,
    )
    res1 = event_service.ingest_canonical_event(req1)

    req2 = EventIngestRequestDTO(
        event_id="evt_sep_2",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-COMMON",
        payment_reference="PAY-INV-102",
        amount_minor=20000,
        currency="USD",
        failure_code="card_declined",
        occurred_at=now,
    )
    res2 = event_service.ingest_canonical_event(req2)

    assert res1.case_id != res2.case_id
    assert res1.case_key != res2.case_key
    assert len(db_session.query(RecoveryCase).all()) == 2


def test_payment_succeeded_resolves_active_recovery_case(db_session):
    """PAYMENT_SUCCEEDED transitions matching open case to RECOVERED and sets closed_at."""
    event_service = EventService(db_session)
    base_time = datetime.now(timezone.utc) - timedelta(hours=3)

    # 1. Ingest failure -> Case created
    fail_req = EventIngestRequestDTO(
        event_id="evt_res_fail",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-RESOLVE",
        payment_reference="PAY-RECOVER-99",
        amount_minor=149900,
        currency="INR",
        failure_code="insufficient_funds",
        occurred_at=base_time,
    )
    fail_res = event_service.ingest_canonical_event(fail_req)
    case_id = UUID(fail_res.case_id)

    # 2. Ingest success for same payment reference
    succ_req = EventIngestRequestDTO(
        event_id="evt_res_succ",
        event_type=CanonicalEventType.PAYMENT_SUCCEEDED.value,
        provider="stripe",
        customer_reference="CUST-RESOLVE",
        payment_reference="PAY-RECOVER-99",
        amount_minor=149900,
        currency="INR",
        occurred_at=base_time + timedelta(hours=1),
    )
    succ_res = event_service.ingest_canonical_event(succ_req)
    assert succ_res.case_id == str(case_id)

    # Verify case state is RECOVERED
    case = RecoveryCaseService(db_session).get_case(case_id)
    assert case.state == RecoveryCaseState.RECOVERED
    assert case.closed_at is not None

    # Verify timeline records CASE_RECOVERED
    timeline = RecoveryCaseService(db_session).get_case_timeline(case_id)
    assert timeline[-1].event_type == "CASE_RECOVERED"
    assert timeline[-1].to_state == RecoveryCaseState.RECOVERED


def test_terminal_case_preserves_historical_resolution(db_session):
    """A late failure event arriving for an already RECOVERED case preserves history."""
    event_service = EventService(db_session)
    base_time = datetime.now(timezone.utc) - timedelta(hours=4)

    # Create and resolve case
    fail_req = EventIngestRequestDTO(
        event_id="evt_term_1",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-TERM",
        payment_reference="PAY-TERM-1",
        amount_minor=5000,
        currency="USD",
        failure_code="insufficient_funds",
        occurred_at=base_time,
    )
    res = event_service.ingest_canonical_event(fail_req)
    case_id = UUID(res.case_id)

    succ_req = EventIngestRequestDTO(
        event_id="evt_term_2",
        event_type=CanonicalEventType.PAYMENT_SUCCEEDED.value,
        provider="stripe",
        customer_reference="CUST-TERM",
        payment_reference="PAY-TERM-1",
        amount_minor=5000,
        currency="USD",
        occurred_at=base_time + timedelta(hours=1),
    )
    event_service.ingest_canonical_event(succ_req)

    # Now simulate delayed out-of-order failure arriving later
    late_fail_req = EventIngestRequestDTO(
        event_id="evt_term_3_late",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        customer_reference="CUST-TERM",
        payment_reference="PAY-TERM-1",
        amount_minor=5000,
        currency="USD",
        failure_code="insufficient_funds",
        occurred_at=base_time + timedelta(hours=2),
    )
    late_res = event_service.ingest_canonical_event(late_fail_req)

    # Assert historical resolution was preserved
    case = RecoveryCaseService(db_session).get_case(case_id)
    assert case.state == RecoveryCaseState.RECOVERED


# ==============================================================================
# SECTION C: Prioritization and Risk Classification Tests
# ==============================================================================

def test_case_prioritizer_deterministic_rules():
    """Verify deterministic priority scoring and explainability."""
    # 1. High exposure (>= 500,000 minor = $5,000)
    p_high = CasePrioritizer.calculate_priority(
        amount_minor=600000,
        currency="USD",
        failure_code="insufficient_funds",
        event_type="PAYMENT_FAILED",
    )
    # Base 100 - 50 (exposure) - 20 (transient) = 30
    assert p_high.priority == 30
    assert "Major exposure" in p_high.reason
    assert "balance shortage" in p_high.reason

    # 2. Fraud decline de-prioritizes automated queue (+50 adjustment)
    p_fraud = CasePrioritizer.calculate_priority(
        amount_minor=10000,
        currency="USD",
        failure_code="fraud_suspected",
        event_type="PAYMENT_FAILED",
    )
    assert p_fraud.priority >= 100
    assert "fraud" in p_fraud.reason.lower()

    # 3. Priority clamped in [1, 1000]
    p_clamped = CasePrioritizer.calculate_priority(
        amount_minor=50_000_000,
        currency="USD",
        failure_code="insufficient_funds",
        event_type="PAYMENT_FAILED",
        opened_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    assert 1 <= p_clamped.priority <= 1000


def test_case_risk_classifier_tiers():
    """Verify independent risk classification (HIGH, MEDIUM, LOW)."""
    # 1. High risk: recurring subscription failure with high exposure
    r1 = CaseRiskClassifier.classify_risk(
        amount_minor=600000,
        currency="USD",
        failure_code="insufficient_funds",
        event_type="SUBSCRIPTION_PAYMENT_FAILED",
    )
    assert r1.risk_tier == RiskTier.HIGH
    assert "subscription" in r1.reason.lower()

    # 2. High risk: Fraud suspected
    r_fraud = CaseRiskClassifier.classify_risk(
        amount_minor=10000,
        currency="USD",
        failure_code="fraud_suspected",
        event_type="PAYMENT_FAILED",
    )
    assert r_fraud.risk_tier == RiskTier.HIGH

    # 3. Low risk: small transaction, transient network error
    r_low = CaseRiskClassifier.classify_risk(
        amount_minor=1500,  # $15
        currency="USD",
        failure_code="processing_error",
        event_type="PAYMENT_FAILED",
    )
    assert r_low.risk_tier == RiskTier.LOW


# ==============================================================================
# SECTION D: State Machine and Lifecycle Tests
# ==============================================================================

def test_case_lifecycle_state_transitions(db_session):
    """Enforce permitted finite-state machine transitions and reject invalid jumps."""
    service = RecoveryCaseService(db_session)
    now = datetime.now(timezone.utc)

    # Setup customer and tx
    cust = Customer(id=uuid4(), provider="test", external_customer_id="c_fsm", status=CustomerStatus.ACTIVE)
    tx = Transaction(
        id=uuid4(),
        customer_id=cust.id,
        provider="test",
        external_transaction_id="tx_fsm",
        amount_minor=10000,
        currency="USD",
        status=TransactionStatus.FAILED,
        occurred_at=now,
    )
    db_session.add_all([cust, tx])
    db_session.commit()

    # Open case
    created = service.create_case(
        RecoveryCaseCreateDTO(customer_id=cust.id, trigger_transaction_id=tx.id, priority=50)
    )
    case_id = created.id
    assert created.state == RecoveryCaseState.DETECTED

    # 1. Valid transition: DETECTED -> CONTEXT_READY
    t1 = service.transition_state(
        case_id,
        CaseStateTransitionDTO(
            to_state=RecoveryCaseState.CONTEXT_READY,
            reason_code="CONTEXT_ASSEMBLED",
            actor_type=ActorType.SYSTEM,
            correlation_id="corr_1",
        ),
    )
    assert t1.state == RecoveryCaseState.CONTEXT_READY

    # 2. Valid transition: CONTEXT_READY -> AWAITING_DECISION
    t2 = service.transition_state(
        case_id,
        CaseStateTransitionDTO(
            to_state=RecoveryCaseState.AWAITING_DECISION,
            reason_code="READY_FOR_RECOMMENDATION",
            actor_type=ActorType.SYSTEM,
            correlation_id="corr_2",
        ),
    )
    assert t2.state == RecoveryCaseState.AWAITING_DECISION

    # 3. Identity transition rejected: AWAITING_DECISION -> AWAITING_DECISION
    with pytest.raises(InvalidStateTransitionException):
        service.transition_state(
            case_id,
            CaseStateTransitionDTO(
                to_state=RecoveryCaseState.AWAITING_DECISION,
                reason_code="REDUNDANT",
                actor_type=ActorType.OPERATOR,
                correlation_id="corr_3",
            ),
        )

    # 4. Transition to terminal: AWAITING_DECISION -> STOPPED
    t_term = service.transition_state(
        case_id,
        CaseStateTransitionDTO(
            to_state=RecoveryCaseState.STOPPED,
            reason_code="OPERATOR_CANCELLED",
            actor_type=ActorType.OPERATOR,
            correlation_id="corr_4",
        ),
    )
    assert t_term.state == RecoveryCaseState.STOPPED
    assert t_term.closed_at is not None

    # 5. Terminal state immutability: Cannot transition from STOPPED
    with pytest.raises(InvalidStateTransitionException):
        service.transition_state(
            case_id,
            CaseStateTransitionDTO(
                to_state=RecoveryCaseState.DETECTED,
                reason_code="REOPEN_ATTEMPT",
                actor_type=ActorType.OPERATOR,
                correlation_id="corr_5",
            ),
        )


# ==============================================================================
# SECTION E: Case Management REST APIs Tests
# ==============================================================================

def test_api_list_cases_with_filtering_and_search(client, operator_token, db_session):
    """GET /api/v1/cases supports state filtering, priority range, and search."""
    # Seed 2 cases via EventService
    ev_svc = EventService(db_session)
    now = datetime.now(timezone.utc)

    ev_svc.ingest_canonical_event(
        EventIngestRequestDTO(
            event_id="evt_api_1",
            event_type=CanonicalEventType.PAYMENT_FAILED.value,
            provider="stripe",
            customer_reference="CUST-SEARCH-ALPHA",
            payment_reference="PAY-ALPHA-01",
            amount_minor=500000,
            currency="USD",
            failure_code="insufficient_funds",
            occurred_at=now,
        )
    )

    ev_svc.ingest_canonical_event(
        EventIngestRequestDTO(
            event_id="evt_api_2",
            event_type=CanonicalEventType.PAYMENT_FAILED.value,
            provider="stripe",
            customer_reference="CUST-SEARCH-BETA",
            payment_reference="PAY-BETA-02",
            amount_minor=2000,
            currency="USD",
            failure_code="generic_decline",
            occurred_at=now,
        )
    )

    headers = {"Authorization": f"Bearer {operator_token}"}

    # 1. List all
    res = client.get("/api/v1/cases", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["pagination"]["total"] == 2
    assert len(data["items"]) == 2

    # 2. Filter by search "ALPHA"
    res_search = client.get("/api/v1/cases?search=ALPHA", headers=headers)
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["pagination"]["total"] == 1
    assert "ALPHA" in search_data["items"][0]["customer"]["external_customer_id"]

    # 3. Filter by state "detected"
    res_state = client.get("/api/v1/cases?state=detected", headers=headers)
    assert res_state.status_code == 200
    assert res_state.json()["pagination"]["total"] == 2


def test_api_get_case_detail_and_patch(client, operator_token, db_session):
    """GET and PATCH /api/v1/cases/{case_id}."""
    ev_svc = EventService(db_session)
    ingest_res = ev_svc.ingest_canonical_event(
        EventIngestRequestDTO(
            event_id="evt_detail_1",
            event_type=CanonicalEventType.PAYMENT_FAILED.value,
            provider="stripe",
            customer_reference="CUST-DETAIL",
            payment_reference="PAY-DETAIL-1",
            amount_minor=10000,
            currency="USD",
            failure_code="insufficient_funds",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    case_id = ingest_res.case_id
    headers = {"Authorization": f"Bearer {operator_token}"}

    # 1. GET detail
    res_get = client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert res_get.status_code == 200
    detail = res_get.json()
    assert detail["id"] == case_id
    assert detail["customer"]["external_customer_id"] == "CUST-DETAIL"
    assert detail["trigger_transaction"]["amount_minor"] == 10000

    # 2. PATCH priority and allowed metadata
    patch_payload = {
        "priority": 25,
        "metadata": {"operator_note": "Escalated for immediate review", "amount_minor": 999999},  # Protected key ignored
    }
    res_patch = client.patch(f"/api/v1/cases/{case_id}", json=patch_payload, headers=headers)
    assert res_patch.status_code == 200
    patched = res_patch.json()
    assert patched["priority"] == 25
    assert patched["metadata"]["operator_note"] == "Escalated for immediate review"
    # Verify financial key was protected
    assert patched["metadata"].get("amount_minor") != 999999


def test_api_get_case_history_and_events(client, auditor_token, db_session):
    """GET /api/v1/cases/{case_id}/history and /events."""
    ev_svc = EventService(db_session)
    ingest_res = ev_svc.ingest_canonical_event(
        EventIngestRequestDTO(
            event_id="evt_hist_1",
            event_type=CanonicalEventType.PAYMENT_FAILED.value,
            provider="stripe",
            customer_reference="CUST-HIST",
            payment_reference="PAY-HIST-1",
            amount_minor=10000,
            currency="USD",
            failure_code="insufficient_funds",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    case_id = ingest_res.case_id
    headers = {"Authorization": f"Bearer {auditor_token}"}

    # History timeline
    res_hist = client.get(f"/api/v1/cases/{case_id}/history", headers=headers)
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 1
    assert history[0]["event_type"] == "CASE_OPENED"

    # Gateway events
    res_events = client.get(f"/api/v1/cases/{case_id}/events", headers=headers)
    assert res_events.status_code == 200
    events = res_events.json()
    assert len(events) >= 1
    assert events[0]["external_event_id"] == "evt_hist_1"


def test_api_rbac_security_enforcement(client, ingestor_token, db_session):
    """Users without OPERATOR/ADMIN role are forbidden from mutating cases."""
    ev_svc = EventService(db_session)
    ingest_res = ev_svc.ingest_canonical_event(
        EventIngestRequestDTO(
            event_id="evt_rbac_1",
            event_type=CanonicalEventType.PAYMENT_FAILED.value,
            provider="stripe",
            customer_reference="CUST-RBAC",
            payment_reference="PAY-RBAC-1",
            amount_minor=10000,
            currency="USD",
            failure_code="insufficient_funds",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    case_id = ingest_res.case_id

    # Ingestor attempting to read cases -> 403 Forbidden
    headers = {"Authorization": f"Bearer {ingestor_token}"}
    res_list = client.get("/api/v1/cases", headers=headers)
    assert res_list.status_code == 403

    # Ingestor attempting to transition case -> 403 Forbidden
    transition_payload = {
        "to_state": "context_ready",
        "reason_code": "UNAUTHORIZED_ATTEMPT",
        "actor_type": "operator",
        "correlation_id": "corr_unauth",
    }
    res_trans = client.post(f"/api/v1/cases/{case_id}/transition", json=transition_payload, headers=headers)
    assert res_trans.status_code == 403


# ==============================================================================
# SECTION F: Dashboard Metrics Integration Tests
# ==============================================================================

def test_dashboard_metrics_reflect_real_case_data(db_session):
    """DashboardService calculates truthful KPIs based on ingested recovery cases."""
    dash_service = DashboardService(db_session)

    # 1. Empty state
    empty_metrics = dash_service.get_metrics()
    assert empty_metrics.total_at_risk_cases == 0
    assert empty_metrics.at_risk_revenue_minor == 0
    assert empty_metrics.recovered_revenue_minor == 0

    # 2. Ingest failure event ($100 = 10,000 minor)
    ev_svc = EventService(db_session)
    now = datetime.now(timezone.utc)
    ev_svc.ingest_canonical_event(
        EventIngestRequestDTO(
            event_id="evt_dash_1",
            event_type=CanonicalEventType.PAYMENT_FAILED.value,
            provider="stripe",
            customer_reference="CUST-DASH",
            payment_reference="PAY-DASH-1",
            amount_minor=10000,
            currency="USD",
            failure_code="insufficient_funds",
            occurred_at=now,
        )
    )

    m1 = dash_service.get_metrics()
    assert m1.total_at_risk_cases == 1
    assert m1.at_risk_revenue_minor == 10000
    assert m1.recovered_revenue_minor == 0
    assert m1.total_recovered_cases == 0

    # 3. Ingest success resolving the case
    ev_svc.ingest_canonical_event(
        EventIngestRequestDTO(
            event_id="evt_dash_2",
            event_type=CanonicalEventType.PAYMENT_SUCCEEDED.value,
            provider="stripe",
            customer_reference="CUST-DASH",
            payment_reference="PAY-DASH-1",
            amount_minor=10000,
            currency="USD",
            occurred_at=now + timedelta(minutes=10),
        )
    )

    m2 = dash_service.get_metrics()
    assert m2.total_at_risk_cases == 1
    assert m2.total_recovered_cases == 1
    assert m2.recovered_revenue_minor == 10000
    assert m2.case_recovery_rate_pct == "100.00%"
