"""Global error handling foundation and standard error contracts.

Author: Karthikeya
Architectural layer: core infrastructure.

This module establishes the RFC-7807 compliant error response format,
custom domain exception hierarchy, and global exception handlers.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("revenuerescue.errors")

# HTTP status 422 unprocessable content
HTTP_422_STATUS = 422


def utc_iso_now() -> str:
    """Return an ISO 8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


class ErrorDetail(BaseModel):
    """Granular error detail for field-level validation or domain checks."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """Standardized RFC-7807 compliant problem response payload."""

    success: bool = False
    error_code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable problem summary")
    request_id: str | None = Field(default=None, description="Request or correlation identifier")
    timestamp: str = Field(default_factory=utc_iso_now, description="UTC ISO-8601 timestamp")
    details: list[ErrorDetail] = Field(default_factory=list, description="Field-specific error details")


class RevenueRescueException(Exception):
    """Base exception for all domain and infrastructure errors in RevenueRescue AI."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: list[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or []


class EntityNotFoundException(RevenueRescueException):
    """Raised when a requested resource does not exist."""

    def __init__(self, entity_name: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_name} with identifier '{entity_id}' not found.",
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=[ErrorDetail(field="id", message="Resource does not exist", code="NOT_FOUND")],
        )


class DuplicateEntityException(RevenueRescueException):
    """Raised when a unique constraint or idempotency invariant is violated."""

    def __init__(self, entity_name: str, identifier: str) -> None:
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' already exists.",
            error_code="DUPLICATE_ENTITY",
            status_code=status.HTTP_409_CONFLICT,
            details=[ErrorDetail(field="id", message="Duplicate resource detected", code="CONFLICT")],
        )


class PolicyViolationException(RevenueRescueException):
    """Raised when an operation violates a deterministic safety rule."""

    def __init__(self, rule_name: str, reason: str) -> None:
        super().__init__(
            message=f"Policy rule '{rule_name}' violated: {reason}",
            error_code="POLICY_VIOLATION",
            status_code=HTTP_422_STATUS,
            details=[ErrorDetail(field=rule_name, message=reason, code="POLICY_BLOCKED")],
        )


class DatabaseConnectionException(RevenueRescueException):
    """Raised when the database connection cannot be established or drops."""

    def __init__(self, details: str = "Database connection failed.") -> None:
        super().__init__(
            message="Database connectivity is currently unavailable.",
            error_code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=[ErrorDetail(message=details, code="CONNECTION_FAILED")],
        )


class InvalidStateTransitionException(RevenueRescueException):
    """Raised when attempting an illegal finite state machine transition."""

    def __init__(self, current_state: str, target_state: str) -> None:
        super().__init__(
            message=f"Illegal state transition from '{current_state}' to '{target_state}'.",
            error_code="INVALID_STATE_TRANSITION",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=[
                ErrorDetail(
                    field="state",
                    message=f"Cannot transition from {current_state} to {target_state}",
                    code="ILLEGAL_TRANSITION",
                )
            ],
        )


class IdempotencyConflictException(RevenueRescueException):
    """Raised when a request is resubmitted with an existing key but conflicting payload/state."""

    def __init__(self, idempotency_key: str, reason: str = "Conflicting request with active key.") -> None:
        super().__init__(
            message=f"Idempotency conflict for key '{idempotency_key}': {reason}",
            error_code="IDEMPOTENCY_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=[ErrorDetail(field="idempotency_key", message=reason, code="IDEMPOTENCY_CONFLICT")],
        )


class MalformedRequestException(RevenueRescueException):
    """Raised when client request parameters or payload are structurally invalid or corrupted."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(
            message=message,
            error_code="MALFORMED_REQUEST",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=[ErrorDetail(field=field, message=message, code="MALFORMED_INPUT")] if field else [],
        )


class UnauthorizedException(RevenueRescueException):
    """Raised when authentication credentials are required but missing or invalid."""

    def __init__(self, message: str = "Authentication credentials missing or invalid.") -> None:
        super().__init__(
            message=message,
            error_code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=[ErrorDetail(message=message, code="UNAUTHORIZED")],
        )


class ForbiddenException(RevenueRescueException):
    """Raised when the authenticated caller lacks permission to perform the requested operation."""

    def __init__(self, message: str = "Access forbidden for the requested resource.") -> None:
        super().__init__(
            message=message,
            error_code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details=[ErrorDetail(message=message, code="FORBIDDEN")],
        )


class EventValidationException(RevenueRescueException):
    """Raised when an incoming revenue-risk event fails field-level validation."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(
            message=message,
            error_code="EVENT_VALIDATION_FAILED",
            status_code=HTTP_422_STATUS,
            details=[ErrorDetail(field=field, message=message, code="VALIDATION_ERROR")] if field else [],
        )


