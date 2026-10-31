"""Tests for global error handling and RFC-7807 problem detail contracts.

Author: Karthikeya
Architectural layer: test suite.
"""

from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import (
    EntityNotFoundException,
    PolicyViolationException,
)
from app.main import create_app

mock_error_router = APIRouter(prefix="/test-errors", tags=["testing"])


class SamplePayload(BaseModel):
    amount_cents: int = Field(gt=0)
    customer_id: str = Field(min_length=3)


@mock_error_router.get("/custom-exception")
def raise_custom_exception() -> None:
    raise EntityNotFoundException("RecoveryCase", "case_test_99")


@mock_error_router.get("/policy-violation")
def raise_policy_violation() -> None:
    raise PolicyViolationException("MAX_RETRIES_EXCEEDED", "Retry count 3 exceeds ceiling")


@mock_error_router.post("/validation")
def trigger_validation(payload: SamplePayload) -> dict[str, str]:
    return {"status": "ok"}


@mock_error_router.get("/unhandled-crash")
def trigger_unhandled_crash() -> None:
    raise ZeroDivisionError("Simulated unexpected server error")


def test_entity_not_found_returns_rfc7807_contract() -> None:
    """Resource not found exceptions produce standard RFC-7807 problem details."""
    app = create_app()
    app.include_router(mock_error_router)
    client = TestClient(app)

    response = client.get("/test-errors/custom-exception", headers={"x-request-id": "req-not-found-1"})

    assert response.status_code == 404
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "RESOURCE_NOT_FOUND"
    assert "case_test_99" in payload["message"]
    assert payload["request_id"] == "req-not-found-1"
    assert "timestamp" in payload
    assert len(payload["details"]) == 1
    assert payload["details"][0]["field"] == "id"


def test_policy_violation_returns_unprocessable_entity() -> None:
    """Policy gate violations produce 422 with detailed rule metadata."""
    app = create_app()
    app.include_router(mock_error_router)
    client = TestClient(app)

    response = client.get("/test-errors/policy-violation")

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "POLICY_VIOLATION"
    assert payload["details"][0]["field"] == "MAX_RETRIES_EXCEEDED"


def test_schema_validation_error_formatting() -> None:
    """Pydantic validation errors are neatly parsed into field and code lists."""
    app = create_app()
    app.include_router(mock_error_router)
    client = TestClient(app)

    # Send negative amount and missing customer_id
    response = client.post("/test-errors/validation", json={"amount_cents": -50})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "VALIDATION_FAILED"
    fields = [d["field"] for d in payload["details"]]
    assert "amount_cents" in fields
    assert "customer_id" in fields


def test_unhandled_crash_does_not_leak_stack_trace() -> None:
    """Unexpected 500 exceptions redact internal traceback and return safe message."""
    app = create_app()
    app.include_router(mock_error_router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/test-errors/unhandled-crash", headers={"x-request-id": "req-crash-99"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["error_code"] == "INTERNAL_SERVER_ERROR"
    assert "ZeroDivisionError" not in payload["message"]
    assert "Traceback" not in payload["message"]
    assert payload["request_id"] == "req-crash-99"
