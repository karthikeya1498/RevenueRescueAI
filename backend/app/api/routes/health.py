"""Health and readiness endpoints for RevenueRescue AI.

Author: Karthikeya
"""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import get_settings

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


@router.get("/health", response_model=HealthResponse, summary="Check service liveness")
def health_check() -> HealthResponse:
    """Return deterministic service liveness information."""

    settings = get_settings()
    return HealthResponse(status="healthy", service=settings.app_name, phase=settings.app_phase)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Check service readiness",
)
def readiness_check(response: Response) -> ReadinessResponse:
    """Return readiness without performing external side effects.

    The Phase 10 baseline verifies configuration only. Database and provider
    connectivity are deliberately represented as deferred until an explicit
    dependency check is introduced.
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
