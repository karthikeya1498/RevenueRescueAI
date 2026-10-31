"""Agent decision persistence repository.

Author: Karthikeya
Architectural layer: data access / repository.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import AgentDecision


class AgentDecisionRepository:
    """Encapsulates durable relational queries for AI and Policy recommendations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, decision_id: UUID) -> AgentDecision | None:
        """Find an agent decision record by internal primary key UUID."""
        return self.session.scalar(select(AgentDecision).where(AgentDecision.id == decision_id))

    def find_by_case(self, case_id: UUID) -> list[AgentDecision]:
        """Find all decisions formulated for a case ordered by version."""
        stmt = (
            select(AgentDecision)
            .where(AgentDecision.case_id == case_id)
            .order_by(AgentDecision.decision_version.asc())
        )
        return list(self.session.scalars(stmt).all())

    def find_latest_by_case(self, case_id: UUID) -> AgentDecision | None:
        """Find the most recent decision version formulated for a case."""
        stmt = (
            select(AgentDecision)
            .where(AgentDecision.case_id == case_id)
            .order_by(AgentDecision.decision_version.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def find_by_attempt(self, attempt_id: UUID) -> AgentDecision | None:
        """Find the decision that authorized a specific execution attempt."""
        return self.session.scalar(
            select(AgentDecision).where(AgentDecision.attempt_id == attempt_id)
        )

    def save(self, decision: AgentDecision) -> AgentDecision:
        """Persist or merge an agent decision within active session."""
        self.session.add(decision)
        return decision
