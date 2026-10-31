"""Customer management application service.

Author: Karthikeya
Architectural layer: application service.

Responsibilities:
- Coordinates customer persistence and business validation.
- Explicit transaction boundary management.
- Pure DTO boundaries (never receives or returns HTTP or raw ORM objects).
"""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import CustomerStatus
from app.core.errors import DuplicateEntityException, EntityNotFoundException
from app.mappers.customers import CustomerMapper
from app.models.domain import Customer
from app.repositories.customers import CustomerRepository
from app.schemas.common import PaginatedResponse, PaginationMetadata
from app.schemas.customers import (
    CustomerCreateDTO,
    CustomerResponseDTO,
    CustomerUpdateDTO,
)


class CustomerService:
    """Application service managing customer registration, retrieval, and status updates."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.customer_repo = CustomerRepository(session)

    def create_customer(self, dto: CustomerCreateDTO) -> CustomerResponseDTO:
        """Register a new customer with uniqueness checks and explicit transaction commit."""
        existing = self.customer_repo.find_by_external_id(dto.provider, dto.external_customer_id)
        if existing is not None:
            raise DuplicateEntityException(
                "Customer", f"{dto.provider}:{dto.external_customer_id}"
            )

        customer = CustomerMapper.to_entity(dto)
        self.customer_repo.save(customer)
        self.session.commit()
        return CustomerMapper.to_response(customer)

    def get_customer(self, customer_id: UUID) -> CustomerResponseDTO:
        """Retrieve a customer by internal UUID or raise EntityNotFoundException."""
        customer = self.customer_repo.find_by_id(customer_id)
        if customer is None:
            raise EntityNotFoundException("Customer", str(customer_id))
        return CustomerMapper.to_response(customer)

    def get_by_external_id(self, provider: str, external_customer_id: str) -> CustomerResponseDTO:
        """Retrieve a customer by provider and external ID or raise EntityNotFoundException."""
        customer = self.customer_repo.find_by_external_id(provider, external_customer_id)
        if customer is None:
            raise EntityNotFoundException("Customer", f"{provider}:{external_customer_id}")
        return CustomerMapper.to_response(customer)

    def list_customers(
        self,
        *,
        status: CustomerStatus | None = None,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[CustomerResponseDTO]:
        """Return a paginated collection of customers with optional status filter."""
        offset = (page - 1) * size

        # Query total count
        count_stmt = select(func.count(Customer.id))
        if status is not None:
            count_stmt = count_stmt.where(Customer.status == status)
        total = self.session.scalar(count_stmt) or 0

        # Query paginated entities
        entities = self.customer_repo.list_customers(status=status, limit=size, offset=offset)
        items = [CustomerMapper.to_response(c) for c in entities]

        total_pages = math.ceil(total / size) if total > 0 else 0
        has_more = page < total_pages

        return PaginatedResponse(
            items=items,
            pagination=PaginationMetadata(
                total=total,
                page=page,
                size=size,
                pages=total_pages,
                has_more=has_more,
            ),
        )

    def update_customer(self, customer_id: UUID, dto: CustomerUpdateDTO) -> CustomerResponseDTO:
        """Update customer attributes and commit the change."""
        customer = self.customer_repo.find_by_id(customer_id)
        if customer is None:
            raise EntityNotFoundException("Customer", str(customer_id))

        if dto.display_name is not None:
            customer.display_name = dto.display_name
        if dto.email is not None:
            customer.email = dto.email
        if dto.status is not None:
            customer.status = dto.status
        if dto.metadata is not None:
            merged_metadata = dict(customer.metadata_json) if customer.metadata_json else {}
            merged_metadata.update(dto.metadata)
            customer.metadata_json = merged_metadata

        self.session.commit()
        return CustomerMapper.to_response(customer)
