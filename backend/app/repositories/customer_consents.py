"""Customer Consent persistence repository.

Architectural layer: data access / repository.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.enums import ConsentStatus, ConsentType
from app.models.domain import CustomerConsent


class CustomerConsentRepository:
    """Encapsulates durable relational queries for the CustomerConsent entity."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, consent_id: UUID) -> CustomerConsent | None:
        """Find a single consent record by internal primary key UUID."""
        return self.session.scalar(
            select(CustomerConsent).where(CustomerConsent.id == consent_id)
        )

    def find_by_customer(
        self,
        customer_id: UUID,
        consent_type: ConsentType | None = None,
    ) -> list[CustomerConsent]:
        """Return all consent records for a given customer, ordered by granted_at desc."""
        stmt = select(CustomerConsent).where(CustomerConsent.customer_id == customer_id)
        if consent_type is not None:
            stmt = stmt.where(CustomerConsent.consent_type == consent_type)
        stmt = stmt.order_by(desc(CustomerConsent.granted_at))
        return list(self.session.scalars(stmt).all())

    def find_active_consent(
        self,
        customer_id: UUID,
        consent_type: ConsentType,
        at_time: datetime | None = None,
    ) -> CustomerConsent | None:
        """Query for the latest legally active, unrevoked, unexpired consent.
        
        Fail-Closed Semantics:
        - Must be GRANTED status.
        - Must have revoked_at is NULL (or revoked_at > target time).
        - Must have expires_at is NULL or expires_at > target time.
        """
        now = at_time or datetime.now(timezone.utc)
        stmt = (
            select(CustomerConsent)
            .where(
                CustomerConsent.customer_id == customer_id,
                CustomerConsent.consent_type == consent_type,
                CustomerConsent.status == ConsentStatus.GRANTED,
                CustomerConsent.revoked_at.is_(None),
            )
            .order_by(desc(CustomerConsent.granted_at))
        )
        candidates = list(self.session.scalars(stmt).all())
        for consent in candidates:
            if consent.expires_at is None:
                return consent
            exp = consent.expires_at
            if exp.tzinfo is None and now.tzinfo is not None:
                exp = exp.replace(tzinfo=timezone.utc)
            elif exp.tzinfo is not None and now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            if exp > now:
                return consent
        return None

    def save(self, consent: CustomerConsent) -> CustomerConsent:
        """Persist or merge consent record within active database session."""
        self.session.add(consent)
        return consent

    def revoke_consent(
        self,
        consent_id: UUID,
        revoked_at: datetime | None = None,
    ) -> CustomerConsent | None:
        """Revoke an existing consent record."""
        record = self.find_by_id(consent_id)
        if record is None:
            return None
        now = revoked_at or datetime.now(timezone.utc)
        record.status = ConsentStatus.REVOKED
        record.revoked_at = now
        return record
