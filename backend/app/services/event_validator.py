"""Event validation component for RevenueRescueAI.

Author: Karthikeya
Architectural layer: domain validation service.

Validates common fields and event-type-specific requirements on CanonicalEventDTO.
"""

from __future__ import annotations

from datetime import timedelta, timezone

from app.core.database import utc_now
from app.core.enums import CanonicalEventType
from app.core.errors import EventValidationException, UnsupportedEventTypeException
from app.schemas.events import CanonicalEventDTO


class EventValidator:
    """Validates common and event-specific domain rules on CanonicalEventDTO."""

    SUPPORTED_EVENT_TYPES = {
        CanonicalEventType.PAYMENT_FAILED.value,
        CanonicalEventType.PAYMENT_SUCCEEDED.value,
        CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value,
        CanonicalEventType.CHECKOUT_ABANDONED.value,
        CanonicalEventType.INVOICE_OVERDUE.value,
    }

    @classmethod
    def validate(cls, event: CanonicalEventDTO) -> None:
        """Run common and event-type-specific checks on normalized event.
        
        Raises EventValidationException or UnsupportedEventTypeException on rule violation.
        """
        # 1. Supported Event Type check
        if event.event_type not in cls.SUPPORTED_EVENT_TYPES:
            raise UnsupportedEventTypeException(event.event_type)

        # 2. Common Invariants
        if not event.external_event_id or not event.external_event_id.strip():
            raise EventValidationException("Event external_event_id cannot be empty.", field="external_event_id")

        if len(event.external_event_id) > 200:
            raise EventValidationException("Event external_event_id exceeds maximum length of 200.", field="external_event_id")

        if not event.provider or not event.provider.strip():
            raise EventValidationException("Event provider cannot be empty.", field="provider")

        if len(event.provider) > 64:
            raise EventValidationException("Event provider exceeds maximum length of 64.", field="provider")

        if not event.customer_reference or not event.customer_reference.strip():
            raise EventValidationException("Customer reference cannot be empty.", field="customer_reference")

        if len(event.customer_reference) > 128:
            raise EventValidationException("Customer reference exceeds maximum length of 128.", field="customer_reference")

        if event.amount_minor < 0:
            raise EventValidationException("Monetary amount_minor must be non-negative.", field="amount_minor")

        if len(event.currency) != 3 or event.currency != event.currency.upper():
            raise EventValidationException("Currency must be an exact 3-letter uppercase ISO code.", field="currency")

        # Future clock skew check (reject timestamps > 15 minutes in the future)
        now_utc = utc_now()
        event_time = event.occurred_at
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if event_time > now_utc + timedelta(minutes=15):
            raise EventValidationException("Event occurred_at cannot be in the future.", field="occurred_at")

        # 3. Event-Type-Specific Rules
        if event.event_type == CanonicalEventType.PAYMENT_FAILED.value:
            cls._validate_payment_failed(event)
        elif event.event_type == CanonicalEventType.PAYMENT_SUCCEEDED.value:
            cls._validate_payment_succeeded(event)
        elif event.event_type == CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value:
            cls._validate_subscription_failed(event)
        elif event.event_type == CanonicalEventType.CHECKOUT_ABANDONED.value:
            cls._validate_checkout_abandoned(event)
        elif event.event_type == CanonicalEventType.INVOICE_OVERDUE.value:
            cls._validate_invoice_overdue(event)

    @classmethod
    def _validate_payment_failed(cls, event: CanonicalEventDTO) -> None:
        if not event.payment_reference or not event.payment_reference.strip():
            raise EventValidationException("PAYMENT_FAILED requires a payment_reference.", field="payment_reference")
        if not event.failure_code or not event.failure_code.strip():
            raise EventValidationException("PAYMENT_FAILED requires a failure_code.", field="failure_code")

    @classmethod
    def _validate_payment_succeeded(cls, event: CanonicalEventDTO) -> None:
        if not event.payment_reference or not event.payment_reference.strip():
            raise EventValidationException("PAYMENT_SUCCEEDED requires a payment_reference.", field="payment_reference")

    @classmethod
    def _validate_subscription_failed(cls, event: CanonicalEventDTO) -> None:
        if not (event.subscription_reference or event.payment_reference):
            raise EventValidationException(
                "SUBSCRIPTION_PAYMENT_FAILED requires a subscription_reference or payment_reference.",
                field="subscription_reference",
            )
        if not event.failure_code or not event.failure_code.strip():
            raise EventValidationException("SUBSCRIPTION_PAYMENT_FAILED requires a failure_code.", field="failure_code")

    @classmethod
    def _validate_checkout_abandoned(cls, event: CanonicalEventDTO) -> None:
        if not event.checkout_session_id and not event.metadata.get("checkout_id"):
            raise EventValidationException(
                "CHECKOUT_ABANDONED requires a checkout_session_id.",
                field="checkout_session_id",
            )

    @classmethod
    def _validate_invoice_overdue(cls, event: CanonicalEventDTO) -> None:
        if not event.invoice_reference and not event.metadata.get("invoice_id"):
            raise EventValidationException("INVOICE_OVERDUE requires an invoice_reference.", field="invoice_reference")
