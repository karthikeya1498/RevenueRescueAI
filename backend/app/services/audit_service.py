"""Audit trail application service.

Author: Karthikeya
Architectural layer: application service.

Responsibilities:
- Coordinates append-only compliance audit logging.
- Sequence-numbered audit trail generation.
- Read operations for incident analysis, debugging, and regulatory review.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import EntityNotFoundException
from app.mappers.audit_events import AuditEventMapper
from app.repositories.audit_events import AuditEventRepository
from app.repositories.recovery_cases import RecoveryCaseRepository
from app.schemas.audit_events import (
    AuditEventCreateDTO,
    AuditEventResponseDTO,
)


class AuditService:
    """Application service managing append-only compliance audit records."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit_repo = AuditEventRepository(session)
        self.case_repo = RecoveryCaseRepository(session)

    def record_event(self, dto: AuditEventCreateDTO) -> AuditEventResponseDTO:
        """Record an append-only audit record within a recovery case lifecycle."""
        case = self.case_repo.find_by_id(dto.case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(dto.case_id))

        next_seq = self.audit_repo.get_next_sequence_number(dto.case_id)
        event = AuditEventMapper.to_entity(dto, next_seq)
        self.session.add(event)
        self.session.commit()
        return AuditEventMapper.to_response(event)

    def get_audit_trail_for_case(self, case_id: UUID) -> list[AuditEventResponseDTO]:
        """Retrieve full monotonic audit history for a recovery case."""
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))

        events = self.audit_repo.find_by_case(case_id)
        return [AuditEventMapper.to_response(e) for e in events]

    def get_events_by_correlation_id(self, correlation_id: str) -> list[AuditEventResponseDTO]:
        """Retrieve all events linked by a single end-to-end tracing correlation ID."""
        events = self.audit_repo.find_by_correlation_id(correlation_id)
        return [AuditEventMapper.to_response(e) for e in events]
