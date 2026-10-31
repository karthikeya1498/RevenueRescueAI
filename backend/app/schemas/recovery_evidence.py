"""Recovery evidence request and response Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / contract.

Enforces financial safety:
A payment is NEVER considered recovered simply because a client asserts it.
Authoritative verification requires verified provider event evidence with exact minor units.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RecoveryEvidenceCreateDTO(BaseModel):
    """Client/internal request schema for submitting verified settlement evidence."""

    model_config = ConfigDict(extra="forbid")

    intervention_id: str = Field(..., min_length=1, max_length=200, description="Intervention attempt identifier")
    provider_event_id: str = Field(..., min_length=1, max_length=200, description="Authoritative gateway event reference")
    failed_transaction_id: str = Field(..., min_length=1, max_length=200, description="Original failed transaction ID")
    successful_transaction_id: str = Field(..., min_length=1, max_length=200, description="Successful settlement transaction ID")
    amount_minor: int = Field(
        ...,
        ge=0,
        description="Settled recovery amount in integer minor units; float/double forbidden",
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="3-letter uppercase ISO currency code",
    )
    verified_at: datetime | None = Field(
        default=None,
        description="UTC timestamp of provider verification",
    )
    attribution_window_hours: int = Field(
        default=72,
        ge=1,
        le=720,
        description="Configured attribution window in hours",
    )
    attribution_reason: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Deterministic attribution rationale",
    )
    attributable: bool = Field(
        default=False,
        description="Whether this settlement is verified to be attributable to the intervention",
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw sanitized provider payload/signature verification proof",
    )


class RecoveryEvidenceResponseDTO(BaseModel):
    """Complete recovery evidence response representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique evidence record UUID")
    intervention_id: str = Field(..., description="Associated intervention attempt ID")
    provider_event_id: str = Field(..., description="Provider webhook event ID")
    failed_transaction_id: str = Field(..., description="Original failed transaction ID")
    successful_transaction_id: str = Field(..., description="Settled recovery transaction ID")
    amount_minor: int = Field(..., description="Settled amount in minor units")
    currency: str = Field(..., description="Currency code")
    verified_at: datetime = Field(..., description="Verification timestamp")
    attribution_window_hours: int = Field(..., description="Attribution window in hours")
    attribution_reason: str = Field(..., description="Attribution rule reason")
    attributable: bool = Field(..., description="Attributability status")
    evidence: dict[str, Any] = Field(default_factory=dict, description="Proof evidence dictionary")
    created_at: datetime = Field(..., description="Creation UTC timestamp")
    updated_at: datetime = Field(..., description="Update UTC timestamp")
