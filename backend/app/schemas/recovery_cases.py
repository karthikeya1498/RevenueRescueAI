"""Recovery case request and response Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / contract.

Defines schemas for recovery lifecycle management, state transitions, and operator interventions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ActorType, RecoveryCaseState
from app.schemas.customers import CustomerResponseDTO, CustomerSummaryDTO
from app.schemas.transactions import TransactionResponseDTO, TransactionSummaryDTO


class RecoveryCaseCreateDTO(BaseModel):
    """Client/internal request schema for opening a revenue recovery case."""

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID = Field(..., description="Customer whose payment failed")
    trigger_transaction_id: UUID = Field(..., description="Failed transaction triggering this case")
    case_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Optional unique business case key; generated automatically if omitted",
    )
    priority: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Queue processing priority (lower number = higher urgency)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Initial context metadata (e.g., failure codes, customer tier)",
    )


class RecoveryCaseUpdateDTO(BaseModel):
    """Request schema for updating case metadata or priority."""

    model_config = ConfigDict(extra="forbid")

    priority: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Updated queue priority",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Updated context metadata map",
    )


class CaseStateTransitionDTO(BaseModel):
    """Request schema for recording an explicit state transition on a case."""

    model_config = ConfigDict(extra="forbid")

    to_state: RecoveryCaseState = Field(..., description="Target state in the recovery finite state machine")
    reason_code: str = Field(
        ...,
        min_length=3,
        max_length=120,
        description="Machine-readable reason for the transition",
    )
    actor_type: ActorType = Field(
        default=ActorType.OPERATOR,
        description="Entity triggering the state change",
    )
    correlation_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Tracing correlation identifier for end-to-end auditability",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for audit recording",
    )


class ExecuteRetryRequestDTO(BaseModel):
    """Request schema for operator-triggered payment retry."""

    model_config = ConfigDict(extra="forbid")

    justification: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Operator justification for initiating retry attempt",
    )


class StopRecoveryRequestDTO(BaseModel):
    """Request schema for operator-initiated recovery termination."""

    model_config = ConfigDict(extra="forbid")

    stop_reason: str = Field(
        ...,
        min_length=3,
        max_length=120,
        description="Formal reason code for stopping recovery",
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional explanatory notes from operator",
    )


class RecoveryCaseSummaryDTO(BaseModel):
    """Compact recovery case representation for list/dashboard views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique case UUID")
    case_key: str = Field(..., description="Unique business case key")
    customer_id: UUID = Field(..., description="Associated customer UUID")
    trigger_transaction_id: UUID = Field(..., description="Trigger transaction UUID")
    state: RecoveryCaseState = Field(..., description="Current FSM state")
    priority: int = Field(..., description="Case priority")
    opened_at: datetime = Field(..., description="Case opening UTC timestamp")
    last_state_changed_at: datetime = Field(..., description="Last state change UTC timestamp")
    closed_at: datetime | None = Field(None, description="Case closure UTC timestamp if closed")


class RecoveryCaseResponseDTO(BaseModel):
    """Complete recovery case representation returned by API endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique case UUID")
    case_key: str = Field(..., description="Canonical case identifier")
    customer_id: UUID = Field(..., description="Customer UUID")
    trigger_transaction_id: UUID = Field(..., description="Trigger transaction UUID")
    state: RecoveryCaseState = Field(..., description="Current state in lifecycle")
    priority: int = Field(..., description="Priority value")
    version: int = Field(..., description="Optimistic locking version")
    opened_at: datetime = Field(..., description="Opening timestamp")
    last_state_changed_at: datetime = Field(..., description="State change timestamp")
    closed_at: datetime | None = Field(None, description="Closure timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata attributes")


class CaseSummaryItemDTO(BaseModel):
    """Enriched recovery case representation including embedded customer and transaction summaries."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique case UUID")
    case_key: str = Field(..., description="Canonical case identifier")
    customer: CustomerSummaryDTO | None = Field(None, description="Embedded customer summary")
    trigger_transaction: TransactionSummaryDTO | None = Field(
        None, description="Embedded trigger transaction summary"
    )
    state: RecoveryCaseState = Field(..., description="Current FSM state")
    priority: int = Field(..., description="Queue processing priority")
    attempts_count: int = Field(default=0, description="Total recovery attempts recorded")
    opened_at: datetime = Field(..., description="Opening timestamp")
    last_state_changed_at: datetime = Field(..., description="Timestamp of latest state change")


class CaseDetailResponseDTO(BaseModel):
    """Deep recovery case representation including related entities and audit timeline."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique case UUID")
    case_key: str = Field(..., description="Canonical case identifier")
    customer: CustomerResponseDTO | None = Field(None, description="Full customer details")
    trigger_transaction: TransactionResponseDTO | None = Field(
        None, description="Full trigger transaction details"
    )
    state: RecoveryCaseState = Field(..., description="Current lifecycle state")
    priority: int = Field(..., description="Case priority")
    version: int = Field(..., description="Optimistic locking version")
    opened_at: datetime = Field(..., description="Opening timestamp")
    last_state_changed_at: datetime = Field(..., description="Timestamp of latest state change")
    closed_at: datetime | None = Field(None, description="Closure timestamp if terminal")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata map")
    attempts_count: int = Field(default=0, description="Count of recovery attempts")

