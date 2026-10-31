"""Recovery case management and lifecycle API endpoints.

Author: Karthikeya
Architectural layer: API controller.

Endpoints:
- GET /api/v1/cases: Paginated, filterable collection of recovery cases with search.
- GET /api/v1/cases/{case_id}: Detailed representation of a recovery case with customer and transaction details.
- PATCH /api/v1/cases/{case_id}: Update case priority or permitted context metadata.
- POST /api/v1/cases/{case_id}/transition: Execute and audit explicit FSM state transitions.
- GET /api/v1/cases/{case_id}/history: Chronological compliance audit event timeline.
- GET /api/v1/cases/{case_id}/events: Associated provider and gateway webhook receipts.
"""

from __future__ import annotations

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_operator, require_roles
from app.core.database import get_db
from app.core.enums import RecoveryCaseState, UserRole
from app.core.errors import EntityNotFoundException
from app.mappers.recovery_cases import RecoveryCaseMapper
from app.models.domain import Customer, RecoveryCase, Transaction, User
from app.schemas.audit_events import AuditEventResponseDTO
from app.schemas.common import PaginatedResponse, PaginationMetadata
from app.schemas.events import EventSummaryDTO
from app.schemas.recommendations import CaseRecommendationDTO
from app.schemas.recovery_cases import (
    CaseDetailResponseDTO,
    CaseStateTransitionDTO,
    CaseSummaryItemDTO,
    RecoveryCaseResponseDTO,
    RecoveryCaseUpdateDTO,
)
from app.services.intelligence.orchestrator import IntelligenceOrchestrator
from app.services.recovery_case_service import RecoveryCaseService

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])

# Case read operations are authorized for Operators, Admins, and Compliance Auditors
case_viewers = require_roles([UserRole.ADMIN, UserRole.OPERATOR, UserRole.AUDITOR])


@router.get(
    "",
    response_model=PaginatedResponse[CaseSummaryItemDTO],
    summary="List recovery cases",
)
def list_cases(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(case_viewers)],
    state: str | None = Query(None, description="Filter by case lifecycle state (case-insensitive)"),
    customer_id: UUID | None = Query(None, description="Filter by customer UUID"),
    priority_min: int | None = Query(None, ge=1, le=1000, description="Minimum priority score"),
    priority_max: int | None = Query(None, ge=1, le=1000, description="Maximum priority score"),
    risk_tier: str | None = Query(None, description="Filter by risk tier (high, medium, low)"),
    search: str | None = Query(None, min_length=1, max_length=100, description="Search case key or references"),
    sort_by: str = Query("priority", description="Sort field: priority, opened_at, last_state_changed_at"),
    sort_order: str = Query("asc", description="Sort direction: asc or desc"),
    page: int = Query(1, ge=1, description="1-indexed page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[CaseSummaryItemDTO]:
    """Return a paginated, filterable collection of recovery cases for the operator queue."""
    offset = (page - 1) * size

    # Parse state case-insensitively
    parsed_state: RecoveryCaseState | None = None
    if state is not None:
        try:
            parsed_state = RecoveryCaseState(state.lower())
        except ValueError:
            pass

    # Build base where criteria
    filters = []
    if parsed_state is not None:
        filters.append(RecoveryCase.state == parsed_state)
    elif state is not None:
        filters.append(RecoveryCase.state == None)  # noqa: E711
    if customer_id is not None:
        filters.append(RecoveryCase.customer_id == customer_id)
    if priority_min is not None:
        filters.append(RecoveryCase.priority >= priority_min)
    if priority_max is not None:
        filters.append(RecoveryCase.priority <= priority_max)
    if search is not None:
        search_pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                RecoveryCase.case_key.ilike(search_pattern),
                RecoveryCase.customer.has(Customer.external_customer_id.ilike(search_pattern)),
                RecoveryCase.trigger_transaction.has(Transaction.external_transaction_id.ilike(search_pattern)),
            )
        )

    # 1. Total count query
    count_stmt = select(func.count(RecoveryCase.id))
    for f in filters:
        count_stmt = count_stmt.where(f)
    total = db.scalar(count_stmt) or 0

    # 2. Item query with eager loaded relationships to prevent N+1 query overhead
    query = (
        select(RecoveryCase)
        .options(
            joinedload(RecoveryCase.customer),
            joinedload(RecoveryCase.trigger_transaction),
            joinedload(RecoveryCase.attempts),
        )
    )
    for f in filters:
        query = query.where(f)

    # Sorting
    sort_col = RecoveryCase.priority
    if sort_by == "opened_at":
        sort_col = RecoveryCase.opened_at
    elif sort_by == "last_state_changed_at":
        sort_col = RecoveryCase.last_state_changed_at

    if sort_order.lower() == "desc":
        query = query.order_by(sort_col.desc(), RecoveryCase.opened_at.desc())
    else:
        query = query.order_by(sort_col.asc(), RecoveryCase.last_state_changed_at.desc())

    query = query.limit(size).offset(offset)

    entities = db.scalars(query).unique().all()

    # In-memory post-filter for JSON metadata risk_tier if specified
    if risk_tier is not None:
        clean_tier = risk_tier.strip().lower()
        entities = [
            c for c in entities
            if (c.metadata_json or {}).get("risk_tier", "").lower() == clean_tier
        ]

    items = [RecoveryCaseMapper.to_summary_item(c) for c in entities]

    total_pages = math.ceil(total / size) if total > 0 else 0
    has_more = page < total_pages

    return PaginatedResponse(
        items=items,
        pagination=PaginationMetadata(
            total=total,
            page=page,
            size=size,
            pages=total_pages,
            has_more=has_more,
        ),
    )


