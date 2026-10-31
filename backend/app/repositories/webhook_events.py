"""Durable provider-event idempotency repository.
Author: Karthikeya
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.domain import ProviderWebhookEvent


@dataclass(frozen=True)
class EventRecordResult:
    event: ProviderWebhookEvent
    accepted: bool
    duplicate: bool
    reason: str
    conflict: bool = False


class WebhookEventRepository:
    """Persist provider event receipts under a database uniqueness boundary."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        payload_hash: str,
        signature_verified: bool,
        payload_safe: dict,
        ingestion_status: str = "ACCEPTED",
    ) -> EventRecordResult:
        existing = self.session.scalar(
            select(ProviderWebhookEvent).where(
                ProviderWebhookEvent.provider == provider,
                ProviderWebhookEvent.external_event_id == event_id,
            )
        )
        if existing is not None:
            if existing.payload_hash != payload_hash:
                return EventRecordResult(
                    existing, False, True, "event_id_reused_with_different_payload", conflict=True
                )
            return EventRecordResult(existing, False, True, "duplicate_event_suppressed", conflict=False)
        event = ProviderWebhookEvent(
            provider=provider,
            external_event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            signature_verified=signature_verified,
            processed=False,
            ingestion_status=ingestion_status,
            payload_safe=payload_safe,
        )
        try:
            with self.session.begin_nested():
                self.session.add(event)
                self.session.flush()
        except IntegrityError:
            existing = self.session.scalar(
                select(ProviderWebhookEvent).where(
                    ProviderWebhookEvent.provider == provider,
                    ProviderWebhookEvent.external_event_id == event_id,
                )
            )
            if existing is None:
                raise
            conflict = existing.payload_hash != payload_hash
            reason = (
                "event_id_reused_with_different_payload"
                if conflict
                else "duplicate_event_suppressed"
            )
            return EventRecordResult(existing, False, True, reason, conflict=conflict)
        self.session.flush()
        return EventRecordResult(event, True, False, "accepted", conflict=False)

    def mark_processed(self, event: ProviderWebhookEvent) -> ProviderWebhookEvent:
        """Mark processing complete only after downstream work commits successfully."""
        event.processed = True
        self.session.flush()
        return event

    def find_by_id(self, event_id: UUID) -> ProviderWebhookEvent | None:
        """Retrieve single webhook event by primary key UUID."""
        return self.session.get(ProviderWebhookEvent, event_id)

    def find_by_external_id(self, provider: str, external_event_id: str) -> ProviderWebhookEvent | None:
        """Retrieve single webhook event by provider and external event ID."""
        return self.session.scalar(
            select(ProviderWebhookEvent).where(
                ProviderWebhookEvent.provider == provider,
                ProviderWebhookEvent.external_event_id == external_event_id,
            )
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
    ) -> tuple[list[ProviderWebhookEvent], int]:
        """Query paginated events with optional filtering."""
        filters = []
        if provider:
            filters.append(ProviderWebhookEvent.provider == provider)
        if event_type:
            filters.append(ProviderWebhookEvent.event_type == event_type)
        if ingestion_status:
            filters.append(ProviderWebhookEvent.ingestion_status == ingestion_status)
        if processed is not None:
            filters.append(ProviderWebhookEvent.processed == processed)

        count_query = select(func.count(ProviderWebhookEvent.id))
        if filters:
            count_query = count_query.where(and_(*filters))
        total = self.session.scalar(count_query) or 0

        query = select(ProviderWebhookEvent)
        if filters:
            query = query.where(and_(*filters))
        query = query.order_by(ProviderWebhookEvent.created_at.desc())
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        items = list(self.session.scalars(query).all())
        return items, total
