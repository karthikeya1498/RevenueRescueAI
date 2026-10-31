"""HTTP REST endpoints for Revenue-Risk Event Ingestion, Webhooks, and Development Simulation.

Author: Karthikeya
Architectural layer: API controllers / routing.

Exposes:
- POST /api/v1/events: Canonical event ingestion
- POST /api/v1/webhooks/provider: Gateway webhook ingress with signature check
- POST /api/v1/events/simulate-failure: Development event simulator
- GET /api/v1/events: Paginated event listing and filtering
- GET /api/v1/events/{event_id}: Single event detail lookup
"""

from __future__ import annotations

import hmac
import hashlib
import json
import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.errors import (
    MalformedRequestException,
    UnauthorizedEventSourceException,
)
from app.models.domain import User
from app.schemas.events import (
    EventDetailDTO,
    EventIngestRequestDTO,
    EventIngestResponseDTO,
    PaginatedEventsDTO,
    SimulateFailureRequestDTO,
)
from app.services.event_service import EventService

router = APIRouter(tags=["events"])


def verify_webhook_hmac(body: bytes, signature_header: str | None, secret: str) -> bool:
    """Validate raw payload HMAC-SHA256 digest against secret."""
    if not secret:
        # Development mode without secret configured accepts payload
        return True
    if not signature_header:
        return False

    # Normalize header: support hex digest directly or 'sha256=...' prefix
    sig = signature_header.strip()
    if sig.startswith("sha256="):
        sig = sig.split("=", 1)[1]

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), sig.lower())


@router.post(
    "/api/v1/events",
    response_model=EventIngestResponseDTO,
    summary="Ingest canonical revenue-risk event",
    description="Idempotently accepts, normalizes, validates, and persists a revenue-risk event.",
)
def ingest_event(
    request_dto: EventIngestRequestDTO,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles([UserRole.OPERATOR, UserRole.ADMIN, UserRole.INGESTOR])
    ),
    x_correlation_id: str | None = Header(default=None),
) -> EventIngestResponseDTO:
    """Ingest a validated revenue-risk event directly from an authorized source."""
    service = EventService(db)
    result = service.ingest_canonical_event(
        request_dto,
        signature_verified=True,
        correlation_id=x_correlation_id,
    )
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_201_CREATED
    return result


@router.post(
    "/api/v1/webhooks/provider",
    response_model=EventIngestResponseDTO,
    summary="Ingest payment gateway webhook",
    description="Idempotently receives external provider webhook (Stripe, Razorpay) with HMAC validation.",
)
async def ingest_provider_webhook(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_signature_sha256: str | None = Header(default=None),
    x_event_id: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None),
) -> EventIngestResponseDTO:
    """Ingest external payment gateway webhook with cryptographic replay protection."""
    raw_body = await request.body()
    if not raw_body:
        raise MalformedRequestException("Webhook request body cannot be empty.")

    # Determine provider signature from standard or vendor headers
    sig = (
        x_signature_sha256
        or request.headers.get("x-razorpay-signature")
        or request.headers.get("stripe-signature")
    )
    event_id = (
        x_event_id
        or request.headers.get("x-razorpay-event-id")
        or request.headers.get("stripe-event-id")
    )

    webhook_secret = (
        os.getenv("WEBHOOK_SIGNING_SECRET")
        or os.getenv("RAZORPAY_WEBHOOK_SECRET")
        or os.getenv("STRIPE_WEBHOOK_SECRET")
        or ""
    )

    verified = verify_webhook_hmac(raw_body, sig, webhook_secret)
    if not verified:
        raise UnauthorizedEventSourceException("Webhook signature verification failed.")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
    except Exception as exc:
        raise MalformedRequestException(f"Invalid JSON payload: {exc}") from exc

    # Identify provider hint
    provider_hint = "stripe"
    if "razorpay" in request.headers.get("user-agent", "").lower() or "payload" in payload:
        provider_hint = "razorpay"
    elif "synthetic" in str(payload.get("provider", "")):
        provider_hint = "synthetic"

    service = EventService(db)
    result = service.ingest_raw_webhook(
        payload,
        provider=provider_hint,
        event_id_header=event_id,
        signature_verified=True,
        correlation_id=x_correlation_id,
    )
    if result.duplicate:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_200_OK
    return result


@router.post(
    "/api/v1/webhooks/razorpay",
    response_model=EventIngestResponseDTO,
    summary="Ingest Razorpay webhook",
    description="Receives Razorpay payment and refund webhooks with HMAC-SHA256 signature verification.",
)
async def ingest_razorpay_webhook(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_razorpay_signature: str | None = Header(default=None),
    x_razorpay_event_id: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None),
) -> EventIngestResponseDTO:
    """Ingest Razorpay webhook with HMAC-SHA256 signature verification and idempotency."""
    from app.core.config import get_settings
    from app.services.verification import verify_signature

    raw_body = await request.body()
    if not raw_body:
        raise MalformedRequestException("Razorpay webhook body cannot be empty.")

    settings = get_settings()
    secret = (
        os.getenv("RAZORPAY_WEBHOOK_SECRET")
        or settings.payment_webhook_secret
        or settings.razorpay_webhook_secret
        or ""
    )

    sig = x_razorpay_signature or request.headers.get("x-razorpay-signature")
    if secret:
        if not sig or not verify_signature(raw_body, sig, secret):
            raise UnauthorizedEventSourceException("Razorpay webhook signature verification failed.")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
    except Exception as exc:
        raise MalformedRequestException(f"Invalid JSON payload: {exc}") from exc

    service = EventService(db)
    result = service.ingest_raw_webhook(
        payload,
        provider="razorpay",
        event_id_header=x_razorpay_event_id,
        signature_verified=True,
        correlation_id=x_correlation_id,
    )
    response.status_code = status.HTTP_200_OK
    return result



@router.post(
    "/api/v1/events/simulate-failure",
    response_model=EventIngestResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Simulate synthetic payment failure",
    description="Development-only simulator to trigger deterministic payment failure events.",
)
def simulate_failure(
    sim_request: SimulateFailureRequestDTO,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.OPERATOR, UserRole.ADMIN])),
    x_correlation_id: str | None = Header(default=None),
) -> EventIngestResponseDTO:
    """Generate a deterministic synthetic payment failure for testing and demo."""
    service = EventService(db)
    return service.simulate_failure_event(sim_request, correlation_id=x_correlation_id)


@router.get(
    "/api/v1/events",
    response_model=PaginatedEventsDTO,
    summary="List ingested events",
    description="Paginated retrieval of ingested provider events with filtering.",
)
def list_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: str | None = Query(default=None, description="Filter by provider (e.g. stripe, synthetic)"),
    event_type: str | None = Query(default=None, description="Filter by canonical event type"),
    status: str | None = Query(default=None, description="Filter by ingestion status"),
    processed: bool | None = Query(default=None, description="Filter by downstream processed flag"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginatedEventsDTO:
    """Query ingested events with pagination and filters."""
    service = EventService(db)
    return service.list_events(
        provider=provider,
        event_type=event_type,
        ingestion_status=status,
        processed=processed,
        page=page,
        limit=limit,
    )


@router.get(
    "/api/v1/events/{event_id}",
    response_model=EventDetailDTO,
    summary="Get ingested event details",
    description="Retrieve complete record of an ingested event by internal UUID or external event ID.",
)
def get_event_detail(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventDetailDTO:
    """Retrieve single ingested event details."""
    service = EventService(db)
    return service.get_event_by_id(event_id)
