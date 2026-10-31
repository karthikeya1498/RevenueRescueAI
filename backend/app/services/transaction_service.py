"""Transaction management application service.

Author: Karthikeya
Architectural layer: application service.

Responsibilities:
- Ingestion and querying of payment transactions.
- Customer referential integrity validation prior to transaction persistence.
- Lossless monetary amount management in exact minor units.
"""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import TransactionStatus
from app.core.errors import DuplicateEntityException, EntityNotFoundException
from app.mappers.transactions import TransactionMapper
from app.models.domain import Transaction
from app.repositories.customers import CustomerRepository
from app.repositories.transactions import TransactionRepository
from app.schemas.common import PaginatedResponse, PaginationMetadata
from app.schemas.transactions import (
    TransactionCreateDTO,
    TransactionResponseDTO,
)


class TransactionService:
    """Application service for recording, querying, and auditing payment transactions."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.transaction_repo = TransactionRepository(session)
        self.customer_repo = CustomerRepository(session)

    def record_transaction(self, dto: TransactionCreateDTO) -> TransactionResponseDTO:
        """Record an ingested or simulated payment transaction after validating customer existence."""
        customer = self.customer_repo.find_by_id(dto.customer_id)
        if customer is None:
            raise EntityNotFoundException("Customer", str(dto.customer_id))

        existing = self.transaction_repo.find_by_external_id(
            dto.provider, dto.external_transaction_id
        )
        if existing is not None:
            raise DuplicateEntityException(
                "Transaction", f"{dto.provider}:{dto.external_transaction_id}"
            )

        transaction = TransactionMapper.to_entity(dto)
        self.transaction_repo.save(transaction)
        self.session.commit()
        return TransactionMapper.to_response(transaction)

    def get_transaction(self, transaction_id: UUID) -> TransactionResponseDTO:
        """Retrieve a transaction by primary key UUID or raise EntityNotFoundException."""
        tx = self.transaction_repo.find_by_id(transaction_id)
        if tx is None:
            raise EntityNotFoundException("Transaction", str(transaction_id))
        return TransactionMapper.to_response(tx)

    def get_by_external_id(
        self, provider: str, external_transaction_id: str
    ) -> TransactionResponseDTO:
        """Retrieve a transaction by provider external reference or raise EntityNotFoundException."""
        tx = self.transaction_repo.find_by_external_id(provider, external_transaction_id)
        if tx is None:
            raise EntityNotFoundException("Transaction", f"{provider}:{external_transaction_id}")
        return TransactionMapper.to_response(tx)

    def list_transactions_for_customer(
        self,
        customer_id: UUID,
        *,
        status: TransactionStatus | None = None,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[TransactionResponseDTO]:
        """Return a paginated list of transactions for a specific customer."""
        customer = self.customer_repo.find_by_id(customer_id)
        if customer is None:
            raise EntityNotFoundException("Customer", str(customer_id))

        offset = (page - 1) * size

        # Count total
        count_stmt = select(func.count(Transaction.id)).where(
            Transaction.customer_id == customer_id
        )
        if status is not None:
            count_stmt = count_stmt.where(Transaction.status == status)
        total = self.session.scalar(count_stmt) or 0

        # Query items
        entities = self.transaction_repo.find_by_customer(
            customer_id, status=status, limit=size, offset=offset
        )
        items = [TransactionMapper.to_response(t) for t in entities]

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
