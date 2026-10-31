"""Comprehensive tests for Workflow Orchestration, Bounded Execution, and Pre-Execution Revalidation.

Author: Karthikeya
Architectural layer: tests / recovery workflow engine.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, utc_now
from app.core.enums import (
    ActionType,
    ActorType,
    ConsentStatus,
    ConsentType,
    CustomerStatus,
    DecisionValidationStatus,
    ExecutionStatus,
    PolicyDecisionStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    TransactionStatus,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepType,
)
from app.models.domain import (
    AgentDecision,
    Customer,
    CustomerConsent,
    PolicyDecision,
    RecoveryAttempt,
    RecoveryCase,
    RecoveryExecution,
    RecoveryWorkflow,
    Transaction,
    WorkflowStep,
)
from app.workflows.adapters.base import ExecutionResult
from app.workflows.adapters.razorpay_adapter import RazorpaySandboxPaymentAdapter
from app.workflows.creation_service import WorkflowCreationService
from app.workflows.execution_service import WorkflowExecutionService
from app.workflows.revalidation_service import WorkflowRevalidationService


@pytest.fixture
def db():
    """In-memory SQLite session with foreign key integrity enabled."""
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(conn, _rec):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def seed_test_context(db, *, consent_granted: bool = True, case_state: RecoveryCaseState = RecoveryCaseState.ACTION_PENDING):
    """Seed baseline customer, transaction, consent, case, decision, and policy decision."""
    now = utc_now()
    customer = Customer(
        id=uuid4(),
        provider="razorpay",
        external_customer_id=f"cust_{uuid4().hex[:8]}",
        email="test_user@example.com",
        display_name="Test Customer",
        status=CustomerStatus.ACTIVE,
    )
    db.add(customer)
    db.flush()

    if consent_granted:
        consent = CustomerConsent(
            id=uuid4(),
            customer_id=customer.id,
            consent_type=ConsentType.RECURRING_BILLING,
            status=ConsentStatus.GRANTED,
            merchant_id="merchant_123",
            granted_at=now - timedelta(days=1),
            source="checkout_agreement",
            version=1,
        )
        db.add(consent)
        db.flush()

    txn = Transaction(
        id=uuid4(),
        customer_id=customer.id,
        provider="razorpay",
        external_transaction_id=f"txn_{uuid4().hex[:10]}",
        amount_minor=250000,  # ₹2,500.00
        currency="INR",
        status=TransactionStatus.FAILED,
        occurred_at=now,
    )
    db.add(txn)
    db.flush()

    case = RecoveryCase(
        id=uuid4(),
        customer_id=customer.id,
        trigger_transaction_id=txn.id,
        case_key=f"case_{uuid4().hex[:12]}",
        state=case_state,
        priority=100,
        opened_at=now,
        last_state_changed_at=now,
        version=1,
        metadata_json={},
    )
    db.add(case)
    db.flush()

    rec = AgentDecision(
        id=uuid4(),
        case_id=case.id,
        decision_version=1,
        action_type=ActionType.RETRY_PAYMENT,
        reason_code="SOFT_DECLINE_RETRY_ELIGIBLE",
        rationale_safe="AI recommends retry later",
        validation_status=DecisionValidationStatus.VALID,
    )
    db.add(rec)
    db.flush()

    policy_dec = PolicyDecision(
        id=uuid4(),
        case_id=case.id,
        recommendation_id=rec.id,
        proposed_action=ActionType.RETRY_PAYMENT,
        decision_status=PolicyDecisionStatus.APPROVED,
        policy_version="1.0.0",
        rule_results_json=[],
        reasons_json=["All safety checks passed"],
        actor_type=ActorType.SYSTEM,
        case_version=1,
        evaluated_at=now,
    )
    db.add(policy_dec)
    db.flush()

    return customer, txn, case, rec, policy_dec


def test_workflow_creation_success(db):
    """Workflow creation builds 4 sequential bounded steps for RETRY_PAYMENT."""
    _, _, case, _, policy_dec = seed_test_context(db)
    service = WorkflowCreationService(db)

    workflow = service.create_workflow_for_decision(policy_dec.id)

    assert workflow.status == WorkflowStatus.PENDING
    assert workflow.case_id == case.id
    assert workflow.strategy == "RETRY_PAYMENT"
    assert len(workflow.steps) == 4

    step_types = [s.step_type for s in workflow.steps]
    assert step_types == [
        WorkflowStepType.VALIDATE_AUTHORIZATION,
        WorkflowStepType.WAIT_COOLDOWN,
        WorkflowStepType.DISPATCH_PAYMENT_RETRY,
        WorkflowStepType.AWAIT_VERIFICATION,
    ]


def test_workflow_creation_rejects_non_approved_decision(db):
    """Workflow creation fails closed if policy decision is REJECTED."""
    _, _, _, _, policy_dec = seed_test_context(db)
    policy_dec.decision_status = PolicyDecisionStatus.REJECTED
    db.flush()

    service = WorkflowCreationService(db)
    with pytest.raises(ValueError, match="non-approved decision"):
        service.create_workflow_for_decision(policy_dec.id)


def test_workflow_revalidation_blocks_missing_consent(db):
    """Revalidation fails closed if customer consent is missing."""
    _, _, case, _, _ = seed_test_context(db, consent_granted=False)
    service = WorkflowRevalidationService(db)

    result = service.revalidate_for_execution(case.id, ActionType.RETRY_PAYMENT)

    assert result.allowed is False
    assert result.reason_code == "MISSING_RECURRING_CONSENT"


def test_workflow_revalidation_blocks_retry_limit_exceeded(db):
    """Revalidation fails closed if attempt count reaches maximum limit."""
    _, _, case, _, _ = seed_test_context(db, consent_granted=True)
    # Add 4 dummy attempts
    for i in range(1, 5):
        db.add(
            RecoveryAttempt(
                id=uuid4(),
                case_id=case.id,
                sequence_number=i,
                status=RecoveryAttemptStatus.FAILED,
                action_type=ActionType.RETRY_PAYMENT,
                idempotency_key=f"att_{case.id}_{i}",
                metadata_json={},
            )
        )
    db.flush()

    service = WorkflowRevalidationService(db, max_retry_attempts=4)
    result = service.revalidate_for_execution(case.id, ActionType.RETRY_PAYMENT)

    assert result.allowed is False
    assert result.reason_code == "RETRY_LIMIT_EXCEEDED"


def test_workflow_revalidation_blocks_when_payment_already_succeeded(db):
    """Revalidation fails closed if transaction has already succeeded."""
    _, txn, case, _, _ = seed_test_context(db, consent_granted=True)
    txn.status = TransactionStatus.SUCCEEDED
    db.flush()

    service = WorkflowRevalidationService(db)
    result = service.revalidate_for_execution(case.id, ActionType.RETRY_PAYMENT)

    assert result.allowed is False
    assert result.reason_code == "PAYMENT_ALREADY_SUCCEEDED"


def test_workflow_execution_submitted_flow(db):
    """Executing retry step dispatches to adapter and transitions case to VERIFICATION_PENDING."""
    _, _, case, _, policy_dec = seed_test_context(db, consent_granted=True)
    creation_service = WorkflowCreationService(db)
    workflow = creation_service.create_workflow_for_decision(policy_dec.id)

    adapter = RazorpaySandboxPaymentAdapter(simulate_scenarios=True)
    exec_service = WorkflowExecutionService(db, payment_adapter=adapter)

    # Run all steps through to payment dispatch
    updated_wf = exec_service.execute_all_available_steps(workflow.id)

    # Case must transition from ACTION_PENDING -> VERIFICATION_PENDING
    assert case.state == RecoveryCaseState.VERIFICATION_PENDING

    # Step 1, 2, 3 must be COMPLETED, Step 4 in WAITING
    step_statuses = [s.status for s in updated_wf.steps]
    assert step_statuses[0] == WorkflowStepStatus.COMPLETED  # Validate
    assert step_statuses[1] == WorkflowStepStatus.COMPLETED  # Cooldown
    assert step_statuses[2] == WorkflowStepStatus.COMPLETED  # Dispatch
    assert step_statuses[3] == WorkflowStepStatus.WAITING    # Await verification

    # Check recovery execution record
    step3 = updated_wf.steps[2]
    assert len(step3.executions) == 1
    exec_rec = step3.executions[0]
    assert exec_rec.status == ExecutionStatus.SUBMITTED
    assert exec_rec.amount_minor == 250000
    assert exec_rec.currency == "INR"
    assert exec_rec.provider == "razorpay"


def test_workflow_execution_timeout_escalates_without_blind_retry(db):
    """Simulated timeout outcome marks step failed, escalates case, and NEVER blind retries."""
    _, _, case, _, policy_dec = seed_test_context(db, consent_granted=True)
    creation_service = WorkflowCreationService(db)
    workflow = creation_service.create_workflow_for_decision(policy_dec.id)

    adapter = RazorpaySandboxPaymentAdapter(simulate_scenarios=True)
    exec_service = WorkflowExecutionService(db, payment_adapter=adapter)

    # Force step 3 to simulate timeout
    updated_wf = exec_service.execute_all_available_steps(
        workflow.id,
        step_metadata_override={"sandbox_scenario": "TIMEOUT"},
    )

    # Step 3 must be FAILED, workflow REQUIRES_REVIEW
    step3 = updated_wf.steps[2]
    assert step3.status == WorkflowStepStatus.FAILED
    assert "timed out" in step3.error_message.lower()
    assert updated_wf.status == WorkflowStatus.REQUIRES_REVIEW

    # Case must be ESCALATED for reconciliation rather than retried
    assert case.state == RecoveryCaseState.ESCALATED

    # Verify that RevalidationService now refuses to allow any new retry attempts
    reval = WorkflowRevalidationService(db)
    check = reval.revalidate_for_execution(case.id, ActionType.RETRY_PAYMENT)
    assert check.allowed is False
    assert check.reason_code == "CASE_NOT_ACTION_PENDING" or check.reason_code == "UNRESOLVED_UNKNOWN_OUTCOME"
