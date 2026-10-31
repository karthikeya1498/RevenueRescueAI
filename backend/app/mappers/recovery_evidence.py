"""Recovery evidence entity-to-DTO and DTO-to-entity pure mappers.

Author: Karthikeya
Architectural layer: mapper.

Rules:
- Maps verified settlement evidence preserving exact integer minor monetary values.
- Pure functions without network or database interaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.domain import RecoveryEvidence
from app.schemas.recovery_evidence import (
    RecoveryEvidenceCreateDTO,
    RecoveryEvidenceResponseDTO,
)


class RecoveryEvidenceMapper:
    """Stateless transformation utility between RecoveryEvidence entities and DTOs."""

    @staticmethod
    def to_response(entity: RecoveryEvidence) -> RecoveryEvidenceResponseDTO:
        """Convert a RecoveryEvidence persistence entity into a RecoveryEvidenceResponseDTO."""
        return RecoveryEvidenceResponseDTO(
            id=entity.id,
            intervention_id=entity.intervention_id,
            provider_event_id=entity.provider_event_id,
            failed_transaction_id=entity.failed_transaction_id,
            successful_transaction_id=entity.successful_transaction_id,
            amount_minor=entity.amount_minor,
            currency=entity.currency,
            verified_at=entity.verified_at,
            attribution_window_hours=entity.attribution_window_hours,
            attribution_reason=entity.attribution_reason,
            attributable=entity.attributable,
            evidence=dict(entity.evidence_json) if entity.evidence_json else {},
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_entity(dto: RecoveryEvidenceCreateDTO) -> RecoveryEvidence:
        """Instantiate a new detached RecoveryEvidence entity."""
        verified_time = dto.verified_at or datetime.now(timezone.utc)
        return RecoveryEvidence(
            id=uuid4(),
            intervention_id=dto.intervention_id,
            provider_event_id=dto.provider_event_id,
            failed_transaction_id=dto.failed_transaction_id,
            successful_transaction_id=dto.successful_transaction_id,
            amount_minor=dto.amount_minor,
            currency=dto.currency,
            verified_at=verified_time,
            attribution_window_hours=dto.attribution_window_hours,
            attribution_reason=dto.attribution_reason,
            attributable=dto.attributable,
            evidence_json=dto.evidence,
        )
