"""Dashboard KPI and revenue analytics Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / external contract.

Defines schemas for authoritative financial KPIs, trend curves, and workflow status distribution.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DashboardMetricsResponseDTO(BaseModel):
    """Authoritative financial KPIs computed strictly in integer minor units."""

    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="USD", description="Currency code (ISO-4217 3-letter)")
    time_range: str = Field(default="all_time", description="Filter time window")
    at_risk_revenue_minor: int = Field(..., ge=0, description="Total at-risk revenue in integer minor units")
    recovered_revenue_minor: int = Field(..., ge=0, description="Total verified recovered revenue in minor units")
    recovery_rate_pct: str = Field(..., description="Revenue recovery rate percentage (e.g. '45.34%')")
    case_recovery_rate_pct: str = Field(..., description="Case recovery rate percentage (e.g. '45.50%')")
    total_at_risk_cases: int = Field(..., ge=0, description="Total count of at-risk cases")
    total_recovered_cases: int = Field(..., ge=0, description="Count of cases successfully recovered")
    escalated_cases: int = Field(..., ge=0, description="Count of cases escalated to human queue")
    verification_pending_cases: int = Field(..., ge=0, description="Count of cases pending payment verification")
    stopped_cases: int = Field(..., ge=0, description="Count of cases stopped or terminated by policy")
    safety_rate_pct: str = Field(default="100.00%", description="Proportion of interventions bounded by policy")
    generated_at: datetime = Field(..., description="UTC timestamp of calculation")


class RevenueTrendPointDTO(BaseModel):
    """Chronological point along the revenue recovery trendline."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(..., description="Time bucket boundary")
    recovered_minor: int = Field(..., ge=0, description="Verified recovered minor units in this bucket")
    at_risk_minor: int = Field(..., ge=0, description="At-risk revenue minor units in this bucket")


class RevenueTrendResponseDTO(BaseModel):
    """Chronological collection of time-bucketed points to render trend charts."""

    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="USD", description="Currency code")
    interval: str = Field(default="day", description="Grouping interval (hour, day, week)")
    points: list[RevenueTrendPointDTO] = Field(default_factory=list, description="Trendline points")


class WorkflowStatusDistributionDTO(BaseModel):
    """Breakdown of all recovery cases across workflow FSM states."""

    model_config = ConfigDict(extra="forbid")

    counts: dict[str, int] = Field(default_factory=dict, description="State to count mapping")
    total_cases: int = Field(..., ge=0, description="Total active and historical cases")
    generated_at: datetime = Field(..., description="UTC timestamp of calculation")
