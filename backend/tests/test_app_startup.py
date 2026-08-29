"""Startup and application-factory tests for the Phase 1 foundation.

Author: Karthikeya
"""

from app.main import create_app
from fastapi import FastAPI


def test_application_factory_creates_fastapi_app() -> None:
    """The application is importable and exposes the expected route."""

    application = create_app()

    assert isinstance(application, FastAPI)
    assert "/health" in application.openapi()["paths"]
