"""Customer entity-to-DTO and DTO-to-entity pure mappers.

Author: Karthikeya
Architectural layer: mapper.

Rules:
- Pure transformation functions only; zero database queries.
- Explicit null handling and type safety.
- Complete decoupling of persistence models from external API contracts.
"""

from __future__ import annotations

from uuid import uuid4

from app.models.domain import Customer
from app.schemas.customers import (
    CustomerCreateDTO,
    CustomerResponseDTO,
    CustomerSummaryDTO,
)


class CustomerMapper:
    """Stateless transformation utility between Customer entities and DTOs."""

    @staticmethod
    def to_response(entity: Customer) -> CustomerResponseDTO:
        """Convert a Customer persistence entity into a CustomerResponseDTO."""
        return CustomerResponseDTO(
            id=entity.id,
            provider=entity.provider,
            external_customer_id=entity.external_customer_id,
            email=entity.email,
            display_name=entity.display_name,
            status=entity.status,
            metadata=dict(entity.metadata_json) if entity.metadata_json else {},
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_summary(entity: Customer) -> CustomerSummaryDTO:
        """Convert a Customer persistence entity into a compact CustomerSummaryDTO."""
        return CustomerSummaryDTO(
            id=entity.id,
            external_customer_id=entity.external_customer_id,
            display_name=entity.display_name,
            status=entity.status,
        )

    @staticmethod
    def to_entity(dto: CustomerCreateDTO) -> Customer:
        """Instantiate a new detached Customer persistence entity from CustomerCreateDTO."""
        return Customer(
            id=uuid4(),
            provider=dto.provider,
            external_customer_id=dto.external_customer_id,
            email=dto.email,
            display_name=dto.display_name,
            status=dto.status,
            metadata_json=dto.metadata,
        )
