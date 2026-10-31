"""Canonical event normalization engine for RevenueRescueAI.

Author: Karthikeya
Architectural layer: domain service / normalizer.

Normalizes diverse source-specific payloads (Stripe, Razorpay, synthetic, canonical)
into a uniform CanonicalEventDTO without floating-point conversion or PII leakage.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.database import utc_now
from app.core.enums import CanonicalEventType, FailureCategory
from app.schemas.events import CanonicalEventDTO, EventIngestRequestDTO, SimulateFailureRequestDTO


class EventNormalizer:
    """Transforms raw vendor-specific and synthetic payloads into canonical event models."""

    # Sensitive keys that must never be stored in safe payloads
    SENSITIVE_KEYS = {
        "card_number",
        "number",
        "cvv",
        "cvc",
        "security_code",
        "pin",
        "password",
        "secret",
        "api_key",
        "token",
        "authorization",
        "cookie",
    }

    # Map raw gateway event types to CanonicalEventType
    EVENT_TYPE_MAPPING = {
        # Payment Failures
        "payment_intent.payment_failed": CanonicalEventType.PAYMENT_FAILED.value,
        "payment.failed": CanonicalEventType.PAYMENT_FAILED.value,
        "charge.failed": CanonicalEventType.PAYMENT_FAILED.value,
        "payment_failed": CanonicalEventType.PAYMENT_FAILED.value,
        "PAYMENT_FAILED": CanonicalEventType.PAYMENT_FAILED.value,
        # Payment Successes
        "payment_intent.succeeded": CanonicalEventType.PAYMENT_SUCCEEDED.value,
        "payment.captured": CanonicalEventType.PAYMENT_SUCCEEDED.value,
        "charge.succeeded": CanonicalEventType.PAYMENT_SUCCEEDED.value,
        "payment_succeeded": CanonicalEventType.PAYMENT_SUCCEEDED.value,
        "PAYMENT_SUCCEEDED": CanonicalEventType.PAYMENT_SUCCEEDED.value,
        # Subscription Failures
        "invoice.payment_failed": CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value,
        "subscription.payment_failed": CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value,
        "subscription_payment_failed": CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value,
        "SUBSCRIPTION_PAYMENT_FAILED": CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value,
        # Checkout Abandonment
        "checkout.session.expired": CanonicalEventType.CHECKOUT_ABANDONED.value,
        "checkout_abandoned": CanonicalEventType.CHECKOUT_ABANDONED.value,
        "CHECKOUT_ABANDONED": CanonicalEventType.CHECKOUT_ABANDONED.value,
        # Invoice Overdue
        "invoice.marked_uncollectible": CanonicalEventType.INVOICE_OVERDUE.value,
        "invoice.overdue": CanonicalEventType.INVOICE_OVERDUE.value,
        "invoice_overdue": CanonicalEventType.INVOICE_OVERDUE.value,
        "INVOICE_OVERDUE": CanonicalEventType.INVOICE_OVERDUE.value,
    }

    # Map raw provider failure codes to FailureCategory
    FAILURE_CODE_MAPPING = {
        "insufficient_funds": FailureCategory.INSUFFICIENT_FUNDS.value,
        "card_declined": FailureCategory.GENERIC_DECLINE.value,
        "expired_card": FailureCategory.CARD_EXPIRED.value,
        "card_expired": FailureCategory.CARD_EXPIRED.value,
        "authentication_required": FailureCategory.AUTHENTICATION_REQUIRED.value,
        "do_not_honor": FailureCategory.DO_NOT_HONOR.value,
        "fraudulent": FailureCategory.FRAUD_SUSPECTED.value,
        "fraud_suspected": FailureCategory.FRAUD_SUSPECTED.value,
        "processing_error": FailureCategory.PROCESSING_ERROR.value,
        "abandoned": FailureCategory.ABANDONED.value,
        "overdue": FailureCategory.OVERDUE.value,
    }

    @classmethod
    def sanitize_metadata(cls, data: Any) -> Any:
        """Recursively redact sensitive card details, credentials, and secrets."""
        if isinstance(data, dict):
            cleaned: dict[str, Any] = {}
            for key, val in data.items():
                lower_key = str(key).lower()
                if any(sens in lower_key for sens in cls.SENSITIVE_KEYS):
                    cleaned[key] = "[REDACTED]"
                else:
                    cleaned[key] = cls.sanitize_metadata(val)
            return cleaned
        if isinstance(data, list):
            return [cls.sanitize_metadata(item) for item in data]
        if isinstance(data, str):
            # Check for potential 13-19 digit credit card numbers
            if re.search(r"\b(?:\d[ -]*?){13,19}\b", data):
                return "[REDACTED_PAN]"
        return data

    @classmethod
    def normalize_event_type(cls, raw_type: str) -> str:
        """Map raw vendor or standard event type into a canonical event identifier."""
        return cls.EVENT_TYPE_MAPPING.get(raw_type.strip(), raw_type.upper().replace(".", "_"))

    @classmethod
    def normalize_failure_code(cls, raw_code: str | None) -> str:
        """Normalize failure codes to standard categories."""
        if not raw_code:
            return FailureCategory.UNKNOWN.value
        cleaned = raw_code.strip().lower()
        return cls.FAILURE_CODE_MAPPING.get(cleaned, cleaned)

    @classmethod
    def normalize_timestamp(cls, raw_ts: Any) -> datetime:
        """Convert unix epoch (seconds/milliseconds) or ISO string into timezone-aware UTC datetime."""
        if isinstance(raw_ts, (int, float)):
            # If timestamp is in milliseconds (> 1e11), convert to seconds
            seconds = raw_ts / 1000.0 if raw_ts > 1e11 else float(raw_ts)
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        if isinstance(raw_ts, str):
            try:
                # Handle ISO 8601 string
                dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass
        if isinstance(raw_ts, datetime):
            if raw_ts.tzinfo is None:
                return raw_ts.replace(tzinfo=timezone.utc)
            return raw_ts
        return utc_now()

    @classmethod
    def normalize_canonical_request(cls, req: EventIngestRequestDTO) -> CanonicalEventDTO:
        """Normalize an explicit EventIngestRequestDTO."""
        ext_event_id = req.event_id or f"evt_ing_{uuid4().hex[:12]}"
        occurred_at = cls.normalize_timestamp(req.occurred_at)
        canonical_type = cls.normalize_event_type(req.event_type)
        failure_code = cls.normalize_failure_code(req.failure_code) if req.failure_code else None

        return CanonicalEventDTO(
            external_event_id=ext_event_id,
            event_type=canonical_type,
            provider=req.provider.strip().lower(),
            occurred_at=occurred_at,
            customer_reference=req.customer_reference.strip(),
            payment_reference=req.payment_reference.strip() if req.payment_reference else None,
            subscription_reference=req.subscription_reference.strip() if req.subscription_reference else None,
            invoice_reference=req.invoice_reference.strip() if req.invoice_reference else None,
            checkout_session_id=req.checkout_session_id.strip() if req.checkout_session_id else None,
            amount_minor=int(req.amount_minor),
            currency=req.currency.strip().upper(),
            failure_code=failure_code,
            failure_message=req.failure_message.strip() if req.failure_message else None,
            metadata=cls.sanitize_metadata(req.metadata),
        )

    @classmethod
    def normalize_simulator_request(cls, sim: SimulateFailureRequestDTO) -> CanonicalEventDTO:
        """Normalize a development simulator request."""
        ext_event_id = f"evt_sim_{uuid4().hex[:12]}"
        payment_id = f"txn_sim_{uuid4().hex[:10]}"
        occurred_at = utc_now()

        return CanonicalEventDTO(
            external_event_id=ext_event_id,
            event_type=CanonicalEventType.PAYMENT_FAILED.value,
            provider="synthetic",
            occurred_at=occurred_at,
            customer_reference=sim.customer_id.strip(),
            payment_reference=payment_id,
            subscription_reference=None,
            invoice_reference=None,
            checkout_session_id=None,
            amount_minor=int(sim.amount_minor),
            currency=sim.currency.strip().upper(),
            failure_code=cls.normalize_failure_code(sim.failure_code),
            failure_message=sim.failure_message.strip(),
            metadata=cls.sanitize_metadata(sim.metadata),
        )

    @classmethod
    def normalize_raw_provider_webhook(
        cls,
        raw_payload: dict[str, Any],
        provider: str = "stripe",
        event_id_header: str | None = None,
    ) -> CanonicalEventDTO:
        """Normalize standard gateway webhook bodies (Stripe, Razorpay, Generic)."""
        prov = provider.strip().lower()
        metadata: dict[str, Any] = {}

        # 1. Stripe Format
        if "data" in raw_payload and "object" in raw_payload["data"]:
            obj = raw_payload["data"]["object"]
            ext_id = raw_payload.get("id") or event_id_header or f"evt_str_{uuid4().hex[:12]}"
            raw_type = raw_payload.get("type", "payment_intent.payment_failed")
            occurred_at = cls.normalize_timestamp(raw_payload.get("created", utc_now()))

            customer_ref = str(obj.get("customer") or obj.get("customer_id") or "cust_unknown")
            payment_ref = str(obj.get("id") or "txn_unknown")
            amount_minor = int(obj.get("amount", 0))
            currency = str(obj.get("currency", "USD")).upper()

            last_error = obj.get("last_payment_error") or {}
            failure_code = cls.normalize_failure_code(last_error.get("code") or obj.get("failure_code"))
            failure_msg = last_error.get("message") or obj.get("failure_message")

            metadata = {"gateway_status": obj.get("status"), "livemode": raw_payload.get("livemode")}

        # 2. Razorpay Format
        elif "payload" in raw_payload and "payment" in raw_payload["payload"]:
            pay_entity = raw_payload["payload"]["payment"].get("entity", {})
            ext_id = event_id_header or raw_payload.get("id") or f"evt_rzp_{uuid4().hex[:12]}"
            raw_type = raw_payload.get("event", "payment.failed")
            occurred_at = cls.normalize_timestamp(raw_payload.get("created_at", utc_now()))

            customer_ref = str(pay_entity.get("contact") or pay_entity.get("email") or "cust_unknown")
            payment_ref = str(pay_entity.get("id") or "pay_unknown")
            amount_minor = int(pay_entity.get("amount", 0))
            currency = str(pay_entity.get("currency", "INR")).upper()

            failure_code = cls.normalize_failure_code(pay_entity.get("error_code"))
            failure_msg = pay_entity.get("error_description")

            metadata = {"method": pay_entity.get("method")}

        # 3. Direct / Generic JSON Format
        else:
            ext_id = (
                event_id_header
                or raw_payload.get("id")
                or raw_payload.get("event_id")
                or f"evt_gen_{uuid4().hex[:12]}"
            )
            raw_type = raw_payload.get("event_type") or raw_payload.get("type") or "PAYMENT_FAILED"
            occurred_at = cls.normalize_timestamp(raw_payload.get("occurred_at") or raw_payload.get("created"))

            customer_ref = str(
                raw_payload.get("customer_reference")
                or raw_payload.get("customer_id")
                or raw_payload.get("customer")
                or "cust_unknown"
            )
            payment_ref = str(
                raw_payload.get("payment_reference")
                or raw_payload.get("transaction_id")
                or raw_payload.get("payment_id")
                or ""
            ) or None

            amount_minor = int(raw_payload.get("amount_minor") or raw_payload.get("amount") or 0)
            currency = str(raw_payload.get("currency", "USD")).upper()

            failure_code = cls.normalize_failure_code(raw_payload.get("failure_code"))
            failure_msg = raw_payload.get("failure_message") or raw_payload.get("message")
            metadata = raw_payload.get("metadata") or {}

        return CanonicalEventDTO(
            external_event_id=ext_id,
            event_type=cls.normalize_event_type(raw_type),
            provider=prov,
            occurred_at=occurred_at,
            customer_reference=customer_ref,
            payment_reference=payment_ref,
            subscription_reference=str(raw_payload.get("subscription_id") or "") or None,
            invoice_reference=str(raw_payload.get("invoice_id") or "") or None,
            checkout_session_id=str(raw_payload.get("checkout_session_id") or "") or None,
            amount_minor=amount_minor,
            currency=currency,
            failure_code=failure_code,
            failure_message=failure_msg,
            metadata=cls.sanitize_metadata(metadata),
        )
