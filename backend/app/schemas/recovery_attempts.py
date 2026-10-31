"""Recovery attempt request and response Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / contract.

Encapsulates individual bounded execution attempts within a recovery workflow.
Enforces idempotency keys, safe error sanitization, and execution metrics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ActionType, RecoveryAttemptStatus


class RecoveryAttemptCreateDTO(BaseModel):
    """Internal/client request schema to record a planned recovery attempt."""

    model_config = ConfigDict(extra="forbid")

    case_id: UUID = Field(..., description="Recovery case UUID")
    action_type: ActionType = Field(..., description="Chosen recovery intervention action")
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=250,
        description="Unique idempotency key ensuring replay safety",
    )
    status: RecoveryAttemptStatus = Field(
        default=RecoveryAttemptStatus.PLANNED,
        description="Initial status of the attempt",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution context metadata",
    )


class RecoveryAttemptSummaryDTO(BaseModel):
    """Compact summary of a recovery attempt for embedded timeline lists."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Attempt UUID")
    sequence_number: int = Field(..., description="Monotonic sequence number within case")
    action_type: ActionType = Field(..., description="Intervention action type")
    status: RecoveryAttemptStatus = Field(..., description="Current attempt execution status")
    provider_reference: str | None = Field(None, description="External provider operation reference")
    started_at: datetime | None = Field(None, description="Start timestamp")
    finished_at: datetime | None = Field(None, description="Finish timestamp")


class RecoveryAttemptResponseDTO(BaseModel):
    """Complete recovery attempt response representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique attempt UUID")
    case_id: UUID = Field(..., description="Associated case UUID")
    sequence_number: int = Field(..., description="Sequence number (1, 2, ...)")
    status: RecoveryAttemptStatus = Field(..., description="Attempt status")
    action_type: ActionType = Field(..., description="Intervention action type")
    started_at: datetime | None = Field(None, description="Start UTC timestamp")
    finished_at: datetime | None = Field(None, description="Finish UTC timestamp")
    outcome: str | None = Field(None, description="Execution outcome summary")
    provider_reference: str | None = Field(None, description="Provider transaction or dispatch reference")
    idempotency_key: str = Field(..., description="Unique idempotency key")
    error_class: str | None = Field(None, description="Error classification if failed")
    error_safe_message: str | None = Field(None, description="Sanitized safe error message")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Safe metadata map")
