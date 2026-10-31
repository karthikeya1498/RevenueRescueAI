"""Recovery evidence persistence repository.

Author: Karthikeya
Architectural layer: data access / repository.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import RecoveryEvidence


class RecoveryEvidenceRepository:
    """Encapsulates durable relational queries for verified outcome settlement evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, evidence_id: UUID) -> RecoveryEvidence | None:
        """Find an evidence record by internal primary key UUID."""
        return self.session.scalar(
            select(RecoveryEvidence).where(RecoveryEvidence.id == evidence_id)
        )

    def find_by_provider_event_id(self, provider_event_id: str) -> RecoveryEvidence | None:
        """Find verified evidence by authoritative provider event identifier."""
        return self.session.scalar(
            select(RecoveryEvidence).where(
                RecoveryEvidence.provider_event_id == provider_event_id
            )
        )

    def find_by_failed_transaction_id(
        self, failed_transaction_id: str
    ) -> list[RecoveryEvidence]:
        """Find all evidence records associated with a specific failed transaction."""
        stmt = (
            select(RecoveryEvidence)
            .where(RecoveryEvidence.failed_transaction_id == failed_transaction_id)
            .order_by(RecoveryEvidence.verified_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def find_by_intervention_id(self, intervention_id: str) -> list[RecoveryEvidence]:
        """Find all evidence records linked to a specific intervention attempt."""
        stmt = (
            select(RecoveryEvidence)
            .where(RecoveryEvidence.intervention_id == intervention_id)
            .order_by(RecoveryEvidence.verified_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def save(self, evidence: RecoveryEvidence) -> RecoveryEvidence:
        """Persist or merge recovery evidence within active session."""
        self.session.add(evidence)
        return evidence
