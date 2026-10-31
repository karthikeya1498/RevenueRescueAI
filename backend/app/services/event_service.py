"""Event ingestion application service for RevenueRescueAI.

Author: Karthikeya
Architectural layer: application service.

Coordinates validation, canonical normalization, deduplication, persistence,
and read operations across event ingestion boundaries.
"""

from __future__ import annotations

import logging
from math import ceil
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.errors import EntityNotFoundException
from app.models.domain import ProviderWebhookEvent
from app.repositories.webhook_events import WebhookEventRepository
from app.schemas.events import (
    CanonicalEventDTO,
    EventDetailDTO,
    EventIngestRequestDTO,
    EventIngestResponseDTO,
    EventSummaryDTO,
    PaginatedEventsDTO,
    SimulateFailureRequestDTO,
)
from app.services.event_deduplicator import EventDeduplicator
from app.services.event_normalizer import EventNormalizer
from app.services.event_validator import EventValidator

logger = logging.getLogger("revenuerescue.events")


class EventService:
    """Application service orchestrating revenue-risk event ingestion."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = WebhookEventRepository(session)

    def ingest_canonical_event(
        self,
        request: EventIngestRequestDTO,
        *,
        signature_verified: bool = False,
        correlation_id: str | None = None,
    ) -> EventIngestResponseDTO:
        """Process and persist a canonical event ingestion request."""
        corr_id = correlation_id or f"corr_{uuid4().hex[:12]}"
        
        # 1. Normalization
        canonical = EventNormalizer.normalize_canonical_request(request)

        # 2. Validation
        EventValidator.validate(canonical)

        # 3. Deduplication & Persistence
        status = "ACCEPTED"
        result = EventDeduplicator.evaluate_and_record(
            self.repo,
            canonical,
            signature_verified=signature_verified,
            ingestion_status=status,
        )

        case_id: str | None = None
        case_key: str | None = None

        # 4. Connect to Case Management Engine if event is not a duplicate
        if not result.duplicate:
            from app.services.event_to_case_engine import EventToCaseEngine

            engine = EventToCaseEngine(self.session)
            case_outcome = engine.process_event(
                canonical, raw_event_record=result.event, correlation_id=corr_id
            )
            self.repo.mark_processed(result.event)
            if case_outcome.case_id:
                case_id = str(case_outcome.case_id)
            if case_outcome.case_key:
                case_key = case_outcome.case_key

        self.session.commit()

        final_status = "DUPLICATE" if result.duplicate else "ACCEPTED"
        logger.info(
            "Event ingested: id=%s, ext_id=%s, type=%s, duplicate=%s, case_id=%s, corr=%s",
            result.event.id,
            canonical.external_event_id,
            canonical.event_type,
            result.duplicate,
            case_id,
            corr_id,
        )

        return EventIngestResponseDTO(
            accepted=True,
            duplicate=result.duplicate,
            event_id=str(result.event.id),
            external_event_id=canonical.external_event_id,
            event_type=canonical.event_type,
            status=final_status,
            reason=result.reason,
            correlation_id=corr_id,
            occurred_at=canonical.occurred_at,
            case_id=case_id,
            case_key=case_key,
        )

    def ingest_raw_webhook(
        self,
        raw_payload: dict[str, Any],
        provider: str = "stripe",
        event_id_header: str | None = None,
        *,
        signature_verified: bool = False,
        correlation_id: str | None = None,
    ) -> EventIngestResponseDTO:
        """Process and persist raw gateway webhook payloads."""
        corr_id = correlation_id or f"corr_{uuid4().hex[:12]}"

        # 1. Normalization
        canonical = EventNormalizer.normalize_raw_provider_webhook(
            raw_payload, provider=provider, event_id_header=event_id_header
        )

        # 2. Validation
        EventValidator.validate(canonical)

        # 3. Deduplication & Persistence
        result = EventDeduplicator.evaluate_and_record(
            self.repo,
            canonical,
            signature_verified=signature_verified,
            ingestion_status="ACCEPTED",
        )

        case_id: str | None = None
        case_key: str | None = None

        # 4. Connect to Case Management Engine if event is not a duplicate
        if not result.duplicate:
            from app.services.event_to_case_engine import EventToCaseEngine

            engine = EventToCaseEngine(self.session)
            case_outcome = engine.process_event(
                canonical, raw_event_record=result.event, correlation_id=corr_id
            )
            self.repo.mark_processed(result.event)
            if case_outcome.case_id:
                case_id = str(case_outcome.case_id)
            if case_outcome.case_key:
                case_key = case_outcome.case_key

        self.session.commit()

        final_status = "DUPLICATE" if result.duplicate else "ACCEPTED"
        logger.info(
            "Webhook ingested: id=%s, provider=%s, ext_id=%s, duplicate=%s, case_id=%s, corr=%s",
            result.event.id,
            canonical.provider,
            canonical.external_event_id,
            result.duplicate,
            case_id,
            corr_id,
        )

        return EventIngestResponseDTO(
            accepted=True,
            duplicate=result.duplicate,
            event_id=str(result.event.id),
            external_event_id=canonical.external_event_id,
            event_type=canonical.event_type,
            status=final_status,
            reason=result.reason,
            correlation_id=corr_id,
            occurred_at=canonical.occurred_at,
            case_id=case_id,
            case_key=case_key,
        )

    def simulate_failure_event(
        self,
        sim_request: SimulateFailureRequestDTO,
        correlation_id: str | None = None,
    ) -> EventIngestResponseDTO:
        """Generate and persist a synthetic payment failure event for development/testing."""
        corr_id = correlation_id or f"corr_{uuid4().hex[:12]}"

        # 1. Normalization
        canonical = EventNormalizer.normalize_simulator_request(sim_request)

        # 2. Validation
        EventValidator.validate(canonical)

        # 3. Deduplication & Persistence
        result = EventDeduplicator.evaluate_and_record(
            self.repo,
            canonical,
            signature_verified=True,
            ingestion_status="ACCEPTED",
        )

        case_id: str | None = None
        case_key: str | None = None

        # 4. Connect to Case Management Engine if event is not a duplicate
        if not result.duplicate:
            from app.services.event_to_case_engine import EventToCaseEngine

            engine = EventToCaseEngine(self.session)
            case_outcome = engine.process_event(
                canonical, raw_event_record=result.event, correlation_id=corr_id
            )
            self.repo.mark_processed(result.event)
            if case_outcome.case_id:
                case_id = str(case_outcome.case_id)
            if case_outcome.case_key:
                case_key = case_outcome.case_key

        self.session.commit()

        logger.info(
            "Simulated event created: id=%s, ext_id=%s, customer=%s, amount=%d, case_id=%s",
            result.event.id,
            canonical.external_event_id,
            canonical.customer_reference,
            canonical.amount_minor,
            case_id,
        )

        return EventIngestResponseDTO(
            accepted=True,
            duplicate=result.duplicate,
            event_id=str(result.event.id),
            external_event_id=canonical.external_event_id,
            event_type=canonical.event_type,
            status="ACCEPTED",
            reason=result.reason,
            correlation_id=corr_id,
            occurred_at=canonical.occurred_at,
            case_id=case_id,
            case_key=case_key,
        )

    def list_events(
        self,
        *,
        provider: str | None = None,
        event_type: str | None = None,
        ingestion_status: str | None = None,
        processed: bool | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedEventsDTO:
        """Retrieve paginated list of ingested events with filtering."""
        limit = max(1, min(limit, 100))
        page = max(1, page)
        items, total = self.repo.list_events(
            provider=provider,
            event_type=event_type,
            ingestion_status=ingestion_status,
            processed=processed,
            page=page,
            limit=limit,
        )
        pages = ceil(total / limit) if total > 0 else 1

        summaries = [
            EventSummaryDTO(
                id=item.id,
                provider=item.provider,
                external_event_id=item.external_event_id,
                event_type=item.event_type,
                signature_verified=item.signature_verified,
                processed=item.processed,
                ingestion_status=item.ingestion_status,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ]

        return PaginatedEventsDTO(
            items=summaries,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    def get_event_by_id(self, event_id: str | UUID) -> EventDetailDTO:
        """Retrieve full details of an ingested event by internal UUID or external event ID."""
        event: ProviderWebhookEvent | None = None
        if isinstance(event_id, str):
            try:
                parsed_uuid = UUID(event_id)
                event = self.repo.find_by_id(parsed_uuid)
            except ValueError:
                # Attempt lookup by external ID across providers
                event = self.session.query(ProviderWebhookEvent).filter_by(external_event_id=event_id).first()
        else:
            event = self.repo.find_by_id(event_id)

        if event is None:
            raise EntityNotFoundException("ProviderWebhookEvent", str(event_id))

        return EventDetailDTO(
            id=event.id,
            provider=event.provider,
            external_event_id=event.external_event_id,
            event_type=event.event_type,
            payload_hash=event.payload_hash,
            signature_verified=event.signature_verified,
            processed=event.processed,
            ingestion_status=event.ingestion_status,
            payload_safe=event.payload_safe,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )
