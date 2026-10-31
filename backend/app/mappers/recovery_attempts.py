"""Recovery attempt entity-to-DTO and DTO-to-entity pure mappers.

Author: Karthikeya
Architectural layer: mapper.

Rules:
- Maps execution attempts without lazy-loading dependencies.
- Explicit sequence number assignment and idempotency preservation.
"""

from __future__ import annotations

from uuid import uuid4

from app.models.domain import RecoveryAttempt
from app.schemas.recovery_attempts import (
    RecoveryAttemptCreateDTO,
    RecoveryAttemptResponseDTO,
    RecoveryAttemptSummaryDTO,
)


class RecoveryAttemptMapper:
    """Stateless transformation utility between RecoveryAttempt entities and DTOs."""

    @staticmethod
    def to_response(entity: RecoveryAttempt) -> RecoveryAttemptResponseDTO:
        """Convert a RecoveryAttempt persistence entity into a RecoveryAttemptResponseDTO."""
        return RecoveryAttemptResponseDTO(
            id=entity.id,
            case_id=entity.case_id,
            sequence_number=entity.sequence_number,
            status=entity.status,
            action_type=entity.action_type,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
            outcome=entity.outcome,
            provider_reference=entity.provider_reference,
            idempotency_key=entity.idempotency_key,
            error_class=entity.error_class,
            error_safe_message=entity.error_safe_message,
            metadata=dict(entity.metadata_json) if entity.metadata_json else {},
        )

    @staticmethod
    def to_summary(entity: RecoveryAttempt) -> RecoveryAttemptSummaryDTO:
        """Convert a RecoveryAttempt persistence entity into a compact RecoveryAttemptSummaryDTO."""
        return RecoveryAttemptSummaryDTO(
            id=entity.id,
            sequence_number=entity.sequence_number,
            action_type=entity.action_type,
            status=entity.status,
            provider_reference=entity.provider_reference,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(dto: RecoveryAttemptCreateDTO, sequence_number: int) -> RecoveryAttempt:
        """Instantiate a new detached RecoveryAttempt entity with a monotonic sequence number."""
        return RecoveryAttempt(
            id=uuid4(),
            case_id=dto.case_id,
            sequence_number=sequence_number,
            status=dto.status,
            action_type=dto.action_type,
            started_at=None,
            finished_at=None,
            outcome=None,
            provider_reference=None,
            idempotency_key=dto.idempotency_key,
            error_class=None,
            error_safe_message=None,
            metadata_json=dto.metadata,
        )
