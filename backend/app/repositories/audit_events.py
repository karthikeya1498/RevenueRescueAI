"""Audit event persistence repository.

Author: Karthikeya
Architectural layer: data access / repository.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import ActorType, RecoveryCaseState
from app.models.domain import AuditEvent


class AuditEventRepository:
    """Encapsulates append-only relational persistence for compliance audit trails."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, event_id: UUID) -> AuditEvent | None:
        """Find an audit event by primary key UUID."""
        return self.session.scalar(select(AuditEvent).where(AuditEvent.id == event_id))

    def find_by_case(self, case_id: UUID) -> list[AuditEvent]:
        """Find all audit events for a recovery case in strict monotonic sequence."""
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id)
            .order_by(AuditEvent.sequence_number.asc())
        )
        return list(self.session.scalars(stmt).all())

    def find_by_correlation_id(self, correlation_id: str) -> list[AuditEvent]:
        """Find all audit records stamped with a specific correlation identifier."""
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.correlation_id == correlation_id)
            .order_by(AuditEvent.event_time.asc())
        )
        return list(self.session.scalars(stmt).all())

    def get_next_sequence_number(self, case_id: UUID) -> int:
        """Calculate the next monotonic sequence number for a case's audit log."""
        current_max = self.session.scalar(
            select(func.max(AuditEvent.sequence_number)).where(AuditEvent.case_id == case_id)
        )
        return (current_max or 0) + 1

    def record(
        self,
        *,
        case_id: UUID,
        event_type: str,
        actor_type: ActorType,
        correlation_id: str,
        payload_safe: dict,
        from_state: RecoveryCaseState | None = None,
        to_state: RecoveryCaseState | None = None,
        actor_id: str | None = None,
    ) -> AuditEvent:
        """Create and append an immutable audit record within the current transaction."""
        seq = self.get_next_sequence_number(case_id)
        event = AuditEvent(
            id=uuid4(),
            case_id=case_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            from_state=from_state,
            to_state=to_state,
            event_time=datetime.now(timezone.utc),
            payload_safe=payload_safe,
            sequence_number=seq,
        )
        self.session.add(event)
        return event

    def save(self, event: AuditEvent) -> AuditEvent:
        """Persist an audit event."""
        self.session.add(event)
        return event
