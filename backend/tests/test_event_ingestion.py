"""Comprehensive automated test suite for Phase 2.6: Payment Event Ingestion and Normalization Engine.

Author: Karthikeya
Architectural layer: integration & unit test suite.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.enums import (
    CanonicalEventType,
    UserRole,
    UserStatus,
)
from app.core.errors import (
    ConflictingDuplicateEventException,
    EventValidationException,
    UnsupportedEventTypeException,
)
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.domain import ProviderWebhookEvent, User
from app.schemas.events import CanonicalEventDTO, EventIngestRequestDTO, SimulateFailureRequestDTO
from app.services.event_deduplicator import EventDeduplicator
from app.services.event_normalizer import EventNormalizer
from app.services.event_service import EventService
from app.services.event_validator import EventValidator


from sqlalchemy.pool import StaticPool


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
    """FastAPI TestClient with isolated db session."""
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def operator_token(db_session):
    """Create operator user and return JWT bearer token."""
    user = User(
        email="operator@revenuerescue.ai",
        name="Operator User",
        password_hash=hash_password("OperatorSecret123!"),
        role=UserRole.OPERATOR,
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return create_access_token(user_id=user.id, email=user.email, role=UserRole.OPERATOR)


# =========================================================================
# 1. NORMALIZATION TESTS
# =========================================================================

def test_normalization_stripe_webhook():
    stripe_payload = {
        "id": "evt_str_001",
        "type": "payment_intent.payment_failed",
        "created": 1730376000,
        "data": {
            "object": {
                "id": "pi_3Mtw",
                "customer": "cus_12345",
                "amount": 250000,
                "currency": "usd",
                "status": "requires_payment_method",
                "last_payment_error": {
                    "code": "card_declined",
                    "message": "Card was declined.",
                },
            }
        },
    }
    canonical = EventNormalizer.normalize_raw_provider_webhook(stripe_payload, provider="stripe")
    assert canonical.external_event_id == "evt_str_001"
    assert canonical.event_type == CanonicalEventType.PAYMENT_FAILED.value
    assert canonical.provider == "stripe"
    assert canonical.customer_reference == "cus_12345"
    assert canonical.payment_reference == "pi_3Mtw"
    assert canonical.amount_minor == 250000
    assert canonical.currency == "USD"
    assert canonical.failure_code == "generic_decline"


def test_normalization_razorpay_webhook():
    razorpay_payload = {
        "event": "payment.failed",
        "created_at": 1730376100,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_98765",
                    "amount": 50000,
                    "currency": "inr",
                    "contact": "+15555555555",
                    "error_code": "insufficient_funds",
                    "error_description": "Insufficient funds in bank account.",
                }
            }
        },
    }
    canonical = EventNormalizer.normalize_raw_provider_webhook(razorpay_payload, provider="razorpay")
    assert canonical.event_type == CanonicalEventType.PAYMENT_FAILED.value
    assert canonical.provider == "razorpay"
    assert canonical.customer_reference == "+15555555555"
    assert canonical.payment_reference == "pay_98765"
    assert canonical.amount_minor == 50000
    assert canonical.currency == "INR"
    assert canonical.failure_code == "insufficient_funds"


def test_normalization_sanitizes_pii():
    payload = {
        "customer_reference": "cus_safe",
        "amount_minor": 1000,
        "currency": "USD",
        "metadata": {
            "card_number": "4111111111111111",
            "cvv": "123",
            "user_note": "Payment with card 4111 2222 3333 4444",
            "tenant_id": "org_abc",
        },
    }
    req = EventIngestRequestDTO(**payload)
    canonical = EventNormalizer.normalize_canonical_request(req)
    assert canonical.metadata["card_number"] == "[REDACTED]"
    assert canonical.metadata["cvv"] == "[REDACTED]"
    assert canonical.metadata["tenant_id"] == "org_abc"
    assert "[REDACTED_PAN]" in canonical.metadata["user_note"]


# =========================================================================
# 2. VALIDATION TESTS
# =========================================================================

def test_validation_all_supported_event_types():
    now = datetime.now(timezone.utc)
    types_and_payloads = [
        (
            CanonicalEventType.PAYMENT_FAILED.value,
            {
                "payment_reference": "pi_1",
                "customer_reference": "cus_1",
                "failure_code": "insufficient_funds",
            },
        ),
        (
            CanonicalEventType.PAYMENT_SUCCEEDED.value,
            {
                "payment_reference": "pi_2",
                "customer_reference": "cus_2",
            },
        ),
        (
            CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value,
            {
                "subscription_reference": "sub_1",
                "customer_reference": "cus_3",
                "failure_code": "card_expired",
            },
        ),
        (
            CanonicalEventType.CHECKOUT_ABANDONED.value,
            {
                "checkout_session_id": "cs_123",
                "customer_reference": "cus_4",
            },
        ),
        (
            CanonicalEventType.INVOICE_OVERDUE.value,
            {
                "invoice_reference": "inv_1",
                "customer_reference": "cus_5",
            },
        ),
    ]

    for event_type, extra in types_and_payloads:
        dto = CanonicalEventDTO(
            external_event_id=f"evt_{uuid4().hex[:8]}",
            event_type=event_type,
            provider="stripe",
            occurred_at=now,
            amount_minor=1000,
            currency="USD",
            **extra,
        )
        # Should not raise exception
        EventValidator.validate(dto)


def test_validation_rejects_unsupported_type():
    dto = CanonicalEventDTO(
        external_event_id="evt_bad",
        event_type="UNSUPPORTED_RANDOM_TYPE",
        provider="stripe",
        occurred_at=datetime.now(timezone.utc),
        customer_reference="cus_1",
        amount_minor=100,
        currency="USD",
    )
    with pytest.raises(UnsupportedEventTypeException):
        EventValidator.validate(dto)


def test_validation_rejects_missing_payment_reference_on_payment_failed():
    dto = CanonicalEventDTO(
        external_event_id="evt_fail_1",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        occurred_at=datetime.now(timezone.utc),
        customer_reference="cus_1",
        amount_minor=100,
        currency="USD",
        failure_code="insufficient_funds",
        payment_reference=None,
    )
    with pytest.raises(EventValidationException) as exc:
        EventValidator.validate(dto)
    assert exc.value.status_code == 422


def test_validation_rejects_negative_amount():
    with pytest.raises(ValueError):
        CanonicalEventDTO(
            external_event_id="evt_neg",
            event_type=CanonicalEventType.PAYMENT_FAILED.value,
            provider="stripe",
            occurred_at=datetime.now(timezone.utc),
            customer_reference="cus_1",
            payment_reference="txn_1",
            amount_minor=-500,
            currency="USD",
            failure_code="generic_decline",
        )


def test_validation_rejects_future_clock_skew():
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)
    dto = CanonicalEventDTO(
        external_event_id="evt_future",
        event_type=CanonicalEventType.PAYMENT_FAILED.value,
        provider="stripe",
        occurred_at=future_time,
        customer_reference="cus_1",
        payment_reference="pi_1",
        amount_minor=1000,
        currency="USD",
        failure_code="generic_decline",
    )
    with pytest.raises(EventValidationException):
        EventValidator.validate(dto)


# =========================================================================
# 3. DEDUPLICATION & IDEMPOTENCY TESTS
# =========================================================================

def test_deduplication_exact_duplicate(db_session):
    service = EventService(db_session)
    req = EventIngestRequestDTO(
        event_id="evt_dedup_001",
        event_type="PAYMENT_FAILED",
        provider="stripe",
        customer_reference="cus_dedup",
        payment_reference="pi_dedup",
        amount_minor=5000,
        currency="USD",
        failure_code="insufficient_funds",
    )

    res1 = service.ingest_canonical_event(req)
    assert res1.accepted is True
    assert res1.duplicate is False
    assert res1.status == "ACCEPTED"

    # Exact duplicate submission
    res2 = service.ingest_canonical_event(req)
    assert res2.accepted is True
    assert res2.duplicate is True
    assert res2.status == "DUPLICATE"
    assert res2.reason == "duplicate_event_suppressed"
    assert res2.event_id == res1.event_id


def test_deduplication_conflicting_duplicate_raises_409(db_session):
    service = EventService(db_session)
    req1 = EventIngestRequestDTO(
        event_id="evt_conflict_001",
        event_type="PAYMENT_FAILED",
        provider="stripe",
        customer_reference="cus_conflict",
        payment_reference="pi_1",
        amount_minor=5000,
        currency="USD",
        failure_code="insufficient_funds",
    )
    service.ingest_canonical_event(req1)

    # Reused event_id with DIFFERENT amount (conflicting payload)
    req2 = EventIngestRequestDTO(
        event_id="evt_conflict_001",
        event_type="PAYMENT_FAILED",
        provider="stripe",
        customer_reference="cus_conflict",
        payment_reference="pi_1",
        amount_minor=99999,
        currency="USD",
        failure_code="insufficient_funds",
    )
    with pytest.raises(ConflictingDuplicateEventException) as exc:
        service.ingest_canonical_event(req2)
    assert exc.value.status_code == 409


def test_different_providers_same_external_id_are_distinct(db_session):
    service = EventService(db_session)
    req_stripe = EventIngestRequestDTO(
        event_id="shared_evt_id_100",
        event_type="PAYMENT_FAILED",
        provider="stripe",
        customer_reference="cus_1",
        payment_reference="pi_1",
        amount_minor=1000,
        currency="USD",
        failure_code="card_declined",
    )
    req_razorpay = EventIngestRequestDTO(
        event_id="shared_evt_id_100",
        event_type="PAYMENT_FAILED",
        provider="razorpay",
        customer_reference="cus_2",
        payment_reference="pay_2",
        amount_minor=1000,
        currency="INR",
        failure_code="card_declined",
    )

    res_str = service.ingest_canonical_event(req_stripe)
    res_rzp = service.ingest_canonical_event(req_razorpay)

    assert res_str.event_id != res_rzp.event_id
    assert res_str.duplicate is False
    assert res_rzp.duplicate is False
    assert db_session.query(ProviderWebhookEvent).count() == 2


# =========================================================================
# 4. API INTEGRATION & SIMULATOR TESTS
# =========================================================================

def test_api_events_post_canonical(client, operator_token):
    headers = {"Authorization": f"Bearer {operator_token}"}
    payload = {
        "event_id": "evt_api_post_1",
        "event_type": "PAYMENT_FAILED",
        "provider": "synthetic",
        "customer_reference": "cus_post_test",
        "payment_reference": "txn_post_test",
        "amount_minor": 15000,
        "currency": "USD",
        "failure_code": "insufficient_funds",
        "failure_message": "Card was declined for insufficient funds.",
    }
    # Initial creation
    res1 = client.post("/api/v1/events", json=payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["accepted"] is True
    assert data1["duplicate"] is False
    assert data1["status"] == "ACCEPTED"

    # Duplicate call
    res2 = client.post("/api/v1/events", json=payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["duplicate"] is True
    assert data2["status"] == "DUPLICATE"


def test_api_webhook_with_hmac_verification(client):
    secret = "test_webhook_signing_secret_xyz"
    raw_payload = {
        "id": "evt_webhook_hmac_1",
        "type": "payment_intent.payment_failed",
        "created": 1730377000,
        "data": {
            "object": {
                "id": "pi_hmac_1",
                "customer": "cus_hmac_1",
                "amount": 42000,
                "currency": "usd",
                "last_payment_error": {
                    "code": "insufficient_funds",
                    "message": "Insufficient balance",
                },
            }
        },
    }
    raw_bytes = json.dumps(raw_payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

    import os
    os.environ["WEBHOOK_SIGNING_SECRET"] = secret

    try:
        # Valid signature
        headers = {
            "X-Signature-SHA256": signature,
            "X-Event-ID": "evt_webhook_hmac_1",
            "Content-Type": "application/json",
        }
        res_valid = client.post("/api/v1/webhooks/provider", content=raw_bytes, headers=headers)
        assert res_valid.status_code == 200
        assert res_valid.json()["accepted"] is True

        # Invalid/Tampered signature
        headers_invalid = {
            "X-Signature-SHA256": "bad_signature_digest_12345",
            "X-Event-ID": "evt_webhook_hmac_2",
            "Content-Type": "application/json",
        }
        res_invalid = client.post("/api/v1/webhooks/provider", content=raw_bytes, headers=headers_invalid)
        assert res_invalid.status_code == 401
    finally:
        os.environ.pop("WEBHOOK_SIGNING_SECRET", None)


def test_api_simulate_failure_endpoint(client, operator_token):
    headers = {"Authorization": f"Bearer {operator_token}"}
    sim_body = {
        "customer_id": "cus_sim_test_01",
        "amount_minor": 842000,
        "currency": "USD",
        "failure_code": "insufficient_funds",
        "failure_message": "Card has insufficient funds for recurring charge.",
        "metadata": {"simulation_run": "test_batch_1"},
    }
    res = client.post("/api/v1/events/simulate-failure", json=sim_body, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["accepted"] is True
    assert data["duplicate"] is False
    assert data["status"] == "ACCEPTED"
    assert "evt_sim_" in data["external_event_id"]


def test_api_list_events_and_detail(client, operator_token):
    headers = {"Authorization": f"Bearer {operator_token}"}
    # Seed an event
    payload = {
        "event_id": "evt_lookup_001",
        "event_type": "PAYMENT_FAILED",
        "provider": "synthetic",
        "customer_reference": "cus_lookup",
        "payment_reference": "pi_lookup",
        "amount_minor": 12000,
        "currency": "USD",
        "failure_code": "card_expired",
    }
    create_res = client.post("/api/v1/events", json=payload, headers=headers)
    assert create_res.status_code == 201
    internal_id = create_res.json()["event_id"]

    # List events
    list_res = client.get("/api/v1/events?limit=10&page=1", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(item["external_event_id"] == "evt_lookup_001" for item in list_data["items"])

    # Detail lookup by UUID
    detail_res = client.get(f"/api/v1/events/{internal_id}", headers=headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["external_event_id"] == "evt_lookup_001"
    assert detail_data["ingestion_status"] == "ACCEPTED"
    assert detail_data["payload_safe"]["amount_minor"] == 12000

    # Non-existent event
    missing_res = client.get(f"/api/v1/events/{uuid4()}", headers=headers)
    assert missing_res.status_code == 404
