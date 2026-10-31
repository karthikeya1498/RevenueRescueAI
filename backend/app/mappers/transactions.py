"""Transaction entity-to-DTO and DTO-to-entity pure mappers.

Author: Karthikeya
Architectural layer: mapper.

Rules:
- Exact monetary preservation: integer minor units mapped 1:1 without floating-point conversion.
- Pure functions without database lookups.
- Safe handling of optional failure codes and metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.domain import Transaction
from app.schemas.transactions import (
    TransactionCreateDTO,
    TransactionResponseDTO,
    TransactionSummaryDTO,
)


class TransactionMapper:
    """Stateless transformation utility between Transaction entities and DTOs."""

    @staticmethod
    def to_response(entity: Transaction) -> TransactionResponseDTO:
        """Convert a Transaction persistence entity into a TransactionResponseDTO."""
        return TransactionResponseDTO(
            id=entity.id,
            customer_id=entity.customer_id,
            provider=entity.provider,
            external_transaction_id=entity.external_transaction_id,
            amount_minor=entity.amount_minor,
            currency=entity.currency,
            status=entity.status,
            failure_code=entity.failure_code,
            failure_message_safe=entity.failure_message_safe,
            occurred_at=entity.occurred_at,
            metadata=dict(entity.metadata_json) if entity.metadata_json else {},
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_summary(entity: Transaction) -> TransactionSummaryDTO:
        """Convert a Transaction persistence entity into a compact TransactionSummaryDTO."""
        return TransactionSummaryDTO(
            id=entity.id,
            external_transaction_id=entity.external_transaction_id,
            amount_minor=entity.amount_minor,
            currency=entity.currency,
            status=entity.status,
            failure_code=entity.failure_code,
            occurred_at=entity.occurred_at,
        )

    @staticmethod
    def to_entity(dto: TransactionCreateDTO) -> Transaction:
        """Instantiate a new detached Transaction entity from TransactionCreateDTO."""
        occurred_time = dto.occurred_at or datetime.now(timezone.utc)
        return Transaction(
            id=uuid4(),
            customer_id=dto.customer_id,
            provider=dto.provider,
            external_transaction_id=dto.external_transaction_id,
            amount_minor=dto.amount_minor,
            currency=dto.currency,
            status=dto.status,
            failure_code=dto.failure_code,
            failure_message_safe=dto.failure_message_safe,
            occurred_at=occurred_time,
            metadata_json=dto.metadata,
        )
