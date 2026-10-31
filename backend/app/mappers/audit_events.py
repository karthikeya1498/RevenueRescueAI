"""Audit event entity-to-DTO and DTO-to-entity pure mappers.

Author: Karthikeya
Architectural layer: mapper.

Rules:
- Maps immutable compliance audit records safely.
- Never reveals secrets or raw credentials in audit payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.domain import AuditEvent
from app.schemas.audit_events import (
    AuditEventCreateDTO,
    AuditEventResponseDTO,
)


class AuditEventMapper:
    """Stateless transformation utility between AuditEvent entities and DTOs."""

    @staticmethod
    def to_response(entity: AuditEvent) -> AuditEventResponseDTO:
        """Convert an AuditEvent persistence entity into an AuditEventResponseDTO."""
        return AuditEventResponseDTO(
            id=entity.id,
            case_id=entity.case_id,
            sequence_number=entity.sequence_number,
            event_type=entity.event_type,
            from_state=entity.from_state,
            to_state=entity.to_state,
            actor_type=entity.actor_type,
            actor_id=entity.actor_id,
            correlation_id=entity.correlation_id,
            event_time=entity.event_time,
            payload_safe=dict(entity.payload_safe) if entity.payload_safe else {},
        )

    @staticmethod
    def to_entity(dto: AuditEventCreateDTO, sequence_number: int) -> AuditEvent:
        """Instantiate a new detached AuditEvent entity."""
        return AuditEvent(
            id=uuid4(),
            case_id=dto.case_id,
            event_type=dto.event_type,
            from_state=dto.from_state,
            to_state=dto.to_state,
            actor_type=dto.actor_type,
            actor_id=dto.actor_id,
            correlation_id=dto.correlation_id,
            event_time=datetime.now(timezone.utc),
            payload_safe=dto.payload_safe,
            sequence_number=sequence_number,
        )
