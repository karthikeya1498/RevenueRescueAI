"""Recovery case persistence repository.

Author: Karthikeya
Architectural layer: data access / repository.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import RecoveryCaseState
from app.models.domain import RecoveryCase


class RecoveryCaseRepository:
    """Encapsulates durable relational queries for the RecoveryCase aggregate root."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, case_id: UUID) -> RecoveryCase | None:
        """Find a recovery case by internal UUID."""
        return self.session.scalar(select(RecoveryCase).where(RecoveryCase.id == case_id))

    def find_by_case_key(self, case_key: str) -> RecoveryCase | None:
        """Find a recovery case by its canonical business case key."""
        return self.session.scalar(select(RecoveryCase).where(RecoveryCase.case_key == case_key))

    def find_by_trigger_transaction_id(self, transaction_id: UUID) -> RecoveryCase | None:
        """Find the recovery case associated with a specific trigger transaction."""
        return self.session.scalar(
            select(RecoveryCase).where(RecoveryCase.trigger_transaction_id == transaction_id)
        )

    def find_by_customer(
        self,
        customer_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecoveryCase]:
        """Find all recovery cases associated with a specific customer."""
        stmt = (
            select(RecoveryCase)
            .where(RecoveryCase.customer_id == customer_id)
            .order_by(RecoveryCase.opened_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def list_cases(
        self,
        *,
        state: RecoveryCaseState | None = None,
        customer_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecoveryCase]:
        """Return a paginated list of recovery cases with optional state and customer filters."""
        stmt = select(RecoveryCase)
        if state is not None:
            stmt = stmt.where(RecoveryCase.state == state)
        if customer_id is not None:
            stmt = stmt.where(RecoveryCase.customer_id == customer_id)
        stmt = stmt.order_by(RecoveryCase.opened_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def count_by_state(self, state: RecoveryCaseState) -> int:
        """Count total recovery cases currently occupying a specific state."""
        return self.session.scalar(
            select(func.count(RecoveryCase.id)).where(RecoveryCase.state == state)
        ) or 0

    def save(self, case: RecoveryCase) -> RecoveryCase:
        """Persist or merge recovery case record within active session."""
        self.session.add(case)
        return case
