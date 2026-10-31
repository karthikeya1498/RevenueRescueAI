"""Transaction persistence repository.

Author: Karthikeya
Architectural layer: data access / repository.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import TransactionStatus
from app.models.domain import Transaction


class TransactionRepository:
    """Encapsulates durable relational queries for payment transactions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, transaction_id: UUID) -> Transaction | None:
        """Find a transaction by primary key UUID."""
        return self.session.scalar(select(Transaction).where(Transaction.id == transaction_id))

    def find_by_external_id(
        self, provider: str, external_transaction_id: str
    ) -> Transaction | None:
        """Find a transaction by provider and external transaction reference."""
        return self.session.scalar(
            select(Transaction).where(
                Transaction.provider == provider,
                Transaction.external_transaction_id == external_transaction_id,
            )
        )

    def find_by_customer(
        self,
        customer_id: UUID,
        *,
        status: TransactionStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """Find all transactions for a specific customer with optional status filter."""
        stmt = select(Transaction).where(Transaction.customer_id == customer_id)
        if status is not None:
            stmt = stmt.where(Transaction.status == status)
        stmt = stmt.order_by(Transaction.occurred_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def save(self, transaction: Transaction) -> Transaction:
        """Persist or merge transaction record within active session."""
        self.session.add(transaction)
        return transaction
