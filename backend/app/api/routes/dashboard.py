"""Dashboard analytics and financial metrics API endpoints.

Author: Karthikeya
Architectural layer: API controller.

Endpoints:
- GET /api/v1/dashboard/metrics: Authoritative financial KPIs in integer minor units.
- GET /api/v1/dashboard/summary: Alias to metrics.
- GET /api/v1/dashboard/trend: Chronological trendline points.
- GET /api/v1/dashboard/revenue-trends: Alias to trend.
- GET /api/v1/dashboard/workflow-status: State breakdown across recovery FSM states.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.domain import User
from app.schemas.dashboard import (
    DashboardMetricsResponseDTO,
    RevenueTrendResponseDTO,
    WorkflowStatusDistributionDTO,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get(
    "/metrics",
    response_model=DashboardMetricsResponseDTO,
    summary="Retrieve authoritative dashboard financial KPIs",
)
def get_dashboard_metrics(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    currency: str = Query("USD", pattern=r"^[A-Z]{3}$", description="3-letter currency code"),
    time_range: str = Query("all_time", description="Filter time window"),
) -> DashboardMetricsResponseDTO:
    """Return pre-aggregated, authoritative financial metrics computed in integer minor units."""
    service = DashboardService(db)
    return service.get_metrics(currency=currency, time_range=time_range)


@router.get(
    "/summary",
    response_model=DashboardMetricsResponseDTO,
    summary="Retrieve dashboard summary KPIs (Alias)",
)
def get_dashboard_summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    currency: str = Query("USD", pattern=r"^[A-Z]{3}$"),
    time_range: str = Query("all_time"),
) -> DashboardMetricsResponseDTO:
    """Alias endpoint for dashboard summary metrics."""
    service = DashboardService(db)
    return service.get_metrics(currency=currency, time_range=time_range)


@router.get(
    "/trend",
    response_model=RevenueTrendResponseDTO,
    summary="Retrieve revenue trendline points",
)
def get_revenue_trend(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    currency: str = Query("USD", pattern=r"^[A-Z]{3}$"),
    interval: str = Query("day", pattern=r"^(hour|day|week)$"),
) -> RevenueTrendResponseDTO:
    """Delivers chronological time-bucketed points to render recovery trend curves."""
    service = DashboardService(db)
    return service.get_revenue_trend(currency=currency, interval=interval)


@router.get(
    "/revenue-trends",
    response_model=RevenueTrendResponseDTO,
    summary="Retrieve revenue trends (Alias)",
)
def get_revenue_trends_alias(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    currency: str = Query("USD", pattern=r"^[A-Z]{3}$"),
    interval: str = Query("day", pattern=r"^(hour|day|week)$"),
) -> RevenueTrendResponseDTO:
    """Alias endpoint for revenue trend points."""
    service = DashboardService(db)
    return service.get_revenue_trend(currency=currency, interval=interval)


@router.get(
    "/workflow-status",
    response_model=WorkflowStatusDistributionDTO,
    summary="Retrieve recovery workflow state distribution",
)
def get_workflow_status(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> WorkflowStatusDistributionDTO:
    """Returns distribution of cases across all FSM recovery states."""
    service = DashboardService(db)
    return service.get_workflow_status()
