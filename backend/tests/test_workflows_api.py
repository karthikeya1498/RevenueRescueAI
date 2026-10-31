"""REST API tests for Workflows, Execution, and Reconciliation endpoints.

Author: Karthikeya
Architectural layer: tests / API routes.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, utc_now
from app.core.enums import (
    ActionType,
    ActorType,
    ConsentStatus,
    ConsentType,
    CustomerStatus,
    DecisionValidationStatus,
    PolicyDecisionStatus,
    RecoveryCaseState,
    TransactionStatus,
    UserRole,
    UserStatus,
)
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.domain import (
    AgentDecision,
    Customer,
    CustomerConsent,
    PolicyDecision,
    RecoveryCase,
    Transaction,
    User,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(conn, _rec):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def operator_token(db_session):
    user = User(
        email="operator@revenuerescue.ai",
        name="Operator Karthik",
        password_hash=hash_password("SafePassword123!"),
        role=UserRole.OPERATOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(user.id, user.email, user.role.value)


def seed_case_and_decision(db_session):
    now = utc_now()
    cust = Customer(
        id=uuid4(),
        provider="razorpay",
        external_customer_id="cust_api_100",
        email="api@example.com",
        status=CustomerStatus.ACTIVE,
    )
    db_session.add(cust)
    db_session.flush()

    consent = CustomerConsent(
        id=uuid4(),
        customer_id=cust.id,
        consent_type=ConsentType.RECURRING_BILLING,
        status=ConsentStatus.GRANTED,
        granted_at=now - timedelta(days=1),
        source="checkout",
    )
    db_session.add(consent)
    db_session.flush()

    txn = Transaction(
        id=uuid4(),
        customer_id=cust.id,
        provider="razorpay",
        external_transaction_id="txn_api_100",
        amount_minor=250000,
        currency="INR",
        status=TransactionStatus.FAILED,
        occurred_at=now,
    )
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(
        id=uuid4(),
        customer_id=cust.id,
        trigger_transaction_id=txn.id,
        case_key=f"case_{uuid4().hex[:8]}",
        state=RecoveryCaseState.ACTION_PENDING,
        priority=100,
        opened_at=now,
        last_state_changed_at=now,
        version=1,
    )
    db_session.add(case)
    db_session.flush()

    rec = AgentDecision(
        id=uuid4(),
        case_id=case.id,
        decision_version=1,
        action_type=ActionType.RETRY_PAYMENT,
        reason_code="RETRY_RECOMMENDED",
        validation_status=DecisionValidationStatus.VALID,
    )
    db_session.add(rec)
    db_session.flush()

    policy_dec = PolicyDecision(
        id=uuid4(),
        case_id=case.id,
        recommendation_id=rec.id,
        proposed_action=ActionType.RETRY_PAYMENT,
        decision_status=PolicyDecisionStatus.APPROVED,
        policy_version="1.0.0",
        rule_results_json=[],
        reasons_json=["Approved by policy"],
        actor_type=ActorType.SYSTEM,
        case_version=1,
        evaluated_at=now,
    )
    db_session.add(policy_dec)
    db_session.commit()

    return cust, txn, case, policy_dec


def test_api_create_and_execute_workflow(client, db_session, operator_token):
    """Verifies workflow creation and execution via REST endpoints."""
    _, _, case, policy_dec = seed_case_and_decision(db_session)
    headers = {"Authorization": f"Bearer {operator_token}"}

    # 1. Create workflow
    create_resp = client.post(
        "/api/v1/workflows",
        json={"policy_decision_id": str(policy_dec.id), "cooldown_hours": 0},
        headers=headers,
    )
    assert create_resp.status_code == 201
    wf_data = create_resp.json()
    wf_id = wf_data["id"]
    assert wf_data["strategy"] == "RETRY_PAYMENT"
    assert len(wf_data["steps"]) == 4

    # 2. Execute workflow
    exec_resp = client.post(
        f"/api/v1/workflows/{wf_id}/execute",
        json={"execute_all": True},
        headers=headers,
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["steps"][2]["status"] == "completed"  # Dispatch retry step completed

    # 3. Retrieve workflow by ID
    get_resp = client.get(f"/api/v1/workflows/{wf_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == wf_id

    # 4. List case workflows
    list_resp = client.get(f"/api/v1/cases/{case.id}/workflows", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_api_reconcile_case(client, db_session, operator_token):
    """Verifies reconciliation endpoint matches and synchronizes state."""
    _, _, case, _ = seed_case_and_decision(db_session)
    headers = {"Authorization": f"Bearer {operator_token}"}

    resp = client.post(
        "/api/v1/reconciliation/reconcile-case",
        json={"case_id": str(case.id), "auto_resolve": True},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == str(case.id)
    assert "status" in data
    assert "discrepancies" in data
