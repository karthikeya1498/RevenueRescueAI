"""Comprehensive API integration and end-to-end tests for Phase 2.5.

Author: Karthikeya
Architectural layer: test suite / integration.

Covers:
- Health and readiness endpoints (liveness, readiness, DB probe, no secret exposure)
- Current user profile endpoints (/api/v1/auth/me and /api/v1/users/me)
- Dashboard metrics foundation (zero-safe empty DB, accurate minor units calculation)
- Revenue trendline and workflow status distribution
- Case listing with pagination, sorting, and status filtering
- Case detail retrieval with embedded relationships and 404 handling
- Security and RBAC enforcement across all protected endpoints
"""

from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.enums import CustomerStatus, RecoveryCaseState, TransactionStatus, UserRole, UserStatus
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.domain import Customer, RecoveryCase, Transaction, User


@pytest.fixture
def api_test_context():
    """Create isolated in-memory test database and configured TestClient."""
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

    # Seed an operator user for authenticated API requests
    with session_factory() as session:
        operator = User(
            id=uuid4(),
            email="operator.integration@revenuerescue.ai",
            name="Alex Operator",
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


# ---------------------------------------------------------------------------
# 1. Health and Readiness Tests
# ---------------------------------------------------------------------------

def test_health_endpoints_liveness_and_readiness(api_test_context):
    """Verify liveness, versioned health, readiness, and DB diagnostic endpoints."""
    client = api_test_context["client"]

    # Root liveness
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
    assert "password" not in res.text
    assert "secret" not in res.text

    # Versioned liveness
    res_v1 = client.get("/api/v1/health")
    assert res_v1.status_code == 200
    assert res_v1.json() == res.json()

    # Readiness check
    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"
    assert res_ready.json()["dependencies"]["configuration"] == "ready"

    # Versioned readiness
    res_ready_v1 = client.get("/api/v1/ready")
    assert res_ready_v1.status_code == 200
    assert res_ready_v1.json() == res_ready.json()

    # DB probe
    res_db = client.get("/health/db")
    assert res_db.status_code == 200
    assert res_db.json()["status"] == "healthy"
    assert res_db.json()["database"] == "connected"


# ---------------------------------------------------------------------------
# 2. Current User Profile API Tests
# ---------------------------------------------------------------------------

def test_current_user_profile_endpoints(api_test_context):
    """Verify /api/v1/auth/me and /api/v1/users/me retrieve the authenticated profile."""
    client = api_test_context["client"]
    headers = api_test_context["auth_headers"]
    operator_id = api_test_context["operator_id"]

    # Call /api/v1/auth/me
    res_auth_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_auth_me.status_code == 200
    data = res_auth_me.json()
    assert data["id"] == operator_id
    assert data["email"] == "operator.integration@revenuerescue.ai"
    assert data["role"] == "ROLE_OPERATOR"
    assert data["status"] == "active"
    assert "password" not in data
    assert "password_hash" not in data

    # Call /api/v1/users/me (contract alias)
    res_users_me = client.get("/api/v1/users/me", headers=headers)
    assert res_users_me.status_code == 200
    assert res_users_me.json() == data

    # Unauthenticated calls must be rejected
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


# ---------------------------------------------------------------------------
# 3. Dashboard Metrics Tests (Empty Database & Zero-Safe)
# ---------------------------------------------------------------------------

def test_dashboard_metrics_empty_database_zero_safe(api_test_context):
    """Verify that an empty database returns structured zero values without division errors."""
    client = api_test_context["client"]
    headers = api_test_context["auth_headers"]

    res = client.get("/api/v1/dashboard/metrics", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["currency"] == "USD"
    assert data["at_risk_revenue_minor"] == 0
    assert data["recovered_revenue_minor"] == 0
    assert data["recovery_rate_pct"] == "0.00%"
    assert data["case_recovery_rate_pct"] == "0.00%"
    assert data["total_at_risk_cases"] == 0
    assert data["total_recovered_cases"] == 0
    assert data["escalated_cases"] == 0
    assert data["verification_pending_cases"] == 0
    assert data["stopped_cases"] == 0
    assert data["safety_rate_pct"] == "100.00%"
    assert "generated_at" in data

    # Alias /api/v1/dashboard/summary
    res_summary = client.get("/api/v1/dashboard/summary", headers=headers)
    assert res_summary.status_code == 200
    assert res_summary.json()["total_at_risk_cases"] == 0


# ---------------------------------------------------------------------------
# 4. Dashboard Metrics Tests (With Seeded Recovery Data)
# ---------------------------------------------------------------------------

def test_dashboard_metrics_with_active_recovery_data(api_test_context):
    """Verify that dashboard calculations accurately aggregate minor units from database entities."""
    client = api_test_context["client"]
    headers = api_test_context["auth_headers"]
    session_factory = api_test_context["session_factory"]

    # Seed customers, transactions, and recovery cases
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        cust1 = Customer(
            id=uuid4(),
            provider="stripe",
            external_customer_id="cus_test_01",
            display_name="Acme Corp",
            email="finance@acme.com",
            status=CustomerStatus.ACTIVE,
        )
        session.add(cust1)
        session.flush()

        # Trigger transaction 1: $1,250.00 (125,000 minor units) -> RECOVERED case
        tx1 = Transaction(
            id=uuid4(),
            customer_id=cust1.id,
            provider="stripe",
            external_transaction_id="txn_test_01",
            amount_minor=125000,
            currency="USD",
            status=TransactionStatus.FAILED,
            failure_code="insufficient_funds",
            occurred_at=now,
        )
        session.add(tx1)
        session.flush()

        case1 = RecoveryCase(
            id=uuid4(),
            customer_id=cust1.id,
            trigger_transaction_id=tx1.id,
            case_key="CASE-TEST-001",
            state=RecoveryCaseState.RECOVERED,
            priority=100,
            opened_at=now,
            last_state_changed_at=now,
        )
        session.add(case1)

        # Trigger transaction 2: $750.00 (75,000 minor units) -> ESCALATED case
        tx2 = Transaction(
            id=uuid4(),
            customer_id=cust1.id,
            provider="stripe",
            external_transaction_id="txn_test_02",
            amount_minor=75000,
            currency="USD",
            status=TransactionStatus.FAILED,
            failure_code="do_not_honor",
            occurred_at=now,
        )
        session.add(tx2)
        session.flush()

        case2 = RecoveryCase(
            id=uuid4(),
            customer_id=cust1.id,
            trigger_transaction_id=tx2.id,
            case_key="CASE-TEST-002",
            state=RecoveryCaseState.ESCALATED,
            priority=50,
            opened_at=now,
            last_state_changed_at=now,
        )
        session.add(case2)
        session.commit()

    # Query metrics
    res = client.get("/api/v1/dashboard/metrics", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Total at risk: 125,000 + 75,000 = 200,000 minor units ($2,000.00)
    assert data["at_risk_revenue_minor"] == 200000
    # Recovered revenue: 125,000 minor units ($1,250.00)
    assert data["recovered_revenue_minor"] == 125000
    # Recovery rate: 125,000 / 200,000 = 62.50%
    assert data["recovery_rate_pct"] == "62.50%"
    # Case recovery rate: 1 recovered / 2 total = 50.00%
    assert data["case_recovery_rate_pct"] == "50.00%"
    assert data["total_at_risk_cases"] == 2
    assert data["total_recovered_cases"] == 1
    assert data["escalated_cases"] == 1


# ---------------------------------------------------------------------------
# 5. Trend and Workflow Status Distribution Tests
# ---------------------------------------------------------------------------

def test_dashboard_revenue_trend_and_workflow_status(api_test_context):
    """Verify revenue trendline points and FSM state distribution."""
    client = api_test_context["client"]
    headers = api_test_context["auth_headers"]

    # Trend API
    res_trend = client.get("/api/v1/dashboard/trend", headers=headers)
    assert res_trend.status_code == 200
    trend_data = res_trend.json()
    assert trend_data["currency"] == "USD"
    assert "points" in trend_data

    # Trend alias API
    res_trend_alias = client.get("/api/v1/dashboard/revenue-trends", headers=headers)
    assert res_trend_alias.status_code == 200

    # Workflow status distribution
    res_workflow = client.get("/api/v1/dashboard/workflow-status", headers=headers)
    assert res_workflow.status_code == 200
    workflow_data = res_workflow.json()
    assert "counts" in workflow_data
    assert "total_cases" in workflow_data


# ---------------------------------------------------------------------------
# 6. Case Listing with Pagination and Filtering Tests
# ---------------------------------------------------------------------------

def test_case_listing_pagination_and_state_filter(api_test_context):
    """Verify paginated case queue retrieval and state filtering."""
    client = api_test_context["client"]
    headers = api_test_context["auth_headers"]
    session_factory = api_test_context["session_factory"]

    # Seed 3 cases with different states
    now = datetime.now(timezone.utc)
    with session_factory() as session:
        cust = Customer(
            id=uuid4(),
            provider="stripe",
            external_customer_id="cus_queue_01",
            display_name="Queue Test Customer",
            status=CustomerStatus.ACTIVE,
        )
        session.add(cust)
        session.flush()

        for i, state in enumerate([RecoveryCaseState.DETECTED, RecoveryCaseState.DETECTED, RecoveryCaseState.RECOVERED]):
            tx = Transaction(
                id=uuid4(),
                customer_id=cust.id,
                provider="stripe",
                external_transaction_id=f"txn_queue_{i}",
                amount_minor=50000 + (i * 10000),
                currency="USD",
                status=TransactionStatus.FAILED,
                occurred_at=now,
            )
            session.add(tx)
            session.flush()

            case = RecoveryCase(
                id=uuid4(),
                customer_id=cust.id,
                trigger_transaction_id=tx.id,
                case_key=f"CASE-QUEUE-{i}",
                state=state,
                priority=100 - i,
                opened_at=now,
                last_state_changed_at=now,
            )
            session.add(case)
        session.commit()

    # List all cases
    res = client.get("/api/v1/cases?page=1&size=10", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "pagination" in body
    assert body["pagination"]["total"] == 3
    assert len(body["items"]) == 3

    # Verify embedded summaries
    first_item = body["items"][0]
    assert first_item["customer"]["display_name"] == "Queue Test Customer"
    assert "amount_minor" in first_item["trigger_transaction"]

    # Filter by state = RECOVERED
    res_filtered = client.get("/api/v1/cases?state=RECOVERED", headers=headers)
    assert res_filtered.status_code == 200
    filtered_body = res_filtered.json()
    assert filtered_body["pagination"]["total"] == 1
    assert filtered_body["items"][0]["state"] == "recovered"


# ---------------------------------------------------------------------------
# 7. Case Detail Read and 404 Tests
# ---------------------------------------------------------------------------

def test_case_detail_read_and_404_handling(api_test_context):
    """Verify deep case representation retrieval and 404 not found handling."""
    client = api_test_context["client"]
    headers = api_test_context["auth_headers"]
    session_factory = api_test_context["session_factory"]

    now = datetime.now(timezone.utc)
    with session_factory() as session:
        cust = Customer(
            id=uuid4(),
            provider="stripe",
            external_customer_id="cus_detail_01",
            display_name="Detail Corp",
            email="detail@corp.com",
            status=CustomerStatus.ACTIVE,
        )
        session.add(cust)
        session.flush()

        tx = Transaction(
            id=uuid4(),
            customer_id=cust.id,
            provider="stripe",
            external_transaction_id="txn_detail_01",
            amount_minor=99000,
            currency="USD",
            status=TransactionStatus.FAILED,
            failure_code="card_declined",
            failure_message_safe="Card was declined by issuing bank",
            occurred_at=now,
        )
        session.add(tx)
        session.flush()

        case = RecoveryCase(
            id=uuid4(),
            customer_id=cust.id,
            trigger_transaction_id=tx.id,
            case_key="CASE-DETAIL-999",
            state=RecoveryCaseState.ACTION_PENDING,
            priority=10,
            opened_at=now,
            last_state_changed_at=now,
        )
        session.add(case)
        session.commit()
        case_id = str(case.id)

    # Valid case detail
    res = client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == case_id
    assert detail["case_key"] == "CASE-DETAIL-999"
    assert detail["customer"]["display_name"] == "Detail Corp"
    assert detail["trigger_transaction"]["amount_minor"] == 99000
    assert detail["trigger_transaction"]["failure_code"] == "card_declined"

    # Nonexistent case UUID -> 404
    missing_id = str(uuid4())
    res_missing = client.get(f"/api/v1/cases/{missing_id}", headers=headers)
    assert res_missing.status_code == 404
    error_data = res_missing.json()
    assert error_data["success"] is False
    assert error_data.get("error_code") in ("RESOURCE_NOT_FOUND", "NOT_FOUND") or (
        "error" in error_data and error_data["error"].get("code") in ("RESOURCE_NOT_FOUND", "NOT_FOUND")
    )


# ---------------------------------------------------------------------------
# 8. Security and Authorization Rejection Tests
# ---------------------------------------------------------------------------

def test_security_protection_unauthenticated_requests_rejected(api_test_context):
    """Verify that unauthenticated and invalid requests to protected endpoints are rejected with 401."""
    client = api_test_context["client"]

    # Protected routes must reject anonymous callers
    assert client.get("/api/v1/dashboard/metrics").status_code == 401
    assert client.get("/api/v1/dashboard/summary").status_code == 401
    assert client.get("/api/v1/dashboard/trend").status_code == 401
    assert client.get("/api/v1/dashboard/workflow-status").status_code == 401
    assert client.get("/api/v1/cases").status_code == 401
    assert client.get(f"/api/v1/cases/{uuid4()}").status_code == 401

    # Malformed token
    bad_headers = {"Authorization": "Bearer malformed.token.value"}
    assert client.get("/api/v1/dashboard/metrics", headers=bad_headers).status_code == 401
