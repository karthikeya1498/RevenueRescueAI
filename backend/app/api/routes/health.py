"""Health and readiness endpoints for RevenueRescue AI.

Author: Karthikeya
"""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import check_database_connection

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Stable response contract for service liveness."""

    status: str
    service: str
    phase: str


class ReadinessResponse(HealthResponse):
    """Stable response contract for dependency readiness."""

    environment: str
    dependencies: dict[str, str]


class DatabaseHealthResponse(BaseModel):
    """Diagnostic response contract for database probe."""

    status: str
    database: str
    dialect: str


@router.get("/health", response_model=HealthResponse, summary="Check service liveness")
@router.get("/api/v1/health", response_model=HealthResponse, summary="Check service liveness (Versioned)")
def health_check() -> HealthResponse:
    """Return deterministic service liveness information."""
    settings = get_settings()
    return HealthResponse(status="healthy", service=settings.app_name, phase=settings.app_phase)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Check service readiness",
)
@router.get(
    "/api/v1/ready",
    response_model=ReadinessResponse,
    summary="Check service readiness (Versioned)",
)
def readiness_check(response: Response) -> ReadinessResponse:
    """Return readiness without performing external side effects.

    The baseline verifies configuration only. Database probe is provided by /health/db.
    """
    settings = get_settings()
    result = ReadinessResponse(
        status="ready",
        service=settings.app_name,
        phase=settings.app_phase,
        environment=settings.environment,
        dependencies={
            "configuration": "ready",
            "database": "deferred",
            "providers": "not_configured",
        },
    )
    response.status_code = status.HTTP_200_OK
    return result


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    summary="Check active database connectivity",
)
def database_health_check(response: Response) -> DatabaseHealthResponse:
    """Execute a lightweight probe to verify active database connectivity."""

    settings = get_settings()
    is_healthy, msg = check_database_connection()
    dialect = settings.database_url.split("://")[0] if "://" in settings.database_url else "unknown"

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return DatabaseHealthResponse(status="unhealthy", database=msg, dialect=dialect)

    response.status_code = status.HTTP_200_OK
    return DatabaseHealthResponse(status="healthy", database="connected", dialect=dialect)
