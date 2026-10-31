"""Customer persistence repository.

Author: Karthikeya
Architectural layer: data access / repository.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import CustomerStatus
from app.models.domain import Customer


class CustomerRepository:
    """Encapsulates durable relational queries for the Customer aggregate."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, customer_id: UUID) -> Customer | None:
        """Find a single customer by internal primary key UUID."""
        return self.session.scalar(select(Customer).where(Customer.id == customer_id))

    def find_by_external_id(self, provider: str, external_customer_id: str) -> Customer | None:
        """Find a single customer by provider and external customer ID."""
        return self.session.scalar(
            select(Customer).where(
                Customer.provider == provider,
                Customer.external_customer_id == external_customer_id,
            )
        )

    def save(self, customer: Customer) -> Customer:
        """Persist or merge customer record within active session."""
        self.session.add(customer)
        return customer

    def list_customers(
        self,
        *,
        status: CustomerStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Customer]:
        """Return a paginated list of customers with optional status filter."""
        stmt = select(Customer)
        if status is not None:
            stmt = stmt.where(Customer.status == status)
        stmt = stmt.order_by(Customer.created_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())
