"""Provider event verification and recovery attribution primitives.

Author: Karthikeya
No event is considered recovered merely because an intent or payment link exists.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class WebhookReceipt:
    event_id: str
    event_type: str
    payload_hash: str
    accepted: bool
    duplicate: bool
    reason: str


@dataclass(frozen=True)
class RecoveryEvidence:
    intervention_id: str
    provider_event_id: str
    failed_transaction_id: str
    successful_transaction_id: str
    amount_minor: int
    currency: str
    verified_at: datetime
    attribution_window_hours: int
    attributable: bool
    reason: str


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Verify Razorpay-compatible HMAC SHA-256 signatures without logging secrets."""
    if not raw_body or not signature or not secret:
        return False
    supplied = signature.removeprefix("v1=").strip()
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


class WebhookEventLedger:
    """Thread-safe in-process idempotency ledger for adapters and tests.

    Production persistence should use a unique provider/event-id constraint; this
    interface makes that requirement explicit while remaining dependency-free.
    """

    def __init__(self) -> None:
        self._seen: dict[str, str] = {}
        self._lock = Lock()

    def accept(self, *, event_id: str, payload: bytes) -> WebhookReceipt:
        payload_hash = hashlib.sha256(payload).hexdigest()
        with self._lock:
            previous = self._seen.get(event_id)
            if previous is not None:
                if previous != payload_hash:
                    return WebhookReceipt(
                        event_id,
                        "unknown",
                        payload_hash,
                        False,
                        True,
                        "event_id_reused_with_different_payload",
                    )
                return WebhookReceipt(
                    event_id, "unknown", payload_hash, False, True, "duplicate_event_suppressed"
                )
            self._seen[event_id] = payload_hash
        try:
            event_type = str(json.loads(payload).get("event", "unknown"))
        except (ValueError, TypeError):
            event_type = "unknown"
        return WebhookReceipt(event_id, event_type, payload_hash, True, False, "accepted")


class RecoveryAttributor:
    """Counts recovery only with verified, linked, amount-matched provider evidence."""

    def attribute(
        self,
        *,
        intervention_id: str,
        failed_transaction_id: str,
        successful_transaction_id: str,
        provider_event_id: str,
        amount_minor: int,
        successful_amount_minor: int,
        currency: str,
        successful_currency: str,
        failed_at: datetime,
        verified_at: datetime,
        provider_signature_valid: bool,
        intervention_created_at: datetime | None = None,
        window_hours: int = 72,
    ) -> RecoveryEvidence:
        start = intervention_created_at or failed_at
        within_window = start <= verified_at <= start + timedelta(hours=window_hours)
        checks = [
            (provider_signature_valid, "provider_signature_invalid"),
            (amount_minor == successful_amount_minor, "amount_mismatch"),
            (currency == successful_currency, "currency_mismatch"),
            (within_window, "outside_attribution_window"),
            (failed_transaction_id != successful_transaction_id, "same_transaction_not_recovery"),
        ]
        failed_check = next((reason for passed, reason in checks if not passed), None)
        return RecoveryEvidence(
            intervention_id,
            provider_event_id,
            failed_transaction_id,
            successful_transaction_id,
            successful_amount_minor,
            successful_currency,
            verified_at,
            window_hours,
            failed_check is None,
            "verified_intervention_link" if failed_check is None else failed_check,
        )


def canonical_payload(payload: dict[str, Any]) -> bytes:
    """Canonicalize payload for signature tests and deterministic audit hashing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
