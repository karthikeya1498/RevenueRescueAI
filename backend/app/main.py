"""FastAPI application entry point for RevenueRescue AI.

Author: Karthikeya
Architectural layer: application composition.

This module wires configuration, logging, CORS, error handling, and routes.
Future business logic belongs in services, workflows, policies, tools, and
repositories—not here.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.cases import router as cases_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.events import router as events_router
from app.api.routes.health import router as health_router
from app.api.routes.policy import router as policy_router
from app.api.routes.realtime import router as realtime_router
from app.api.routes.recovery_intelligence import router as recovery_intelligence_router
from app.api.routes.workflows import router as workflows_router
from app.core.config import get_settings

from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.observability import RequestObservabilityMiddleware


def create_app() -> FastAPI:
    """Create and configure the FastAPI application without side effects."""

    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Autonomous, Bounded, and Verified AI Revenue Recovery Platform Backend API.",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Global Observability & Access Logging Middleware
    application.add_middleware(RequestObservabilityMiddleware)

    # CORS Middleware (Restricted to configured origins, never unrestricted in production)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Uniform RFC-7807 Global Error Handlers
    register_exception_handlers(application)

    # API Routers
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(dashboard_router)
    application.include_router(cases_router)
    application.include_router(events_router)
    application.include_router(recovery_intelligence_router)
    application.include_router(policy_router)
    application.include_router(realtime_router)
    application.include_router(workflows_router)

    return application



app = create_app()