@router.get(
    "/{case_id}",
    response_model=CaseDetailResponseDTO,
    summary="Get recovery case detail",
)
def get_case_detail(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(case_viewers)],
) -> CaseDetailResponseDTO:
    """Return comprehensive case details including customer, trigger transaction, and attempt history."""
    query = (
        select(RecoveryCase)
        .options(
            joinedload(RecoveryCase.customer),
            joinedload(RecoveryCase.trigger_transaction),
            joinedload(RecoveryCase.attempts),
        )
        .where(RecoveryCase.id == case_id)
    )
    case = db.scalars(query).unique().first()
    if case is None:
        raise EntityNotFoundException("RecoveryCase", str(case_id))

    return RecoveryCaseMapper.to_detail_response(case)


@router.patch(
    "/{case_id}",
    response_model=RecoveryCaseResponseDTO,
    summary="Update recovery case priority or metadata",
)
def update_case(
    case_id: UUID,
    update_dto: RecoveryCaseUpdateDTO,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
) -> RecoveryCaseResponseDTO:
    """Update case priority or permitted context metadata under operator authority."""
    service = RecoveryCaseService(db)
    return service.update_case(case_id, update_dto, actor_id=str(current_user.id))


@router.post(
    "/{case_id}/transition",
    response_model=RecoveryCaseResponseDTO,
    summary="Transition recovery case state",
)
def transition_case_state(
    case_id: UUID,
    transition_dto: CaseStateTransitionDTO,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
) -> RecoveryCaseResponseDTO:
    """Execute and record an explicit finite-state-machine state transition on a recovery case."""
    service = RecoveryCaseService(db)
    return service.transition_state(case_id, transition_dto)


@router.get(
    "/{case_id}/history",
    response_model=list[AuditEventResponseDTO],
    summary="Get case audit history timeline",
)
def get_case_history(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(case_viewers)],
) -> list[AuditEventResponseDTO]:
    """Retrieve the monotonic chronological audit event history for a recovery case."""
    service = RecoveryCaseService(db)
    return service.get_case_timeline(case_id)


@router.get(
    "/{case_id}/events",
    response_model=list[EventSummaryDTO],
    summary="Get case associated gateway events",
)
def get_case_events(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(case_viewers)],
) -> list[EventSummaryDTO]:
    """Retrieve all ingested gateway and webhook events associated with this recovery case."""
    service = RecoveryCaseService(db)
    return service.get_case_events(case_id)


@router.post(
    "/{case_id}/recommendations",
    response_model=CaseRecommendationDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI recovery recommendation",
)
def generate_case_recommendation(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_operator)],
) -> CaseRecommendationDTO:
    """Analyse failure, assess risk, calculate expected value, and generate recommendation.

    Note: The recommendation is persisted with validation_status = NOT_VALIDATED.
    It does NOT execute payment retries or communications. Action authorization
    is deferred to the Phase 2.9 Recovery Policy Engine.
    """
    orchestrator = IntelligenceOrchestrator(db)
    return orchestrator.generate_recommendation(
        case_id, current_user_id=str(current_user.id)
    )


@router.get(
    "/{case_id}/recommendations/latest",
    response_model=CaseRecommendationDTO,
    summary="Get latest AI recovery recommendation",
)
def get_latest_case_recommendation(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(case_viewers)],
) -> CaseRecommendationDTO:
    """Retrieve the most recent AI recommendation generated for this recovery case."""
    orchestrator = IntelligenceOrchestrator(db)
    rec = orchestrator.get_latest_recommendation(case_id)
    if rec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recovery recommendation generated for case {case_id}",
        )
    return rec


@router.get(
    "/{case_id}/recommendations",
    response_model=list[CaseRecommendationDTO],
    summary="Get AI recommendation history for case",
)
def get_case_recommendation_history(
    case_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(case_viewers)],
) -> list[CaseRecommendationDTO]:
    """Retrieve all historical recommendations formulated for this recovery case."""
    orchestrator = IntelligenceOrchestrator(db)
    return orchestrator.get_recommendation_history(case_id)
