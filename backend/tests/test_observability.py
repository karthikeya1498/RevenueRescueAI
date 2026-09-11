"""Phase 10 observability and readiness tests.

Author: Karthikeya
"""

import json
import logging

from app.main import create_app
from fastapi.testclient import TestClient


def test_readiness_contract_is_deterministic() -> None:
    """Readiness exposes safe configuration and deferred dependency states."""

    response = TestClient(create_app()).get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "RevenueRescue AI",
        "phase": "foundation",
        "environment": "development",
        "dependencies": {
            "configuration": "ready",
            "database": "deferred",
            "providers": "not_configured",
        },
    }


def test_request_id_is_preserved_and_access_event_is_structured(caplog) -> None:
    """Requests receive a response correlation ID and one JSON access event."""

    request_id = "phase10-test-001"
    with caplog.at_level(logging.INFO, logger="revenuerescue.access"):
        response = TestClient(create_app()).get("/health", headers={"x-request-id": request_id})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id
    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "revenuerescue.access"
    ]
    assert len(events) == 1
    assert events[0]["event"] == "http_request"
    assert events[0]["request_id"] == request_id
    assert events[0]["path"] == "/health"
    assert events[0]["status_code"] == 200
    assert events[0]["duration_ms"] >= 0


def test_blank_request_id_is_replaced() -> None:
    """Blank inbound IDs never become blank response correlation IDs."""

    response = TestClient(create_app()).get("/health", headers={"x-request-id": ""})

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.headers["x-request-id"] != ""
