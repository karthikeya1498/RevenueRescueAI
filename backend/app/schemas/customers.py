"""Customer request and response Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / contract.

Strictly decouples external HTTP payload representations from internal persistence models.
Never exposes sensitive or internal database implementation details.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import CustomerStatus


class CustomerCreateDTO(BaseModel):
    """Client request schema for registering a customer."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(
        default="synthetic",
        min_length=1,
        max_length=64,
        description="Billing or payment provider identifier (e.g., stripe, razorpay, synthetic)",
    )
    external_customer_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="External customer reference in the billing provider",
    )
    email: str | None = Field(
        default=None,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Customer email address for notifications and identification",
    )
    display_name: str | None = Field(
        default=None,
        max_length=200,
        description="Human-readable customer display name or company name",
    )
    status: CustomerStatus = Field(
        default=CustomerStatus.ACTIVE,
        description="Account subscription status",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary safe metadata attributes",
    )


class CustomerUpdateDTO(BaseModel):
    """Client request schema for updating customer attributes."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(
        default=None,
        max_length=200,
        description="Updated display name",
    )
    email: str | None = Field(
        default=None,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        description="Updated email address",
    )
    status: CustomerStatus | None = Field(
        default=None,
        description="Updated account status",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Updated metadata map",
    )


class CustomerSummaryDTO(BaseModel):
    """Compact summary of a customer for inclusion in relational lists."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Internal system UUID")
    external_customer_id: str = Field(..., description="External provider customer identifier")
    display_name: str | None = Field(None, description="Display name")
    status: CustomerStatus = Field(..., description="Customer status")


class CustomerResponseDTO(BaseModel):
    """Complete customer representation returned to API consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique internal customer UUID")
    provider: str = Field(..., description="Provider identifier")
    external_customer_id: str = Field(..., description="External provider customer reference")
    email: str | None = Field(None, description="Customer contact email")
    display_name: str | None = Field(None, description="Display name")
    status: CustomerStatus = Field(..., description="Customer status")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")
    created_at: datetime = Field(..., description="Creation UTC timestamp")
    updated_at: datetime = Field(..., description="Last modification UTC timestamp")
