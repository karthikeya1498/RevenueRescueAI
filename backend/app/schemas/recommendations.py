"""Pydantic schemas and DTOs for AI recovery recommendations.

Author: Karthikeya
Architectural layer: API DTO / contract.

Defines schemas for recommendation responses, failure diagnostics, risk bands,
and expected-value strategy comparisons.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ActionType, DecisionValidationStatus


class StrategyEstimateDTO(BaseModel):
    """Estimated financial utility for a candidate recovery strategy."""

    model_config = ConfigDict(from_attributes=True)

    strategy: str = Field(..., description="Approved recovery strategy identifier")
    action_type: ActionType = Field(..., description="Mapped domain action type")
    probability: Decimal = Field(..., description="Estimated conditional recovery probability")
    recovery_value_minor: int = Field(..., description="Gross recovery value in minor currency units")
    cost_minor: int = Field(..., description="Estimated intervention cost in minor units")
    expected_value_minor: int = Field(..., description="Net expected value in minor units")
    permitted: bool = Field(..., description="Whether strategy satisfies preconditions and policy")
    reasons: list[str] = Field(default_factory=list, description="Diagnostic reasons for candidate rating")


class CaseRecommendationDTO(BaseModel):
    """Structured, evidence-backed AI recovery recommendation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique recommendation / decision UUID")
    case_id: UUID = Field(..., description="Target recovery case UUID")
    decision_version: int = Field(..., description="Sequential decision version for this case")
    recommended_strategy: str = Field(..., description="Selected strategy from approved catalogue")
    action_type: ActionType = Field(..., description="Mapped domain action type")
    failure_category: str = Field(..., description="Normalized payment failure category")
    risk_band: str = Field(..., description="Assessed risk band (low, medium, high)")
    risk_score: int = Field(..., ge=0, le=100, description="Composite risk score [0, 100]")
    recovery_probability: Decimal | None = Field(None, description="Model-estimated recovery probability")
    confidence: Decimal | None = Field(None, description="Confidence score [0.0, 1.0]")
    expected_value_minor: int = Field(..., description="Net expected financial value in minor units")
    explanation: str = Field(..., description="Concise human-readable explanation")
    supporting_evidence: list[str] = Field(default_factory=list, description="Factual supporting evidence")
    limitations: list[str] = Field(default_factory=list, description="Model and scope boundary limitations")
    analysis_method: str = Field(default="hybrid_expected_value", description="Methodology used")
    model_version: str = Field(..., description="Version of estimator and rule catalogue")
    validation_status: DecisionValidationStatus = Field(
        default=DecisionValidationStatus.NOT_VALIDATED,
        description="Policy rule validation status (pending Phase 2.9)",
    )
    generated_at: datetime = Field(..., description="UTC timestamp when recommendation was formulated")
    candidate_strategies: list[StrategyEstimateDTO] = Field(
        default_factory=list, description="Comparative evaluation of candidate strategies"
    )
