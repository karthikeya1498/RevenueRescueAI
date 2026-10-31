"""Workflow Creation Service.

Author: Karthikeya
Architectural layer: workflow orchestration / creation boundary.

Transforms approved PolicyDecisions into concrete, bounded RecoveryWorkflow
and WorkflowStep records with deterministic idempotency keys.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.database import utc_now
from app.core.enums import (
    ActionType,
    PolicyDecisionStatus,
    RecoveryCaseState,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepType,
)
from app.models.domain import PolicyDecision, RecoveryCase, RecoveryWorkflow, WorkflowStep
from app.repositories.workflows import WorkflowRepository, WorkflowStepRepository


class WorkflowCreationService:
    """Creates orchestrated workflows exclusively from APPROVED PolicyDecisions."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.workflow_repo = WorkflowRepository(session)
        self.step_repo = WorkflowStepRepository(session)

    def create_workflow_for_decision(
        self,
        decision_id: UUID,
        *,
        cooldown_hours: int = 4,
        max_workflow_hours: int = 72,
    ) -> RecoveryWorkflow:
        """Create a multi-step bounded recovery workflow from an approved decision."""
        decision = self.session.get(PolicyDecision, decision_id)
        if decision is None:
            raise ValueError(f"PolicyDecision not found: {decision_id}")

        if decision.decision_status != PolicyDecisionStatus.APPROVED:
            raise ValueError(
                f"Cannot create workflow from non-approved decision: status={decision.decision_status}"
            )

        case = self.session.get(RecoveryCase, decision.case_id)
        if case is None:
            raise ValueError(f"RecoveryCase not found: {decision.case_id}")

        if case.state != RecoveryCaseState.ACTION_PENDING:
            raise ValueError(
                f"Cannot create workflow for case in non-actionable state: state={case.state}"
            )

        # Check for existing active workflow
        existing_active = self.workflow_repo.find_active_by_case(case.id)
        if existing_active is not None:
            raise ValueError(
                f"Active workflow already exists for case {case.id}: workflow_id={existing_active.id}"
            )

        now = utc_now()
        expires_at = now + timedelta(hours=max_workflow_hours)

        # Determine strategy name from proposed action
        strategy_name = decision.proposed_action.value.upper()

        workflow = RecoveryWorkflow(
            id=uuid4(),
            case_id=case.id,
            policy_decision_id=decision.id,
            status=WorkflowStatus.PENDING,
            strategy=strategy_name,
            current_step_index=0,
            max_steps=10,
            scheduled_for=now,
            expires_at=expires_at,
            metadata_json={
                "policy_version": decision.policy_version,
                "proposed_action": decision.proposed_action.value,
            },
        )
        self.workflow_repo.save(workflow)
        self.session.flush()

        # Build bounded execution steps based on action
        steps = self._build_steps(workflow, decision.proposed_action, cooldown_hours)
        for step in steps:
            self.step_repo.save(step)

        self.session.flush()
        return workflow

    def _build_steps(
        self,
        workflow: RecoveryWorkflow,
        action: ActionType,
        cooldown_hours: int,
    ) -> list[WorkflowStep]:
        """Construct the bounded sequence of steps for a given authorized action."""
        steps: list[WorkflowStep] = []

        if action == ActionType.RETRY_PAYMENT:
            # Step 1: Pre-execution validation
            steps.append(
                WorkflowStep(
                    id=uuid4(),
                    workflow_id=workflow.id,
                    step_index=1,
                    step_type=WorkflowStepType.VALIDATE_AUTHORIZATION,
                    status=WorkflowStepStatus.PENDING,
                    idempotency_key=f"step:{workflow.id}:1:validate",
                    action_type=action,
                    payload_json={"check": "consent_and_retry_limits"},
                    execution_result_json={},
                )
            )
            # Step 2: Cooldown check / wait
            steps.append(
                WorkflowStep(
                    id=uuid4(),
                    workflow_id=workflow.id,
                    step_index=2,
                    step_type=WorkflowStepType.WAIT_COOLDOWN,
                    status=WorkflowStepStatus.PENDING,
                    idempotency_key=f"step:{workflow.id}:2:cooldown",
                    action_type=action,
                    payload_json={"cooldown_hours": cooldown_hours},
                    execution_result_json={},
                )
            )
            # Step 3: Dispatch payment retry to provider adapter
            steps.append(
                WorkflowStep(
                    id=uuid4(),
                    workflow_id=workflow.id,
                    step_index=3,
                    step_type=WorkflowStepType.DISPATCH_PAYMENT_RETRY,
                    status=WorkflowStepStatus.PENDING,
                    idempotency_key=f"step:{workflow.id}:3:dispatch",
                    action_type=action,
                    payload_json={"adapter": "razorpay_sandbox"},
                    execution_result_json={},
                )
            )
            # Step 4: Await verification
            steps.append(
                WorkflowStep(
                    id=uuid4(),
                    workflow_id=workflow.id,
                    step_index=4,
                    step_type=WorkflowStepType.AWAIT_VERIFICATION,
                    status=WorkflowStepStatus.PENDING,
                    idempotency_key=f"step:{workflow.id}:4:await_verify",
                    action_type=action,
                    payload_json={"verification_window_hours": 72},
                    execution_result_json={},
                )
            )

        elif action == ActionType.SEND_REMINDER:
            steps.append(
                WorkflowStep(
                    id=uuid4(),
                    workflow_id=workflow.id,
                    step_index=1,
                    step_type=WorkflowStepType.VALIDATE_AUTHORIZATION,
                    status=WorkflowStepStatus.PENDING,
                    idempotency_key=f"step:{workflow.id}:1:validate_comm",
                    action_type=action,
                    payload_json={"check": "communication_consent"},
                    execution_result_json={},
                )
            )
            steps.append(
                WorkflowStep(
                    id=uuid4(),
                    workflow_id=workflow.id,
                    step_index=2,
                    step_type=WorkflowStepType.DISPATCH_COMMUNICATION,
                    status=WorkflowStepStatus.PENDING,
                    idempotency_key=f"step:{workflow.id}:2:dispatch_comm",
                    action_type=action,
                    payload_json={"channel": "email"},
                    execution_result_json={},
                )
            )

        elif action == ActionType.REQUEST_OPERATOR_REVIEW:
            steps.append(
                WorkflowStep(
                    id=uuid4(),
                    workflow_id=workflow.id,
                    step_index=1,
                    step_type=WorkflowStepType.CREATE_SUPPORT_TASK,
                    status=WorkflowStepStatus.PENDING,
                    idempotency_key=f"step:{workflow.id}:1:support_task",
                    action_type=action,
                    payload_json={"target_queue": "human_operator_review"},
                    execution_result_json={},
                )
            )

        return steps