class ConflictingDuplicateEventException(RevenueRescueException):
    """Raised when an event ID is re-submitted with a different payload body."""

    def __init__(self, event_id: str, provider: str = "provider") -> None:
        super().__init__(
            message=f"Event '{event_id}' from provider '{provider}' already exists with differing payload content.",
            error_code="CONFLICTING_DUPLICATE_EVENT",
            status_code=status.HTTP_409_CONFLICT,
            details=[ErrorDetail(field="external_event_id", message="Conflicting payload hash detected", code="CONFLICT")],
        )


class UnauthorizedEventSourceException(RevenueRescueException):
    """Raised when an event source fails signature or credential checks."""

    def __init__(self, message: str = "Invalid or unverified event source signature.") -> None:
        super().__init__(
            message=message,
            error_code="UNAUTHORIZED_EVENT_SOURCE",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=[ErrorDetail(message=message, code="INVALID_SIGNATURE")],
        )


class UnsupportedEventTypeException(RevenueRescueException):
    """Raised when an unrecognized event type is submitted for ingestion."""

    def __init__(self, event_type: str) -> None:
        super().__init__(
            message=f"Unsupported event type: '{event_type}'.",
            error_code="UNSUPPORTED_EVENT_TYPE",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=[ErrorDetail(field="event_type", message=f"Type '{event_type}' is not supported", code="UNSUPPORTED_TYPE")],
        )



def _get_request_id(request: Request) -> str | None:
    """Extract request-id or correlation-id from request headers or state."""
    return (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or getattr(request.state, "request_id", None)
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform global exception handlers on the FastAPI application."""

    @app.exception_handler(RevenueRescueException)
    async def revenue_rescue_exception_handler(
        request: Request, exc: RevenueRescueException
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.warning(
            "Domain exception: code=%s, status=%d, message=%s, request_id=%s",
            exc.error_code,
            exc.status_code,
            exc.message,
            request_id,
        )
        response_payload = ErrorResponse(
            success=False,
            error_code=exc.error_code,
            message=exc.message,
            request_id=request_id,
            timestamp=utc_iso_now(),
            details=exc.details,
        )
        return JSONResponse(status_code=exc.status_code, content=response_payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        formatted_details = [
            ErrorDetail(
                field=".".join(str(loc) for loc in err.get("loc", []) if loc != "body"),
                message=err.get("msg", "Validation error"),
                code=err.get("type", "invalid"),
            )
            for err in exc.errors()
        ]
        logger.info("Validation error on %s: request_id=%s", request.url.path, request_id)
        response_payload = ErrorResponse(
            success=False,
            error_code="VALIDATION_FAILED",
            message="The request payload failed input schema validation.",
            request_id=request_id,
            timestamp=utc_iso_now(),
            details=formatted_details,
        )
        return JSONResponse(
            status_code=HTTP_422_STATUS,
            content=response_payload.model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = _get_request_id(request)
        error_code = "HTTP_ERROR"
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = "UNAUTHORIZED"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = "FORBIDDEN"
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            error_code = "RESOURCE_NOT_FOUND"
        elif exc.status_code == status.HTTP_400_BAD_REQUEST:
            error_code = "BAD_REQUEST"

        message = str(exc.detail) if isinstance(exc.detail, str) else "HTTP request failed."
        response_payload = ErrorResponse(
            success=False,
            error_code=error_code,
            message=message,
            request_id=request_id,
            timestamp=utc_iso_now(),
            details=[ErrorDetail(message=message, code=error_code)],
        )
        return JSONResponse(status_code=exc.status_code, content=response_payload.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.error(
            "Unhandled server exception on %s %s: request_id=%s",
            request.method,
            request.url.path,
            request_id,
            exc_info=exc,
        )
        response_payload = ErrorResponse(
            success=False,
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal error occurred. Please contact support with the request ID.",
            request_id=request_id,
            timestamp=utc_iso_now(),
            details=[],
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_payload.model_dump(),
        )
