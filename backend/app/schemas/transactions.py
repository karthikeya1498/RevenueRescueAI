"""Transaction request and response Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / contract.

Enforces financial data integrity:
- Authoritative money amounts represented strictly as non-negative integer minor units.
- Currency represented strictly as 3-letter ISO-4217 uppercase code.
- Explicit rejection of float/double precision money fields.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TransactionStatus


class TransactionCreateDTO(BaseModel):
    """Client request schema for recording an ingested or simulated payment transaction."""

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID = Field(..., description="Associated customer UUID")
    provider: str = Field(
        default="synthetic",
        min_length=1,
        max_length=64,
        description="Payment provider name (e.g., stripe, razorpay, synthetic)",
    )
    external_transaction_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Authoritative payment identifier from provider/gateway",
    )
    amount_minor: int = Field(
        ...,
        ge=0,
        description="Exact monetary amount in integer minor units (cents/paise); float/double strictly forbidden",
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="3-letter uppercase ISO-4217 currency code (e.g., USD, EUR, INR)",
    )
    status: TransactionStatus = Field(
        ...,
        description="Transaction lifecycle status",
    )
    failure_code: str | None = Field(
        default=None,
        max_length=100,
        description="Normalized provider failure reason code",
    )
    failure_message_safe: str | None = Field(
        default=None,
        max_length=500,
        description="Sanitized, safe failure description without PII/credentials",
    )
    occurred_at: datetime | None = Field(
        default=None,
        description="Timestamp when payment event occurred in UTC (defaults to current time)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Safe metadata attributes (e.g. payment_method, gateway_response)",
    )


class TransactionSummaryDTO(BaseModel):
    """Compact transaction summary for embedded relational responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Internal transaction UUID")
    external_transaction_id: str = Field(..., description="External gateway reference")
    amount_minor: int = Field(..., description="Amount in integer minor units")
    currency: str = Field(..., description="Currency code")
    status: TransactionStatus = Field(..., description="Status")
    failure_code: str | None = Field(None, description="Failure reason code")
    occurred_at: datetime = Field(..., description="Occurrence timestamp")


class TransactionResponseDTO(BaseModel):
    """Complete transaction response representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Internal system UUID")
    customer_id: UUID = Field(..., description="Associated customer UUID")
    provider: str = Field(..., description="Provider gateway identifier")
    external_transaction_id: str = Field(..., description="Provider payment reference ID")
    amount_minor: int = Field(..., description="Transaction amount in integer minor units")
    currency: str = Field(..., description="3-letter ISO-4217 currency code")
    status: TransactionStatus = Field(..., description="Transaction status")
    failure_code: str | None = Field(None, description="Failure code if transaction failed")
    failure_message_safe: str | None = Field(None, description="Safe error message without PII")
    occurred_at: datetime = Field(..., description="Payment occurrence UTC timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Safe metadata map")
    created_at: datetime = Field(..., description="Record creation UTC timestamp")
    updated_at: datetime = Field(..., description="Record update UTC timestamp")
