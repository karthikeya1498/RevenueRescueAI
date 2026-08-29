"""FastAPI application entry point for RevenueRescue AI.

Author: Karthikeya
Architectural layer: application composition.

This module wires configuration, logging, and routes. Future business logic
belongs in services, workflows, policies, tools, and repositories—not here.
"""

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application without side effects."""

    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(title=settings.app_name, version="0.1.0")
    application.include_router(health_router)
    return application


app = create_app()
