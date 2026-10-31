"""Pydantic schemas and DTOs for event ingestion, normalization, and deduplication.

Author: Karthikeya
Architectural layer: API data transfer objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import CanonicalEventType, EventProcessingStatus


class CanonicalEventDTO(BaseModel):
    """Canonical internal normalized event model.
    
    All source-specific payloads (Stripe, Razorpay, simulator, direct) are normalized
    into this uniform domain representation before persistence and validation.
    """

    model_config = ConfigDict(extra="forbid")

    external_event_id: str = Field(
        ..., min_length=1, max_length=200, description="Provider or source event ID"
    )
    event_type: str = Field(
        ..., min_length=1, max_length=160, description="Canonical event type identifier"
    )
    provider: str = Field(
        ..., min_length=1, max_length=64, description="Gateway or source origin (e.g., stripe, razorpay, synthetic)"
    )
    occurred_at: datetime = Field(
        ..., description="Timestamp when event occurred at source (UTC)"
    )
    customer_reference: str = Field(
        ..., min_length=1, max_length=128, description="External customer reference"
    )
    payment_reference: str | None = Field(
        default=None, max_length=128, description="External transaction or payment intent reference"
    )
    subscription_reference: str | None = Field(
        default=None, max_length=128, description="Subscription or recurring billing ID"
    )
    invoice_reference: str | None = Field(
        default=None, max_length=128, description="Invoice reference ID"
    )
    checkout_session_id: str | None = Field(
        default=None, max_length=128, description="Checkout session or cart ID for abandonments"
    )
    amount_minor: int = Field(
        default=0, ge=0, description="Exact transaction amount in minor currency units (cents)"
    )
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="3-letter uppercase ISO currency code"
    )
    failure_code: str | None = Field(
        default=None, max_length=100, description="Normalized failure classification code"
    )
    failure_message: str | None = Field(
        default=None, max_length=500, description="Sanitized human-readable failure reason"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Sanitized non-sensitive diagnostic metadata"
    )


class EventIngestRequestDTO(BaseModel):
    """Ingestion request payload for POST /api/v1/events."""

    model_config = ConfigDict(extra="ignore")

    event_id: str | None = Field(
        default=None, max_length=200, description="Optional explicit event ID; generated if omitted"
    )
    event_type: str = Field(
        default=CanonicalEventType.PAYMENT_FAILED.value, description="Event type"
    )
    provider: str = Field(
        default="synthetic", max_length=64, description="Source provider name"
    )
    occurred_at: datetime | None = Field(
        default=None, description="Event occurrence timestamp (UTC)"
    )
    customer_reference: str = Field(
        ..., min_length=1, max_length=128, description="Customer identifier"
    )
    payment_reference: str | None = Field(
        default=None, max_length=128, description="Payment/Transaction identifier"
    )
    subscription_reference: str | None = Field(
        default=None, max_length=128, description="Subscription identifier"
    )
    invoice_reference: str | None = Field(
        default=None, max_length=128, description="Invoice identifier"
    )
    checkout_session_id: str | None = Field(
        default=None, max_length=128, description="Checkout session ID"
    )
    amount_minor: int = Field(
        default=0, ge=0, description="Amount in minor units (e.g. cents)"
    )
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="3-letter uppercase ISO currency code"
    )
    failure_code: str | None = Field(
        default=None, max_length=100, description="Failure reason code"
    )
    failure_message: str | None = Field(
        default=None, max_length=500, description="Failure message"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Sanitized metadata"
    )


class SimulateFailureRequestDTO(BaseModel):
    """Request payload for development simulator endpoint POST /api/v1/events/simulate-failure."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(
        default="cus_sim_9A12F", min_length=1, max_length=128, description="Customer ID"
    )
    amount_minor: int = Field(
        default=842000, ge=0, description="Amount in minor units (cents)"
    )
    currency: str = Field(
        default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$", description="3-letter uppercase ISO currency"
    )
    failure_code: str = Field(
        default="insufficient_funds", max_length=100, description="Decline or failure code"
    )
    failure_message: str = Field(
        default="Card has insufficient funds.", max_length=500, description="Safe failure description"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional simulation tags"
    )


class EventIngestResponseDTO(BaseModel):
    """Standardized response schema for event ingress."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool = Field(..., description="Whether event was accepted into the system")
    duplicate: bool = Field(..., description="Whether event was identified as a duplicate")
    event_id: str = Field(..., description="Internal UUID of persisted event record")
    external_event_id: str = Field(..., description="Source-provided external event ID")
    event_type: str = Field(..., description="Canonical event type")
    status: str = Field(..., description="Ingestion processing status (ACCEPTED, DUPLICATE)")
    reason: str = Field(..., description="Detailed status or deduplication explanation")
    correlation_id: str = Field(..., description="End-to-end tracing correlation ID")
    occurred_at: datetime = Field(..., description="Source event timestamp")
    case_id: str | None = Field(default=None, description="Generated or matched recovery case UUID if eligible")
    case_key: str | None = Field(default=None, description="Generated or matched recovery case business key")



class EventSummaryDTO(BaseModel):
    """Compact summary of an ingested event for paginated listings."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    external_event_id: str
    event_type: str
    signature_verified: bool
    processed: bool
    ingestion_status: str
    created_at: datetime
    updated_at: datetime


class EventDetailDTO(BaseModel):
    """Detailed representation of an ingested event."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    external_event_id: str
    event_type: str
    payload_hash: str
    signature_verified: bool
    processed: bool
    ingestion_status: str
    payload_safe: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PaginatedEventsDTO(BaseModel):
    """Paginated collection envelope for ingested events."""

    items: list[EventSummaryDTO]
    total: int
    page: int
    limit: int
    pages: int
