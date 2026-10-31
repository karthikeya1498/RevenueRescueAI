"""Pydantic schemas and DTOs for Policy Engine REST endpoints (Phase 2.9 Step 4).

Architectural layer: API data transfer objects.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ActionType, ConsentStatus, ConsentType, PolicyDecisionStatus


class PolicyRuleCheckResponseDTO(BaseModel):
    """Structured result of an individual policy rule check."""

    model_config = ConfigDict(extra="ignore")

    rule_name: str
    status: str
    reason_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluationRequestDTO(BaseModel):
    """Request payload to trigger policy evaluation for an AI recommendation."""

    model_config = ConfigDict(extra="forbid")

    case_id: UUID
    recommendation_id: UUID
    proposed_action: ActionType | None = None
    communication_channel: str | None = Field(default=None, max_length=50)
    idempotency_key: str | None = Field(default=None, max_length=250)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluationResponseDTO(BaseModel):
    """Authoritative policy evaluation decision response."""

    model_config = ConfigDict(extra="ignore")

    decision_status: str
    case_id: UUID
    recommendation_id: UUID
    proposed_action: str
    policy_version: str
    is_approved: bool
    validation_status: str
    reasons: list[str]
    rule_results: list[PolicyRuleCheckResponseDTO]
    evaluated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class CustomerConsentCreateDTO(BaseModel):
    """Request payload to register a customer legal consent record."""

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    consent_type: ConsentType
    status: ConsentStatus = ConsentStatus.GRANTED
    merchant_id: str | None = Field(default=None, max_length=128)
    source: str = Field(default="checkout_agreement", max_length=120)
    evidence_reference: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None


class CustomerConsentResponseDTO(BaseModel):
    """Detailed response representation of a customer consent record."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    customer_id: UUID
    consent_type: str
    status: str
    merchant_id: str | None = None
    granted_at: datetime
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    source: str
    evidence_reference: str | None = None
    version: int
    is_valid: bool
