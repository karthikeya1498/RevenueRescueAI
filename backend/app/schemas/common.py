"""Reusable core schema types, pagination envelopes, and financial DTOs.

Author: Karthikeya
Architectural layer: API DTO / contract.

Enforces strict Pydantic v2 validation, non-negative integer minor unit representation
of money, and RFC-compliant pagination envelopes.
"""

from __future__ import annotations

from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class MoneyMinorUnits(BaseModel):
    """Authoritative representation of monetary values in integer minor units (e.g. cents)."""

    model_config = ConfigDict(extra="forbid")

    amount_minor: int = Field(..., ge=0, description="Amount in minor currency units (e.g., cents, paise)")
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="3-letter ISO-4217 uppercase currency code",
    )


class PaginationParams(BaseModel):
    """Query parameter validation for paginated collection requests."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, description="1-based page index")
    size: int = Field(default=50, ge=1, le=100, description="Number of items per page (max 100)")

    @property
    def offset(self) -> int:
        """Calculate zero-based database query offset."""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """Alias for size matching SQL LIMIT clause."""
        return self.size


class PaginationMetadata(BaseModel):
    """Standard collection pagination envelope metadata."""

    total: int = Field(..., ge=0, description="Total number of items across all pages")
    page: int = Field(..., ge=1, description="Current 1-based page number")
    size: int = Field(..., ge=1, le=100, description="Number of items per page")
    pages: int = Field(..., ge=0, description="Total number of pages")
    has_more: bool = Field(..., description="Whether additional pages exist beyond current")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response envelope for all collection endpoints."""

    items: list[T] = Field(..., description="List of items for the current page")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")


class StatusResponseDTO(BaseModel):
    """Generic simple status acknowledgement response."""

    success: bool = Field(..., description="Whether the requested operation succeeded")
    message: str = Field(..., description="Human-readable operation summary")
