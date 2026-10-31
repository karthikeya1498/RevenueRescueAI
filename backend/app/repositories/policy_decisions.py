"""Policy Decision persistence repository.

Architectural layer: data access / repository.
"""

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.domain import PolicyDecision


class PolicyDecisionRepository:
    """Encapsulates durable relational queries for PolicyDecision audit records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, decision_id: UUID) -> PolicyDecision | None:
        """Find a single policy decision by internal primary key UUID."""
        return self.session.scalar(
            select(PolicyDecision).where(PolicyDecision.id == decision_id)
        )

    def find_by_case(self, case_id: UUID) -> list[PolicyDecision]:
        """Return all historical policy decisions for a given recovery case, ordered newest first."""
        stmt = (
            select(PolicyDecision)
            .where(PolicyDecision.case_id == case_id)
            .order_by(desc(PolicyDecision.evaluated_at))
        )
        return list(self.session.scalars(stmt).all())

    def find_by_idempotency_key(
        self, case_id: UUID, idempotency_key: str
    ) -> PolicyDecision | None:
        """Find an existing policy decision matching case and idempotency key."""
        stmt = select(PolicyDecision).where(
            PolicyDecision.case_id == case_id,
            PolicyDecision.idempotency_key == idempotency_key,
        )
        return self.session.scalar(stmt)

    def save(self, decision: PolicyDecision) -> PolicyDecision:
        """Persist or merge policy decision within active database session."""
        self.session.add(decision)
        return decision
