"""Audit event request and response Data Transfer Objects (DTOs).

Author: Karthikeya
Architectural layer: API DTO / contract.

Encapsulates immutable compliance audit records for financial tracing and security review.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import ActorType, RecoveryCaseState


class AuditEventCreateDTO(BaseModel):
    """Internal schema for recording an append-only audit log entry."""

    model_config = ConfigDict(extra="forbid")

    case_id: UUID = Field(..., description="Target recovery case UUID")
    event_type: str = Field(..., min_length=1, max_length=120, description="Audit event category identifier")
    actor_type: ActorType = Field(..., description="Actor category initiating event")
    correlation_id: str = Field(..., min_length=1, max_length=200, description="Tracing correlation ID")
    actor_id: str | None = Field(None, max_length=200, description="Actor username or service ID")
    payload_safe: dict[str, Any] = Field(default_factory=dict, description="Sanitized audit payload")
    from_state: RecoveryCaseState | None = Field(None, description="Source lifecycle state")
    to_state: RecoveryCaseState | None = Field(None, description="Target lifecycle state")


class AuditEventResponseDTO(BaseModel):
    """Complete audit record representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Audit record UUID")
    case_id: UUID = Field(..., description="Recovery case UUID")
    sequence_number: int = Field(..., description="Monotonic sequence number within case")
    event_type: str = Field(..., description="Event type name")
    from_state: RecoveryCaseState | None = Field(None, description="Source state")
    to_state: RecoveryCaseState | None = Field(None, description="Destination state")
    actor_type: ActorType = Field(..., description="Actor category")
    actor_id: str | None = Field(None, description="Actor identifier")
    correlation_id: str = Field(..., description="Correlation ID")
    event_time: datetime = Field(..., description="Event occurrence UTC timestamp")
    payload_safe: dict[str, Any] = Field(default_factory=dict, description="Sanitized event details")
