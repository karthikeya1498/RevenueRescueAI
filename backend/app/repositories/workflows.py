"""Recovery Workflow and Execution persistence repositories.

Architectural layer: data access / repository.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.enums import ExecutionStatus, WorkflowStatus
from app.models.domain import RecoveryExecution, RecoveryWorkflow, WorkflowStep


class WorkflowRepository:
    """Encapsulates relational persistence queries for recovery workflows."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, workflow_id: UUID) -> RecoveryWorkflow | None:
        return self.session.scalar(
            select(RecoveryWorkflow).where(RecoveryWorkflow.id == workflow_id)
        )

    def find_by_case(self, case_id: UUID) -> list[RecoveryWorkflow]:
        stmt = (
            select(RecoveryWorkflow)
            .where(RecoveryWorkflow.case_id == case_id)
            .order_by(desc(RecoveryWorkflow.created_at))
        )
        return list(self.session.scalars(stmt).all())

    def find_active_by_case(self, case_id: UUID) -> RecoveryWorkflow | None:
        """Find an active workflow (RUNNING, SCHEDULED, PENDING, WAITING) for a case."""
        active_statuses = {
            WorkflowStatus.RUNNING,
            WorkflowStatus.SCHEDULED,
            WorkflowStatus.PENDING,
            WorkflowStatus.WAITING,
        }
        stmt = (
            select(RecoveryWorkflow)
            .where(
                RecoveryWorkflow.case_id == case_id,
                RecoveryWorkflow.status.in_(active_statuses),
            )
            .limit(1)
        )
        return self.session.scalar(stmt)

    def save(self, workflow: RecoveryWorkflow) -> RecoveryWorkflow:
        self.session.add(workflow)
        return workflow


class WorkflowStepRepository:
    """Encapsulates relational queries for discrete workflow steps."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, step_id: UUID) -> WorkflowStep | None:
        return self.session.scalar(
            select(WorkflowStep).where(WorkflowStep.id == step_id)
        )

    def find_by_workflow(self, workflow_id: UUID) -> list[WorkflowStep]:
        stmt = (
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow_id)
            .order_by(WorkflowStep.step_index.asc())
        )
        return list(self.session.scalars(stmt).all())

    def find_by_idempotency_key(self, idempotency_key: str) -> WorkflowStep | None:
        stmt = select(WorkflowStep).where(WorkflowStep.idempotency_key == idempotency_key)
        return self.session.scalar(stmt)

    def save(self, step: WorkflowStep) -> WorkflowStep:
        self.session.add(step)
        return step


class RecoveryExecutionRepository:
    """Encapsulates persistence queries for provider execution dispatches."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, execution_id: UUID) -> RecoveryExecution | None:
        return self.session.scalar(
            select(RecoveryExecution).where(RecoveryExecution.id == execution_id)
        )

    def find_by_step(self, step_id: UUID) -> list[RecoveryExecution]:
        stmt = (
            select(RecoveryExecution)
            .where(RecoveryExecution.step_id == step_id)
            .order_by(desc(RecoveryExecution.executed_at))
        )
        return list(self.session.scalars(stmt).all())

    def find_by_case(self, case_id: UUID) -> list[RecoveryExecution]:
        stmt = (
            select(RecoveryExecution)
            .where(RecoveryExecution.case_id == case_id)
            .order_by(desc(RecoveryExecution.executed_at))
        )
        return list(self.session.scalars(stmt).all())

    def find_by_external_reference(self, external_reference: str) -> list[RecoveryExecution]:
        stmt = (
            select(RecoveryExecution)
            .where(RecoveryExecution.external_reference == external_reference)
            .order_by(desc(RecoveryExecution.executed_at))
        )
        return list(self.session.scalars(stmt).all())

    def find_by_idempotency_key(self, idempotency_key: str) -> RecoveryExecution | None:
        stmt = select(RecoveryExecution).where(
            RecoveryExecution.idempotency_key == idempotency_key
        )
        return self.session.scalar(stmt)

    def save(self, execution: RecoveryExecution) -> RecoveryExecution:
        self.session.add(execution)
        return execution
