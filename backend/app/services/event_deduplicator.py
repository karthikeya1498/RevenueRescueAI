"""Event deduplication and payload fingerprinting engine for RevenueRescueAI.

Author: Karthikeya
Architectural layer: domain service / deduplication.

Enforces idempotency using SHA-256 payload fingerprints and database unique constraints.
Distinguishes exact duplicate retries from conflicting payload re-use.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.core.errors import ConflictingDuplicateEventException
from app.models.domain import ProviderWebhookEvent
from app.repositories.webhook_events import WebhookEventRepository
from app.schemas.events import CanonicalEventDTO


@dataclass(frozen=True)
class DeduplicationResult:
    """Outcome of deduplication evaluation."""

    event: ProviderWebhookEvent
    accepted: bool
    duplicate: bool
    reason: str
    payload_hash: str


class EventDeduplicator:
    """Manages event fingerprinting and idempotency boundaries."""

    @classmethod
    def compute_fingerprint(cls, event: CanonicalEventDTO) -> str:
        """Generate deterministic SHA-256 hash of the normalized canonical payload."""
        fingerprint_data: dict[str, Any] = {
            "event_type": event.event_type,
            "provider": event.provider.lower(),
            "customer_reference": event.customer_reference,
            "payment_reference": event.payment_reference,
            "subscription_reference": event.subscription_reference,
            "invoice_reference": event.invoice_reference,
            "checkout_session_id": event.checkout_session_id,
            "amount_minor": event.amount_minor,
            "currency": event.currency.upper(),
            "failure_code": event.failure_code,
            "failure_message": event.failure_message,
            "metadata": event.metadata,
        }
        serialized = json.dumps(fingerprint_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def evaluate_and_record(
        cls,
        repo: WebhookEventRepository,
        event: CanonicalEventDTO,
        *,
        signature_verified: bool = False,
        ingestion_status: str = "ACCEPTED",
    ) -> DeduplicationResult:
        """Deduplicate against database and record under atomic transaction boundary."""
        payload_hash = cls.compute_fingerprint(event)
        safe_payload = event.model_dump(mode="json")

        record_result = repo.record(
            provider=event.provider.lower(),
            event_id=event.external_event_id,
            event_type=event.event_type,
            payload_hash=payload_hash,
            signature_verified=signature_verified,
            payload_safe=safe_payload,
            ingestion_status=ingestion_status,
        )

        if record_result.conflict:
            raise ConflictingDuplicateEventException(
                event_id=event.external_event_id,
                provider=event.provider,
            )

        return DeduplicationResult(
            event=record_result.event,
            accepted=record_result.accepted,
            duplicate=record_result.duplicate,
            reason=record_result.reason,
            payload_hash=payload_hash,
        )
