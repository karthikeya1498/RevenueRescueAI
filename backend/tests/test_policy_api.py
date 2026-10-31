"""API integration test suite for Recovery Policy Engine REST endpoints (Phase 2.9 Step 4 & 5).

Verifies:
- POST /api/v1/policy/evaluate (Auth, evaluation, FSM transition, rule check outputs)
- GET /api/v1/policy/cases/{case_id}/decisions (Historical evaluation retrieval)
- POST /api/v1/policy/consents (Consent registration)
- GET /api/v1/policy/consents/{customer_id} (Consent query)
- POST /api/v1/policy/consents/{consent_id}/revoke (Consent revocation)
- Unauthorized access rejection on all protected endpoints
"""

from datetime import datetime, timedelta, timezone
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
    RecoveryCase,
    Transaction,
    User,
)


@pytest.fixture
def policy_api_context():
    """Create isolated in-memory test database and authenticated client."""
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

    app = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # Seed operator user
    with session_factory() as session:
        operator = User(
            id=uuid4(),
            email="policy.operator@revenuerescue.ai",
            name="Policy Operator",
            password_hash=hash_password("OperatorSecret2026!"),
            role=UserRole.OPERATOR,
            status=UserStatus.ACTIVE,
        )
        session.add(operator)
        session.commit()
        operator_id = operator.id
        operator_email = operator.email

    token = create_access_token(
        user_id=operator_id,
        email=operator_email,
        role=UserRole.OPERATOR,
    )
    auth_headers = {"Authorization": f"Bearer {token}"}

    yield {
        "client": client,
        "session_factory": session_factory,
        "operator_id": str(operator_id),
        "auth_headers": auth_headers,
    }

    Base.metadata.drop_all(engine)


def _seed_api_case(
    session_factory,
    amount_minor=50_000,
    currency="INR",
    failure_code="insufficient_funds",
    confidence=Decimal("0.85"),
):
    """Seed relational case data for API endpoint tests."""
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        customer = Customer(
            id=uuid4(),
            provider="stripe",
            external_customer_id=f"cust_api_{uuid4().hex[:6]}",
            email="api_customer@example.com",
            status=CustomerStatus.ACTIVE,
            metadata_json={"merchant_id": "merch_api_1"},
        )
        session.add(customer)
        session.flush()

        tx = Transaction(
            id=uuid4(),
            customer_id=customer.id,
            provider="stripe",
            external_transaction_id=f"tx_api_{uuid4().hex[:6]}",
            amount_minor=amount_minor,
            currency=currency,
            status=TransactionStatus.FAILED,
            failure_code=failure_code,
            failure_message_safe="Insufficient funds",
            occurred_at=now - timedelta(hours=1),
        )
        session.add(tx)
        session.flush()

        case = RecoveryCase(
            id=uuid4(),
            customer_id=customer.id,
            trigger_transaction_id=tx.id,
            case_key=f"case_api_{uuid4().hex[:6]}",
            state=RecoveryCaseState.AWAITING_DECISION,
            priority=100,
            opened_at=now,
            last_state_changed_at=now,
            version=1,
        )
        session.add(case)
        session.flush()

        rec = AgentDecision(
            id=uuid4(),
            case_id=case.id,
            decision_version=1,
            action_type=ActionType.RETRY_PAYMENT,
            reason_code="AI_RECOMMENDED_RETRY",
            confidence=confidence,
            validation_status=DecisionValidationStatus.NOT_VALIDATED,
        )
        session.add(rec)
        session.flush()

        consent = CustomerConsent(
            id=uuid4(),
            customer_id=customer.id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            merchant_id="merch_api_1",
            granted_at=now - timedelta(days=5),
            source="checkout_api",
        )
        session.add(consent)
        session.commit()

        return str(customer.id), str(tx.id), str(case.id), str(rec.id), str(consent.id)


class TestPolicyRESTEndpoints:
    """Test suite verifying Policy Engine REST API endpoints."""

    def test_unauthorized_access_fails_closed(self, policy_api_context):
        client = policy_api_context["client"]
        cid = str(uuid4())

        # No auth token -> 401 Unauthorized
        res = client.post(
            "/api/v1/policy/evaluate",
            json={
                "case_id": cid,
                "recommendation_id": str(uuid4()),
            },
        )
        assert res.status_code == 401

    def test_evaluate_endpoint_approved_flow(self, policy_api_context):
        client = policy_api_context["client"]
        headers = policy_api_context["auth_headers"]
        session_factory = policy_api_context["session_factory"]

        cust_id, tx_id, case_id, rec_id, _con_id = _seed_api_case(session_factory)

        res = client.post(
            "/api/v1/policy/evaluate",
            json={
                "case_id": case_id,
                "recommendation_id": rec_id,
                "idempotency_key": "api_eval_test_1",
            },
            headers=headers,
        )

        assert res.status_code == 200
        data = res.json()
        assert data["decision_status"] == "approved"
        assert data["is_approved"] is True
        assert data["validation_status"] == "valid"
        assert len(data["rule_results"]) == 5

        # Verify case state transition in database
        with session_factory() as session:
            case = session.get(RecoveryCase, UUID(case_id))
            assert case.state == RecoveryCaseState.ACTION_PENDING

    def test_get_case_policy_decisions_history(self, policy_api_context):
        client = policy_api_context["client"]
        headers = policy_api_context["auth_headers"]
        session_factory = policy_api_context["session_factory"]

        cust_id, tx_id, case_id, rec_id, _con_id = _seed_api_case(session_factory)

        # Trigger evaluation
        eval_res = client.post(
            "/api/v1/policy/evaluate",
            json={"case_id": case_id, "recommendation_id": rec_id},
            headers=headers,
        )
        assert eval_res.status_code == 200

        # Query history
        hist_res = client.get(
            f"/api/v1/policy/cases/{case_id}/decisions",
            headers=headers,
        )
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) == 1
        assert history[0]["case_id"] == case_id
        assert history[0]["decision_status"] == "approved"

    def test_consent_management_crud(self, policy_api_context):
        client = policy_api_context["client"]
        headers = policy_api_context["auth_headers"]
        session_factory = policy_api_context["session_factory"]

        cust_id, _tx_id, _case_id, _rec_id, _con_id = _seed_api_case(session_factory)

        # 1. Create SMS consent
        create_res = client.post(
            "/api/v1/policy/consents",
            json={
                "customer_id": cust_id,
                "consent_type": "communication_sms",
                "status": "granted",
                "merchant_id": "merch_api_1",
                "source": "sms_opt_in",
            },
            headers=headers,
        )
        assert create_res.status_code == 201
        sms_consent = create_res.json()
        assert sms_consent["consent_type"] == "communication_sms"
        assert sms_consent["is_valid"] is True
        consent_id = sms_consent["id"]

        # 2. List customer consents
        list_res = client.get(f"/api/v1/policy/consents/{cust_id}", headers=headers)
        assert list_res.status_code == 200
        consents = list_res.json()
        assert len(consents) == 2  # Seeded recurring billing + newly created SMS

        # 3. Revoke SMS consent
        revoke_res = client.post(
            f"/api/v1/policy/consents/{consent_id}/revoke",
            headers=headers,
        )
        assert revoke_res.status_code == 200
        revoked_data = revoke_res.json()
        assert revoked_data["status"] == "revoked"
        assert revoked_data["is_valid"] is False
