"""Recovery case application service.

Author: Karthikeya
Architectural layer: application service.

Responsibilities:
- Manages recovery case lifecycles and finite state machine transitions.
- Records atomic state transitions and compliance audit trail events.
- Enforces state machine invariants (terminal states, referential checks).
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import ActorType, RecoveryCaseState
from app.core.errors import (
    DuplicateEntityException,
    EntityNotFoundException,
    InvalidStateTransitionException,
)
from app.mappers.recovery_cases import RecoveryCaseMapper
from app.models.domain import CaseStateTransition, RecoveryCase
from app.repositories.audit_events import AuditEventRepository
from app.repositories.customers import CustomerRepository
from app.repositories.recovery_cases import RecoveryCaseRepository
from app.repositories.transactions import TransactionRepository
from app.schemas.common import PaginatedResponse, PaginationMetadata
from app.schemas.recovery_cases import (
    CaseStateTransitionDTO,
    RecoveryCaseCreateDTO,
    RecoveryCaseResponseDTO,
    RecoveryCaseSummaryDTO,
)

TERMINAL_STATES = {
    RecoveryCaseState.RECOVERED,
    RecoveryCaseState.STOPPED,
    RecoveryCaseState.CLOSED,
}


class RecoveryCaseService:
    """Application service for recovery cases and state machine coordination."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.case_repo = RecoveryCaseRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.transaction_repo = TransactionRepository(session)
        self.audit_repo = AuditEventRepository(session)

    def create_case(self, dto: RecoveryCaseCreateDTO) -> RecoveryCaseResponseDTO:
        """Create a new recovery case in DETECTED state with opening audit event."""
        # 1. Validate customer existence
        customer = self.customer_repo.find_by_id(dto.customer_id)
        if customer is None:
            raise EntityNotFoundException("Customer", str(dto.customer_id))

        # 2. Validate trigger transaction existence
        tx = self.transaction_repo.find_by_id(dto.trigger_transaction_id)
        if tx is None:
            raise EntityNotFoundException("Transaction", str(dto.trigger_transaction_id))

        # 3. Enforce 1-to-1 trigger transaction to case invariant
        existing_case = self.case_repo.find_by_trigger_transaction_id(dto.trigger_transaction_id)
        if existing_case is not None:
            raise DuplicateEntityException(
                "RecoveryCase", f"trigger_tx:{dto.trigger_transaction_id}"
            )

        # 4. Check case_key uniqueness if provided
        if dto.case_key is not None:
            key_case = self.case_repo.find_by_case_key(dto.case_key)
            if key_case is not None:
                raise DuplicateEntityException("RecoveryCase", dto.case_key)

        # 5. Persist case
        case = RecoveryCaseMapper.to_entity(dto)
        self.case_repo.save(case)

        # 6. Record initial audit event
        correlation_id = str(uuid4())
        self.audit_repo.record(
            case_id=case.id,
            event_type="CASE_OPENED",
            actor_type=ActorType.SYSTEM,
            correlation_id=correlation_id,
            payload_safe={
                "trigger_transaction_id": str(dto.trigger_transaction_id),
                "customer_id": str(dto.customer_id),
                "case_key": case.case_key,
                "initial_priority": case.priority,
            },
            from_state=None,
            to_state=RecoveryCaseState.DETECTED,
            actor_id="system.risk_detector",
        )

        self.session.commit()
        return RecoveryCaseMapper.to_response(case)

    def get_case(self, case_id: UUID) -> RecoveryCaseResponseDTO:
        """Retrieve a recovery case by internal UUID or raise EntityNotFoundException."""
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))
        return RecoveryCaseMapper.to_response(case)

    def get_by_case_key(self, case_key: str) -> RecoveryCaseResponseDTO:
        """Retrieve a recovery case by canonical case key or raise EntityNotFoundException."""
        case = self.case_repo.find_by_case_key(case_key)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", case_key)
        return RecoveryCaseMapper.to_response(case)

    def list_cases(
        self,
        *,
        state: RecoveryCaseState | None = None,
        customer_id: UUID | None = None,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[RecoveryCaseSummaryDTO]:
        """Return a paginated list of recovery cases."""
        offset = (page - 1) * size

        # Count total
        count_stmt = select(func.count(RecoveryCase.id))
        if state is not None:
            count_stmt = count_stmt.where(RecoveryCase.state == state)
        if customer_id is not None:
            count_stmt = count_stmt.where(RecoveryCase.customer_id == customer_id)
        total = self.session.scalar(count_stmt) or 0

        # Query items
        entities = self.case_repo.list_cases(
            state=state, customer_id=customer_id, limit=size, offset=offset
        )
        items = [RecoveryCaseMapper.to_summary(c) for c in entities]

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

    def transition_state(
        self, case_id: UUID, transition: CaseStateTransitionDTO
    ) -> RecoveryCaseResponseDTO:
        """Execute and record an explicit state transition in the recovery FSM."""
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))

        # Enforce terminal state immutability
        if case.state in TERMINAL_STATES:
            raise InvalidStateTransitionException(case.state.value, transition.to_state.value)

        # Enforce non-identity transitions
        if case.state == transition.to_state:
            raise InvalidStateTransitionException(case.state.value, transition.to_state.value)

        from_state = case.state
        now = datetime.now(timezone.utc)

        # Update case entity
        case.state = transition.to_state
        case.last_state_changed_at = now
        case.version += 1
        if transition.to_state in TERMINAL_STATES:
            case.closed_at = now

        # Record state transition history
        current_trans_max = self.session.scalar(
            select(func.max(CaseStateTransition.sequence_number)).where(
                CaseStateTransition.case_id == case_id
            )
        )
        next_trans_seq = (current_trans_max or 0) + 1

        state_trans_record = CaseStateTransition(
            id=uuid4(),
            case_id=case.id,
            from_state=from_state,
            to_state=transition.to_state,
            reason_code=transition.reason_code,
            actor_type=transition.actor_type,
            correlation_id=transition.correlation_id,
            occurred_at=now,
            sequence_number=next_trans_seq,
            metadata_json=transition.metadata,
        )
        self.session.add(state_trans_record)

        # Record audit event
        self.audit_repo.record(
            case_id=case.id,
            event_type="STATE_TRANSITION",
            actor_type=transition.actor_type,
            correlation_id=transition.correlation_id,
            payload_safe={
                "reason_code": transition.reason_code,
                "metadata": transition.metadata,
                "sequence_number": next_trans_seq,
            },
            from_state=from_state,
            to_state=transition.to_state,
            actor_id=None,
        )

        self.session.commit()
        return RecoveryCaseMapper.to_response(case)

    def update_case(
        self,
        case_id: UUID,
        update_dto: RecoveryCaseUpdateDTO,
        actor_id: str | None = None,
    ) -> RecoveryCaseResponseDTO:
        """Update case operational attributes while preserving financial integrity."""
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))

        if case.state in TERMINAL_STATES:
            raise InvalidStateTransitionException(
                case.state.value,
                "UPDATE_REJECTED",
            )

        now = datetime.now(timezone.utc)
        meta = dict(case.metadata_json) if case.metadata_json else {}
        changes: dict[str, Any] = {}

        # 1. Operational Priority Update
        if update_dto.priority is not None and update_dto.priority != case.priority:
            changes["previous_priority"] = case.priority
            changes["new_priority"] = update_dto.priority
            case.priority = update_dto.priority

        # 2. Metadata Updates with Field Protection
        if update_dto.metadata is not None:
            # Protect authoritative financial and identity fields
            restricted_keys = {
                "id",
                "customer_id",
                "trigger_transaction_id",
                "case_key",
                "amount_minor",
                "currency",
                "recovered_amount_minor",
                "version",
            }
            clean_updates = {
                k: v for k, v in update_dto.metadata.items() if k not in restricted_keys
            }
            meta.update(clean_updates)
            case.metadata_json = meta
            changes["metadata_updated"] = list(clean_updates.keys())

        if not changes:
            return RecoveryCaseMapper.to_response(case)

        case.last_state_changed_at = now
        case.version += 1

        # 3. Record Audit Event
        correlation_id = str(uuid4())
        self.audit_repo.record(
            case_id=case.id,
            event_type="CASE_UPDATED",
            actor_type=ActorType.OPERATOR if actor_id else ActorType.SYSTEM,
            correlation_id=correlation_id,
            payload_safe=changes,
            from_state=case.state,
            to_state=case.state,
            actor_id=actor_id or "system.case_service",
        )

        self.session.commit()
        return RecoveryCaseMapper.to_response(case)

    def get_case_timeline(self, case_id: UUID) -> list[AuditEventResponseDTO]:
        """Retrieve chronological, monotonic audit event timeline for a recovery case."""
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))

        from app.schemas.audit_events import AuditEventResponseDTO

        audit_entities = self.audit_repo.find_by_case(case_id)
        return [
            AuditEventResponseDTO(
                id=a.id,
                case_id=a.case_id,
                sequence_number=a.sequence_number,
                event_type=a.event_type,
                from_state=a.from_state,
                to_state=a.to_state,
                actor_type=a.actor_type,
                actor_id=a.actor_id,
                correlation_id=a.correlation_id,
                event_time=a.event_time,
                payload_safe=a.payload_safe,
            )
            for a in audit_entities
        ]

    def get_case_events(self, case_id: UUID) -> list[EventSummaryDTO]:
        """Retrieve all ingested gateway and webhook events associated with this case."""
        case = self.case_repo.find_by_id(case_id)
        if case is None:
            raise EntityNotFoundException("RecoveryCase", str(case_id))

        from app.models.domain import ProviderWebhookEvent
        from app.schemas.events import EventSummaryDTO

        meta = case.metadata_json or {}
        event_ids_to_find = set()
        if "source_event_id" in meta:
            event_ids_to_find.add(meta["source_event_id"])
        if "latest_failure_event_id" in meta:
            event_ids_to_find.add(meta["latest_failure_event_id"])

        events: list[ProviderWebhookEvent] = []
        if event_ids_to_find:
            events = list(
                self.session.scalars(
                    select(ProviderWebhookEvent).where(
                        ProviderWebhookEvent.external_event_id.in_(list(event_ids_to_find))
                    )
                ).all()
            )

        # Fallback: if empty, query by trigger transaction reference or customer
        if not events and case.trigger_transaction:
            ext_tx = case.trigger_transaction.external_transaction_id
            events = list(
                self.session.scalars(
                    select(ProviderWebhookEvent)
                    .where(ProviderWebhookEvent.external_event_id.like(f"%{ext_tx}%"))
                    .limit(20)
                ).all()
            )

        return [
            EventSummaryDTO(
                id=e.id,
                provider=e.provider,
                external_event_id=e.external_event_id,
                event_type=e.event_type,
                signature_verified=e.signature_verified,
                processed=e.processed,
                ingestion_status=e.ingestion_status,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in events
        ]

