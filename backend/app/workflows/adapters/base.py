"""Abstract payment execution adapter contracts for bounded recovery execution.

Author: Karthikeya
Architectural layer: workflow adapters / payment gateway boundary.

Separates internal workflow intent from external vendor-specific network calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.database import utc_now
from app.core.enums import ExecutionStatus


@dataclass(frozen=True)
class PaymentRetryRequest:
    """Internal normalized request for a payment retry attempt."""

    case_id: UUID
    transaction_id: UUID
    amount_minor: int
    currency: str
    customer_reference: str
    idempotency_key: str
    customer_email: str | None = None
    customer_contact: str | None = None
    payment_method: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaymentStatusQuery:
    """Query parameters to fetch payment state directly from the gateway."""

    provider_payment_id: str
    correlation_id: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Normalized outcome returned from a payment adapter execution.

    Invariants:
    - SUBMITTED indicates gateway accepted the instruction; it does NOT mean money is recovered.
    - UNKNOWN indicates timeout or transport failure; caller must NEVER auto-retry without reconciliation.
    - raw_response_safe must be sanitized of any card PANs, CVVs, or credentials.
    """

    status: ExecutionStatus
    provider: str
    provider_payment_id: str | None
    provider_order_id: str | None
    amount_minor: int
    currency: str
    error_code: str | None
    error_message_safe: str | None
    raw_response_safe: dict[str, Any]
    latency_ms: int
    executed_at: datetime = field(default_factory=utc_now)
    is_definitive: bool = True


class PaymentExecutionAdapter(ABC):
    """Abstract interface that all payment gateway adapters must implement."""

    @abstractmethod
    def submit_retry(self, request: PaymentRetryRequest) -> ExecutionResult:
        """Submit a payment retry request to the gateway.

        Must be idempotent using request.idempotency_key.
        """
        raise NotImplementedError

    @abstractmethod
    def retrieve_status(self, query: PaymentStatusQuery) -> ExecutionResult:
        """Fetch authoritative status of a prior payment from the gateway."""
        raise NotImplementedError
