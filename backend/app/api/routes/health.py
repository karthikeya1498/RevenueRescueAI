"""Health endpoint for the RevenueRescue AI foundation.

Author: Karthikeya
Architectural layer: API route.

The endpoint is intentionally local and deterministic so monitoring can use it
without invoking AI, payment providers, or persistence.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Stable response contract for service liveness."""

    status: str
    service: str
    phase: str


@router.get("/health", response_model=HealthResponse, summary="Check service health")
def health_check() -> HealthResponse:
    """Return deterministic foundation health information."""

    settings = get_settings()
    return HealthResponse(status="healthy", service=settings.app_name, phase=settings.app_phase)
