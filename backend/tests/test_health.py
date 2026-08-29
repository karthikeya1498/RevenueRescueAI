"""Behavior tests for the Phase 1 health contract.

Author: Karthikeya
"""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_foundation_contract() -> None:
    """The health endpoint returns the stable, provider-free payload."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "RevenueRescue AI",
        "phase": "foundation",
    }
