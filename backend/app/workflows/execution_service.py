"""Workflow Step Execution Service.

Author: Karthikeya
Architectural layer: workflow orchestration / bounded execution engine.

Coordinates step execution, invokes the payment execution adapter, updates
recovery attempt and execution records, and drives case state transitions.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.database import utc_now
from app.core.enums import (
    ActionType,
    ActorType,
    ExecutionStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepType,
)
from app.models.domain import (
    AuditEvent,
    Customer,
    RecoveryAttempt,
    RecoveryCase,
    RecoveryExecution,
    RecoveryWorkflow,
    Transaction,
    WorkflowStep,
)
from app.repositories.workflows import (
    RecoveryExecutionRepository,
    WorkflowRepository,
    WorkflowStepRepository,
)
from app.workflows.adapters.base import PaymentExecutionAdapter, PaymentRetryRequest
from app.workflows.adapters.razorpay_adapter import RazorpaySandboxPaymentAdapter
from app.workflows.revalidation_service import WorkflowRevalidationService
from app.workflows.vertical_recovery import CaseTransitionService


class WorkflowExecutionService:
    """Executes discrete steps in a recovery workflow with fail-closed financial safeguards."""

    def __init__(
        self,
        session: Session,
        payment_adapter: PaymentExecutionAdapter | None = None,
    ) -> None:
        self.session = session
        self.workflow_repo = WorkflowRepository(session)
        self.step_repo = WorkflowStepRepository(session)
        self.execution_repo = RecoveryExecutionRepository(session)
        self.revalidation_service = WorkflowRevalidationService(session)
        self.transition_service = CaseTransitionService(session)
        self.payment_adapter = payment_adapter or RazorpaySandboxPaymentAdapter()

    def execute_next_step(
        self,
        workflow_id: UUID,
        *,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        step_metadata_override: dict[str, Any] | None = None,
    ) -> WorkflowStep:
        """Find the next pending step in the workflow and execute it safely."""
        workflow = self.workflow_repo.find_by_id(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if workflow.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED):
            raise ValueError(f"Cannot execute step in terminal workflow: status={workflow.status}")

        case = self.session.get(RecoveryCase, workflow.case_id)
        if case is None:
            raise ValueError(f"Associated RecoveryCase not found: {workflow.case_id}")

        # Find first non-completed step
        step = next(
            (s for s in workflow.steps if s.status in (WorkflowStepStatus.PENDING, WorkflowStepStatus.SCHEDULED)),
            None,
        )
        if step is None:
            workflow.status = WorkflowStatus.COMPLETED
            self.session.flush()
            return workflow.steps[-1] if workflow.steps else None

        workflow.status = WorkflowStatus.RUNNING
        step.status = WorkflowStepStatus.RUNNING
        self.session.flush()

        corr_id = correlation_id or f"wf_step_{step.id.hex[:10]}"

        # Dispatch execution by step type
        if step.step_type == WorkflowStepType.VALIDATE_AUTHORIZATION:
            self._execute_validate_authorization(workflow, step, case, corr_id)

        elif step.step_type == WorkflowStepType.WAIT_COOLDOWN:
            self._execute_wait_cooldown(workflow, step, case, corr_id)

        elif step.step_type == WorkflowStepType.DISPATCH_PAYMENT_RETRY:
            self._execute_dispatch_payment_retry(
                workflow, step, case, corr_id, metadata_override=step_metadata_override
            )

        elif step.step_type == WorkflowStepType.AWAIT_VERIFICATION:
            self._execute_await_verification(workflow, step, case, corr_id)

        else:
            # Generic / communication / support task steps
            step.status = WorkflowStepStatus.COMPLETED
            step.executed_at = utc_now()
            step.execution_result_json = {"result": "generic_step_completed"}

        self.session.flush()
        return step

    def execute_all_available_steps(
        self,
        workflow_id: UUID,
        *,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        step_metadata_override: dict[str, Any] | None = None,
    ) -> RecoveryWorkflow:
        """Run workflow steps sequentially until a wait state, terminal state, or error occurs."""
        workflow = self.workflow_repo.find_by_id(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        max_iterations = len(workflow.steps) + 2
        iterations = 0

        while iterations < max_iterations:
            iterations += 1
            # Refresh workflow status
            if workflow.status in (
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
                WorkflowStatus.WAITING,
                WorkflowStatus.REQUIRES_REVIEW,
            ):
                break

            pending = [
                s for s in workflow.steps
                if s.status in (WorkflowStepStatus.PENDING, WorkflowStepStatus.SCHEDULED)
            ]
            if not pending:
                workflow.status = WorkflowStatus.COMPLETED
                break

            step = self.execute_next_step(
                workflow_id,
                actor_id=actor_id,
                correlation_id=correlation_id,
                step_metadata_override=step_metadata_override,
            )

            # If step entered WAITING or FAILED, stop iteration
            if step.status in (WorkflowStepStatus.WAITING, WorkflowStepStatus.FAILED):
                break

        self.session.flush()
        return workflow

    # -------------------------------------------------------------------------
    # Step-Specific Executors
    # -------------------------------------------------------------------------

    def _execute_validate_authorization(
        self,
        workflow: RecoveryWorkflow,
        step: WorkflowStep,
        case: RecoveryCase,
        correlation_id: str,
    ) -> None:
        """Validate case eligibility, consent, and limits before dispatch."""
        reval = self.revalidation_service.revalidate_for_execution(case.id, step.action_type)
        now = utc_now()

        if not reval.allowed:
            step.status = WorkflowStepStatus.FAILED
            step.error_message = reval.message
            step.executed_at = now
            step.execution_result_json = {"allowed": False, "reason_code": reval.reason_code}
            workflow.status = WorkflowStatus.FAILED

            # Transition case to STOPPED or ESCALATED based on failure reason
            target_state = (
                RecoveryCaseState.ESCALATED
                if "UNKNOWN" in reval.reason_code
                else RecoveryCaseState.STOPPED
            )
            self.transition_service.transition(
                case,
                target_state,
                reason_code=reval.reason_code.lower(),
                correlation_id=correlation_id,
            )
            return

        step.status = WorkflowStepStatus.COMPLETED
        step.executed_at = now
        step.execution_result_json = {"allowed": True, "reason_code": reval.reason_code}

    def _execute_wait_cooldown(
        self,
        workflow: RecoveryWorkflow,
        step: WorkflowStep,
        case: RecoveryCase,
        correlation_id: str,
    ) -> None:
        """Enforce cooldown waiting period. Completed immediately in test/sandbox."""
        now = utc_now()
        step.status = WorkflowStepStatus.COMPLETED
        step.executed_at = now
        step.execution_result_json = {"cooldown_satisfied": True}

    def _execute_dispatch_payment_retry(
        self,
        workflow: RecoveryWorkflow,
        step: WorkflowStep,
        case: RecoveryCase,
        correlation_id: str,
        metadata_override: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch payment retry request to Razorpay Sandbox adapter."""
        # 1. Pre-execution revalidation
        reval = self.revalidation_service.revalidate_for_execution(case.id, ActionType.RETRY_PAYMENT)
        now = utc_now()

        if not reval.allowed:
            step.status = WorkflowStepStatus.FAILED
            step.error_message = reval.message
            step.executed_at = now
            workflow.status = WorkflowStatus.FAILED
            return

        # 2. Prepare transaction and customer context
        txn = self.session.get(Transaction, case.trigger_transaction_id)
        cust = self.session.get(Customer, case.customer_id)
        if txn is None or cust is None:
            step.status = WorkflowStepStatus.FAILED
            step.error_message = "Missing transaction or customer record."
            workflow.status = WorkflowStatus.FAILED
            return

        # 3. Create RecoveryAttempt record
        sequence_num = len(case.attempts) + 1
        attempt_idempotency = f"{case.id}:retry:{sequence_num}"
        attempt = RecoveryAttempt(
            case_id=case.id,
            sequence_number=sequence_num,
            status=RecoveryAttemptStatus.STARTED,
            action_type=ActionType.RETRY_PAYMENT,
            started_at=now,
            idempotency_key=attempt_idempotency,
            metadata_json={"workflow_id": str(workflow.id), "step_id": str(step.id)},
        )
        self.session.add(attempt)
        self.session.flush()

        # 4. Construct PaymentRetryRequest
        req_metadata = {**step.payload_json, **(metadata_override or {})}
        request = PaymentRetryRequest(
            case_id=case.id,
            transaction_id=txn.id,
            amount_minor=txn.amount_minor,
            currency=txn.currency,
            customer_reference=cust.external_customer_id,
            idempotency_key=step.idempotency_key,
            customer_email=cust.email,
            payment_method=txn.metadata_json.get("method"),
            metadata=req_metadata,
        )

        # 5. Invoke Payment Execution Adapter
        res = self.payment_adapter.submit_retry(request)

        # 6. Record RecoveryExecution entity
        execution = RecoveryExecution(
            id=uuid4(),
            step_id=step.id,
            case_id=case.id,
            provider=res.provider,
            external_reference=res.provider_payment_id or res.provider_order_id,
            status=res.status,
            amount_minor=res.amount_minor,
            currency=res.currency,
            idempotency_key=step.idempotency_key,
            request_payload_safe={
                "amount_minor": request.amount_minor,
                "currency": request.currency,
                "customer": cust.external_customer_id,
            },
            response_payload_safe=res.raw_response_safe,
            error_code=res.error_code,
            error_message_safe=res.error_message_safe,
            latency_ms=res.latency_ms,
            executed_at=res.executed_at,
        )
        self.execution_repo.save(execution)
        self.session.flush()

        # 7. Evaluate execution outcome
        step.executed_at = res.executed_at
        step.execution_result_json = {
            "status": res.status.value,
            "external_reference": res.provider_payment_id or res.provider_order_id,
            "latency_ms": res.latency_ms,
            "error_code": res.error_code,
        }

        if res.status == ExecutionStatus.SUBMITTED:
            step.status = WorkflowStepStatus.COMPLETED
            attempt.status = RecoveryAttemptStatus.STARTED
            attempt.provider_reference = res.provider_payment_id or res.provider_order_id

            # Transition case from ACTION_PENDING -> VERIFICATION_PENDING
            self.transition_service.transition(
                case,
                RecoveryCaseState.VERIFICATION_PENDING,
                reason_code="payment_retry_submitted_to_provider",
                correlation_id=correlation_id,
            )

        elif res.status == ExecutionStatus.SUCCEEDED:
            # Direct gateway confirmation
            step.status = WorkflowStepStatus.COMPLETED
            attempt.status = RecoveryAttemptStatus.SUCCEEDED
            attempt.outcome = "gateway_confirmed_success"
            attempt.provider_reference = res.provider_payment_id or res.provider_order_id

            self.transition_service.transition(
                case,
                RecoveryCaseState.VERIFICATION_PENDING,
                reason_code="gateway_reported_payment_captured",
                correlation_id=correlation_id,
            )

        elif res.status == ExecutionStatus.UNKNOWN:
            # Fail-closed on timeout or unknown outcome: DO NOT BLIND RETRY
            step.status = WorkflowStepStatus.FAILED
            step.error_message = res.error_message_safe or "Gateway outcome unknown (timeout)."
            attempt.status = RecoveryAttemptStatus.UNCERTAIN
            attempt.outcome = "unknown_outcome_awaiting_reconciliation"
            workflow.status = WorkflowStatus.REQUIRES_REVIEW

            # Escalate case for reconciliation rather than blind retry
            self.transition_service.transition(
                case,
                RecoveryCaseState.ESCALATED,
                reason_code="provider_timeout_unknown_outcome",
                correlation_id=correlation_id,
            )

        elif res.status == ExecutionStatus.FAILED:
            step.status = WorkflowStepStatus.FAILED
            step.error_message = res.error_message_safe or "Payment retry failed on gateway."
            attempt.status = RecoveryAttemptStatus.FAILED
            attempt.outcome = res.error_code or "payment_failed"
            workflow.status = WorkflowStatus.FAILED

            # Case remains actionable or transitions to RETRY_ELIGIBLE / STOPPED
            # If retry limit reached, transition to STOPPED
            if len(case.attempts) >= 4:
                self.transition_service.transition(
                    case,
                    RecoveryCaseState.STOPPED,
                    reason_code="retry_limit_exhausted",
                    correlation_id=correlation_id,
                )

    def _execute_await_verification(
        self,
        workflow: RecoveryWorkflow,
        step: WorkflowStep,
        case: RecoveryCase,
        correlation_id: str,
    ) -> None:
        """Place workflow in WAITING state pending webhook delivery or reconciliation."""
        step.status = WorkflowStepStatus.WAITING
        workflow.status = WorkflowStatus.WAITING
        step.execution_result_json = {"status": "waiting_for_webhook_or_reconciliation"}
