"""Durable provider-event idempotency repository.
Author: Karthikeya
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.domain import ProviderWebhookEvent


@dataclass(frozen=True)
class EventRecordResult:
    event: ProviderWebhookEvent
    accepted: bool
    duplicate: bool
    reason: str


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
                    existing, False, True, "event_id_reused_with_different_payload"
                )
            return EventRecordResult(existing, False, True, "duplicate_event_suppressed")
        event = ProviderWebhookEvent(
            provider=provider,
            external_event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            signature_verified=signature_verified,
            processed=False,
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
            reason = (
                "duplicate_event_suppressed"
                if existing.payload_hash == payload_hash
                else "event_id_reused_with_different_payload"
            )
            return EventRecordResult(existing, False, True, reason)
        self.session.flush()
        return EventRecordResult(event, True, False, "accepted")

    def mark_processed(self, event: ProviderWebhookEvent) -> ProviderWebhookEvent:
        """Mark processing complete only after downstream work commits successfully."""
        event.processed = True
        self.session.flush()
        return event
