"""Tests for the verified decision-system upgrade.
Author: Karthikeya
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from app.main import app
from app.services.intelligence import analyze_recovery, classify_failure
from app.services.verification import (
    RecoveryAttributor,
    WebhookEventLedger,
    canonical_payload,
    verify_signature,
)
from fastapi.testclient import TestClient


def test_failure_classifier_is_explicit_and_conservative() -> None:
    result = classify_failure("card_expired")
    assert result.category == "expired_card"
    assert result.retryable is False


def test_high_risk_never_recommends_automatic_payment_action() -> None:
    result = analyze_recovery(
        amount_minor=250000,
        failure_code="fraud_blocked",
        failure_message="risk",
        prior_attempts=4,
        unusual_velocity=True,
    )
    assert result.risk.band == "high"
    assert result.recommended_action in {"request_operator_review", "stop"}
    assert result.confidence <= 1


def test_expected_value_is_integer_minor_units_and_explainable() -> None:
    result = analyze_recovery(
        amount_minor=4999, failure_code="bank_decline", failure_message=None, prior_attempts=0
    )
    assert result.recommended_action in {
        "retry_payment",
        "send_reminder",
        "request_operator_review",
        "stop",
    }
    assert all(isinstance(row.expected_value_minor, int) for row in result.estimates)
    assert any("probability=" in reason for reason in result.rationale)


def test_signature_and_duplicate_event_protection() -> None:
    body = canonical_payload({"event": "payment.paid", "id": "evt_1"})
    secret = "test-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_signature(body, signature, secret)
    ledger = WebhookEventLedger()
    first = ledger.accept(event_id="evt_1", payload=body)
    second = ledger.accept(event_id="evt_1", payload=body)
    assert first.accepted and not first.duplicate
    assert not second.accepted and second.duplicate


def test_recovery_attribution_requires_verified_matching_evidence() -> None:
    failed = datetime.now(timezone.utc)
    evidence = RecoveryAttributor().attribute(
        intervention_id="intent-1",
        failed_transaction_id="pay-failed",
        successful_transaction_id="pay-new",
        provider_event_id="evt-1",
        amount_minor=4999,
        successful_amount_minor=4999,
        currency="INR",
        successful_currency="INR",
        failed_at=failed,
        verified_at=failed + timedelta(hours=2),
        provider_signature_valid=True,
    )
    assert evidence.attributable is True
    rejected = RecoveryAttributor().attribute(
        intervention_id="intent-1",
        failed_transaction_id="pay-failed",
        successful_transaction_id="pay-new",
        provider_event_id="evt-2",
        amount_minor=4999,
        successful_amount_minor=5000,
        currency="INR",
        successful_currency="INR",
        failed_at=failed,
        verified_at=failed + timedelta(hours=2),
        provider_signature_valid=True,
    )
    assert rejected.attributable is False
    assert rejected.reason == "amount_mismatch"


def test_decision_preview_api_has_policy_and_evidence_fields() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/recovery/decision-preview",
        json={
            "amount_minor": 4999,
            "currency": "INR",
            "failure_code": "bank_decline",
            "prior_attempts": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_authority"] == "deterministic"
    assert payload["risk"]["band"] in {"low", "medium", "high"}
    assert payload["action_estimates"]


def test_webhook_api_rejects_invalid_signature() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/recovery/webhooks/provider",
        content=json.dumps({"event": "payment.paid"}),
        headers={"x-event-id": "evt-invalid", "x-signature": "bad"},
    )
    assert response.status_code == 401
