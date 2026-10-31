"""Agent decision request and response Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / contract.

Defines schemas for AI recommendation formulation, confidence evaluation, and preview requests.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ActionType, DecisionValidationStatus


class DecisionPreviewRequestDTO(BaseModel):
    """Client request schema for dry-run simulation of decision intelligence."""

    model_config = ConfigDict(extra="forbid")

    amount_minor: int = Field(..., ge=0, description="Transaction amount in integer minor units")
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="3-letter uppercase ISO currency code",
    )
    failure_code: str | None = Field(None, max_length=100, description="Gateway failure code")
    failure_message: str | None = Field(None, max_length=500, description="Gateway error message")
    prior_attempts: int = Field(default=0, ge=0, le=20, description="Number of prior recovery attempts")
    customer_success_rate: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Historical customer transaction success probability",
    )
    alternate_method_available: bool = Field(default=True, description="Whether secondary card/method exists")
    unusual_velocity: bool = Field(default=False, description="Whether velocity flag is active")
    customer_restricted: bool = Field(default=False, description="Whether account is suspended/restricted")


class AgentDecisionCreateDTO(BaseModel):
    """Internal schema for recording an evaluated AI/policy recommendation."""

    model_config = ConfigDict(extra="forbid")

    case_id: UUID = Field(..., description="Target recovery case UUID")
    attempt_id: UUID | None = Field(None, description="Optional attempt linked to this decision")
    action_type: ActionType = Field(..., description="Recommended intervention action")
    reason_code: str = Field(..., min_length=1, max_length=120, description="Reason code")
    rationale_safe: str | None = Field(None, max_length=2000, description="Safe explanatory rationale")
    confidence: Decimal | None = Field(
        None,
        ge=Decimal("0.0"),
        le=Decimal("1.0"),
        description="Confidence score bounded between 0.0 and 1.0",
    )
    raw_response_hash: str | None = Field(None, max_length=128, description="SHA-256 hash of raw model response")
    validation_status: DecisionValidationStatus = Field(
        default=DecisionValidationStatus.NOT_VALIDATED,
        description="Policy rule validation status",
    )


class AgentDecisionResponseDTO(BaseModel):
    """Complete agent decision representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Decision UUID")
    case_id: UUID = Field(..., description="Associated case UUID")
    attempt_id: UUID | None = Field(None, description="Associated attempt UUID if executed")
    decision_version: int = Field(..., description="Decision sequence number/version")
    action_type: ActionType = Field(..., description="Recommended action")
    reason_code: str = Field(..., description="Machine-readable reason code")
    rationale_safe: str | None = Field(None, description="Explanatory rationale")
    confidence: Decimal | None = Field(None, description="Model confidence score")
    raw_response_hash: str | None = Field(None, description="Model prompt/response hash")
    validation_status: DecisionValidationStatus = Field(..., description="Validation outcome")
