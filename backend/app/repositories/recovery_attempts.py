"""Recovery attempt persistence repository.

Author: Karthikeya
Architectural layer: data access / repository.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.domain import RecoveryAttempt


class RecoveryAttemptRepository:
    """Encapsulates durable relational queries for recovery execution attempts."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, attempt_id: UUID) -> RecoveryAttempt | None:
        """Find a recovery attempt by its primary key UUID."""
        return self.session.scalar(
            select(RecoveryAttempt).where(RecoveryAttempt.id == attempt_id)
        )

    def find_by_idempotency_key(self, idempotency_key: str) -> RecoveryAttempt | None:
        """Find a recovery attempt by its unique idempotency key."""
        return self.session.scalar(
            select(RecoveryAttempt).where(RecoveryAttempt.idempotency_key == idempotency_key)
        )

    def find_by_case(self, case_id: UUID) -> list[RecoveryAttempt]:
        """Find all attempts belonging to a recovery case ordered monotonically by sequence."""
        stmt = (
            select(RecoveryAttempt)
            .where(RecoveryAttempt.case_id == case_id)
            .order_by(RecoveryAttempt.sequence_number.asc())
        )
        return list(self.session.scalars(stmt).all())

    def get_next_sequence_number(self, case_id: UUID) -> int:
        """Calculate the next monotonic sequence number for a new attempt within a case."""
        current_max = self.session.scalar(
            select(func.max(RecoveryAttempt.sequence_number)).where(
                RecoveryAttempt.case_id == case_id
            )
        )
        return (current_max or 0) + 1

    def save(self, attempt: RecoveryAttempt) -> RecoveryAttempt:
        """Persist or merge recovery attempt within active session."""
        self.session.add(attempt)
        return attempt
