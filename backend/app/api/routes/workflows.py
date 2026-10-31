"""HTTP REST Endpoints for Recovery Workflows, Execution, and Reconciliation.

Author: Karthikeya
Architectural layer: API controllers / routing.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import UserRole
from app.models.domain import User
from app.repositories.workflows import WorkflowRepository
from app.schemas.workflow import (
    ReconciliationRequestDTO,
    ReconciliationResponseDTO,
    WorkflowCreateRequestDTO,
    WorkflowDetailDTO,
    WorkflowExecuteRequestDTO,
)
from app.services.payment_reconciliation_service import PaymentReconciliationService
from app.workflows.creation_service import WorkflowCreationService
from app.workflows.execution_service import WorkflowExecutionService

router = APIRouter(tags=["workflows"])


@router.post(
    "/api/v1/workflows",
    response_model=WorkflowDetailDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Instantiate a recovery workflow",
    description="Creates a bounded execution workflow from an approved policy decision.",
)
def create_workflow(
    payload: WorkflowCreateRequestDTO,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.OPERATOR, UserRole.ADMIN])),
    x_correlation_id: str | None = Header(default=None),
) -> WorkflowDetailDTO:
    """Create a new recovery workflow from an APPROVED policy decision."""
    service = WorkflowCreationService(db)
    try:
        workflow = service.create_workflow_for_decision(
            payload.policy_decision_id,
            cooldown_hours=payload.cooldown_hours,
            max_workflow_hours=payload.max_workflow_hours,
        )
        db.commit()
        db.refresh(workflow)
        return WorkflowDetailDTO.model_validate(workflow)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/workflows/{workflow_id}/execute",
    response_model=WorkflowDetailDTO,
    summary="Execute workflow steps",
    description="Executes ready steps in the workflow through controlled adapters.",
)
def execute_workflow(
    workflow_id: UUID,
    payload: WorkflowExecuteRequestDTO,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.OPERATOR, UserRole.ADMIN])),
    x_correlation_id: str | None = Header(default=None),
) -> WorkflowDetailDTO:
    """Execute pending workflow steps sequentially."""
    service = WorkflowExecutionService(db)
    try:
        if payload.execute_all:
            workflow = service.execute_all_available_steps(
                workflow_id,
                actor_id=str(current_user.id),
                correlation_id=x_correlation_id,
                step_metadata_override=payload.step_metadata_override,
            )
        else:
            service.execute_next_step(
                workflow_id,
                actor_id=str(current_user.id),
                correlation_id=x_correlation_id,
                step_metadata_override=payload.step_metadata_override,
            )
            workflow = service.workflow_repo.find_by_id(workflow_id)

        db.commit()
        db.refresh(workflow)
        return WorkflowDetailDTO.model_validate(workflow)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/api/v1/workflows/{workflow_id}",
    response_model=WorkflowDetailDTO,
    summary="Get workflow details",
    description="Fetch a recovery workflow and its execution steps by ID.",
)
def get_workflow(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowDetailDTO:
    """Retrieve full details for a recovery workflow."""
    repo = WorkflowRepository(db)
    workflow = repo.find_by_id(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return WorkflowDetailDTO.model_validate(workflow)


@router.get(
    "/api/v1/cases/{case_id}/workflows",
    response_model=list[WorkflowDetailDTO],
    summary="List workflows for a recovery case",
    description="Returns all historical and active workflows for a case.",
)
def list_case_workflows(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkflowDetailDTO]:
    """Retrieve all workflows associated with a recovery case."""
    repo = WorkflowRepository(db)
    workflows = repo.find_by_case(case_id)
    return [WorkflowDetailDTO.model_validate(w) for w in workflows]


@router.post(
    "/api/v1/reconciliation/reconcile-case",
    response_model=ReconciliationResponseDTO,
    summary="Reconcile payment status for a case",
    description="Compares internal records against payment gateway truth and resolves discrepancies.",
)
def reconcile_case(
    payload: ReconciliationRequestDTO,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.OPERATOR, UserRole.ADMIN])),
    x_correlation_id: str | None = Header(default=None),
) -> ReconciliationResponseDTO:
    """Run payment reconciliation on a single recovery case."""
    service = PaymentReconciliationService(db)
    try:
        report = service.reconcile_case(
            payload.case_id,
            actor_id=str(current_user.id),
            correlation_id=x_correlation_id,
            auto_resolve=payload.auto_resolve,
        )
        return ReconciliationResponseDTO(
            case_id=report.case_id,
            transaction_id=report.transaction_id,
            internal_status=report.internal_status.value,
            provider_status=report.provider_status.value,
            status=report.status,
            discrepancies=report.discrepancies,
            resolution_action=report.resolution_action,
            reconciled_at=report.reconciled_at,
            details=report.details,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/reconciliation/reconcile-pending",
    response_model=list[ReconciliationResponseDTO],
    summary="Batch reconcile pending verification cases",
    description="Finds cases awaiting verification and synchronizes with provider gateway state.",
)
def reconcile_pending_cases(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.OPERATOR, UserRole.ADMIN])),
) -> list[ReconciliationResponseDTO]:
    """Batch reconcile cases currently in VERIFICATION_PENDING."""
    service = PaymentReconciliationService(db)
    reports = service.reconcile_pending_cases(limit=limit)
    return [
        ReconciliationResponseDTO(
            case_id=r.case_id,
            transaction_id=r.transaction_id,
            internal_status=r.internal_status.value,
            provider_status=r.provider_status.value,
            status=r.status,
            discrepancies=r.discrepancies,
            resolution_action=r.resolution_action,
            reconciled_at=r.reconciled_at,
            details=r.details,
        )
        for r in reports
    ]
