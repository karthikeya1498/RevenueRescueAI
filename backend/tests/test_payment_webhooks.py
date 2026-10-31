"""Tests for Razorpay Webhook Ingress, Signature Verification, Idempotency, and Out-of-Order Safety.

Author: Karthikeya
Architectural layer: tests / webhook receiver & security boundary.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db, utc_now
from app.core.enums import (
    CustomerStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.main import create_app
from app.models.domain import Customer, RecoveryCase, Transaction


@pytest.fixture
def db_session():
    """Create an isolated, in-memory SQLite database session with foreign keys."""
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
    """FastAPI TestClient with isolated in-memory DB session."""
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_razorpay_payload(event_type: str = "payment.captured", payment_id: str | None = None, amount_minor: int = 250000):
    pay_id = payment_id or f"pay_{uuid4().hex[:10]}"
    return {
        "entity": "event",
        "account_id": "acc_test_123",
        "event": event_type,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": pay_id,
                    "entity": "payment",
                    "amount": amount_minor,
                    "currency": "INR",
                    "status": "captured" if "captured" in event_type else "failed",
                    "order_id": f"order_{uuid4().hex[:8]}",
                    "method": "card",
                    "contact": "+919876543210",
                    "email": "customer@example.in",
                    "error_code": None if "captured" in event_type else "BAD_REQUEST_PAYMENT_FAILED",
                    "error_description": None if "captured" in event_type else "Payment failed",
                }
            }
        },
        "created_at": int(utc_now().timestamp()),
    }


def compute_signature(payload_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def test_razorpay_webhook_valid_signature_success(client):
    """Verifies that a valid Razorpay webhook with matching HMAC signature is accepted."""
    settings = get_settings()
    secret = settings.payment_webhook_secret or "rzp_test_webhook_secret"

    payload_data = make_razorpay_payload("payment.captured")
    body_bytes = json.dumps(payload_data).encode("utf-8")
    valid_sig = compute_signature(body_bytes, secret)

    headers = {
        "x-razorpay-signature": valid_sig,
        "x-razorpay-event-id": f"evt_{uuid4().hex[:12]}",
        "Content-Type": "application/json",
    }

    response = client.post("/api/v1/webhooks/razorpay", content=body_bytes, headers=headers)

    assert response.status_code == 200
    res = response.json()
    assert res["accepted"] is True
    assert res["duplicate"] is False
    assert res["event_type"] == "PAYMENT_SUCCEEDED"


def test_razorpay_webhook_invalid_signature_rejected(client):
    """Verifies that an invalid signature is rejected with 401 Unauthorized."""
    payload_data = make_razorpay_payload("payment.captured")
    body_bytes = json.dumps(payload_data).encode("utf-8")

    headers = {
        "x-razorpay-signature": "invalid_forged_signature_hex",
        "x-razorpay-event-id": f"evt_{uuid4().hex[:12]}",
        "Content-Type": "application/json",
    }

    response = client.post("/api/v1/webhooks/razorpay", content=body_bytes, headers=headers)

    assert response.status_code == 401
    res_json = response.json()
    err_msg = res_json.get("message") or res_json.get("detail", "")
    assert "signature verification failed" in err_msg.lower()



def test_razorpay_webhook_idempotency_duplicate(client):
    """Verifies that duplicate webhook deliveries are deduplicated and return 200 OK."""
    settings = get_settings()
    secret = settings.payment_webhook_secret or "rzp_test_webhook_secret"

    payload_data = make_razorpay_payload("payment.captured")
    body_bytes = json.dumps(payload_data).encode("utf-8")
    sig = compute_signature(body_bytes, secret)
    event_id = f"evt_dedup_{uuid4().hex[:10]}"

    headers = {
        "x-razorpay-signature": sig,
        "x-razorpay-event-id": event_id,
        "Content-Type": "application/json",
    }

    # First delivery
    resp1 = client.post("/api/v1/webhooks/razorpay", content=body_bytes, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["duplicate"] is False

    # Second delivery of identical webhook
    resp2 = client.post("/api/v1/webhooks/razorpay", content=body_bytes, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["duplicate"] is True
    assert resp2.json()["status"] == "DUPLICATE"


def test_razorpay_webhook_out_of_order_preserves_verified_success(client, db_session):
    """Verifies that a delayed stale failure event cannot downgrade an already succeeded transaction."""
    settings = get_settings()
    secret = settings.payment_webhook_secret or "rzp_test_webhook_secret"

    # 1. Seed Customer and Transaction with SUCCEEDED status
    now = utc_now()
    cust = Customer(
        id=uuid4(),
        provider="razorpay",
        external_customer_id="+919876543210",
        email="customer@example.in",
        status=CustomerStatus.ACTIVE,
    )
    db_session.add(cust)
    db_session.flush()

    payment_id = f"pay_order_{uuid4().hex[:8]}"
    txn = Transaction(
        id=uuid4(),
        customer_id=cust.id,
        provider="razorpay",
        external_transaction_id=payment_id,
        amount_minor=250000,
        currency="INR",
        status=TransactionStatus.SUCCEEDED,  # Already verified succeeded!
        occurred_at=now,
    )
    db_session.add(txn)
    db_session.flush()

    case = RecoveryCase(
        id=uuid4(),
        customer_id=cust.id,
        trigger_transaction_id=txn.id,
        case_key=f"case_{payment_id}",
        state=RecoveryCaseState.RECOVERED,  # Already resolved!
        priority=100,
        opened_at=now,
        last_state_changed_at=now,
        closed_at=now,
        version=1,
    )
    db_session.add(case)
    db_session.commit()

    # 2. Simulate late arrival of a delayed payment.failed event for the same payment reference
    stale_failure_data = make_razorpay_payload("payment.failed", payment_id=payment_id)
    body_bytes = json.dumps(stale_failure_data).encode("utf-8")
    sig = compute_signature(body_bytes, secret)

    headers = {
        "x-razorpay-signature": sig,
        "x-razorpay-event-id": f"evt_stale_fail_{uuid4().hex[:10]}",
        "Content-Type": "application/json",
    }

    resp = client.post("/api/v1/webhooks/razorpay", content=body_bytes, headers=headers)
    assert resp.status_code == 200

    # 3. Verify in database that transaction and case states remained SUCCEEDED and RECOVERED
    db_session.refresh(txn)
    db_session.refresh(case)

    assert txn.status == TransactionStatus.SUCCEEDED
    assert case.state == RecoveryCaseState.RECOVERED
