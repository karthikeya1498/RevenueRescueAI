"""Recovery case entity-to-DTO and DTO-to-entity pure mappers.

Author: Karthikeya
Architectural layer: mapper.

Rules:
- Converts state machine entities to API response representations cleanly.
- Does not trigger lazy queries across relationships.
- Guarantees deterministic case key generation when omitted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.enums import RecoveryCaseState
from app.models.domain import RecoveryCase
from app.schemas.recovery_cases import (
    RecoveryCaseCreateDTO,
    RecoveryCaseResponseDTO,
    RecoveryCaseSummaryDTO,
)


class RecoveryCaseMapper:
    """Stateless transformation utility between RecoveryCase entities and DTOs."""

    @staticmethod
    def to_response(entity: RecoveryCase) -> RecoveryCaseResponseDTO:
        """Convert a RecoveryCase persistence entity into a RecoveryCaseResponseDTO."""
        return RecoveryCaseResponseDTO(
            id=entity.id,
            case_key=entity.case_key,
            customer_id=entity.customer_id,
            trigger_transaction_id=entity.trigger_transaction_id,
            state=entity.state,
            priority=entity.priority,
            version=entity.version,
            opened_at=entity.opened_at,
            last_state_changed_at=entity.last_state_changed_at,
            closed_at=entity.closed_at,
            metadata=dict(entity.metadata_json) if entity.metadata_json else {},
        )

    @staticmethod
    def to_summary(entity: RecoveryCase) -> RecoveryCaseSummaryDTO:
        """Convert a RecoveryCase persistence entity into a compact RecoveryCaseSummaryDTO."""
        return RecoveryCaseSummaryDTO(
            id=entity.id,
            case_key=entity.case_key,
            customer_id=entity.customer_id,
            trigger_transaction_id=entity.trigger_transaction_id,
            state=entity.state,
            priority=entity.priority,
            opened_at=entity.opened_at,
            last_state_changed_at=entity.last_state_changed_at,
            closed_at=entity.closed_at,
        )

    @staticmethod
    def to_summary_item(entity: RecoveryCase) -> CaseSummaryItemDTO:
        """Convert a RecoveryCase with relationships into an enriched CaseSummaryItemDTO."""
        from app.schemas.customers import CustomerSummaryDTO
        from app.schemas.recovery_cases import CaseSummaryItemDTO
        from app.schemas.transactions import TransactionSummaryDTO

        customer_dto = None
        if entity.customer:
            customer_dto = CustomerSummaryDTO(
                id=entity.customer.id,
                external_customer_id=entity.customer.external_customer_id,
                display_name=entity.customer.display_name,
                status=entity.customer.status,
            )

        tx_dto = None
        if entity.trigger_transaction:
            tx_dto = TransactionSummaryDTO(
                id=entity.trigger_transaction.id,
                external_transaction_id=entity.trigger_transaction.external_transaction_id,
                amount_minor=entity.trigger_transaction.amount_minor,
                currency=entity.trigger_transaction.currency,
                status=entity.trigger_transaction.status,
                occurred_at=entity.trigger_transaction.occurred_at,
            )

        attempts_count = len(entity.attempts) if entity.attempts else 0
        return CaseSummaryItemDTO(
            id=entity.id,
            case_key=entity.case_key,
            customer=customer_dto,
            trigger_transaction=tx_dto,
            state=entity.state,
            priority=entity.priority,
            attempts_count=attempts_count,
            opened_at=entity.opened_at,
            last_state_changed_at=entity.last_state_changed_at,
        )

    @staticmethod
    def to_detail_response(entity: RecoveryCase) -> CaseDetailResponseDTO:
        """Convert a RecoveryCase with deep relationships into a CaseDetailResponseDTO."""
        from app.schemas.customers import CustomerResponseDTO
        from app.schemas.recovery_cases import CaseDetailResponseDTO
        from app.schemas.transactions import TransactionResponseDTO

        customer_dto = None
        if entity.customer:
            customer_dto = CustomerResponseDTO(
                id=entity.customer.id,
                provider=entity.customer.provider,
                external_customer_id=entity.customer.external_customer_id,
                email=entity.customer.email,
                display_name=entity.customer.display_name,
                status=entity.customer.status,
                metadata=dict(entity.customer.metadata_json) if entity.customer.metadata_json else {},
                created_at=entity.customer.created_at,
                updated_at=entity.customer.updated_at,
            )

        tx_dto = None
        if entity.trigger_transaction:
            tx_dto = TransactionResponseDTO(
                id=entity.trigger_transaction.id,
                customer_id=entity.trigger_transaction.customer_id,
                provider=entity.trigger_transaction.provider,
                external_transaction_id=entity.trigger_transaction.external_transaction_id,
                amount_minor=entity.trigger_transaction.amount_minor,
                currency=entity.trigger_transaction.currency,
                status=entity.trigger_transaction.status,
                failure_code=entity.trigger_transaction.failure_code,
                failure_message_safe=entity.trigger_transaction.failure_message_safe,
                occurred_at=entity.trigger_transaction.occurred_at,
                metadata=dict(entity.trigger_transaction.metadata_json)
                if entity.trigger_transaction.metadata_json
                else {},
                created_at=entity.trigger_transaction.created_at,
                updated_at=entity.trigger_transaction.updated_at,
            )

        attempts_count = len(entity.attempts) if entity.attempts else 0
        return CaseDetailResponseDTO(
            id=entity.id,
            case_key=entity.case_key,
            customer=customer_dto,
            trigger_transaction=tx_dto,
            state=entity.state,
            priority=entity.priority,
            version=entity.version,
            opened_at=entity.opened_at,
            last_state_changed_at=entity.last_state_changed_at,
            closed_at=entity.closed_at,
            metadata=dict(entity.metadata_json) if entity.metadata_json else {},
            attempts_count=attempts_count,
        )

    @staticmethod
    def to_entity(dto: RecoveryCaseCreateDTO) -> RecoveryCase:
        """Instantiate a new detached RecoveryCase entity in DETECTED state."""
        now = datetime.now(timezone.utc)
        case_key = dto.case_key or f"CASE-{uuid4().hex[:12].upper()}"
        return RecoveryCase(
            id=uuid4(),
            customer_id=dto.customer_id,
            trigger_transaction_id=dto.trigger_transaction_id,
            case_key=case_key,
            state=RecoveryCaseState.DETECTED,
            priority=dto.priority,
            opened_at=now,
            last_state_changed_at=now,
            closed_at=None,
            version=1,
            metadata_json=dto.metadata,
        )
