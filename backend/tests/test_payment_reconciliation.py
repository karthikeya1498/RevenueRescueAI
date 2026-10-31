"""Tests for Payment Status Reconciliation Service.

Author: Karthikeya
Architectural layer: tests / payment status reconciliation.
"""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, utc_now
from app.core.enums import (
    CustomerStatus,
    ExecutionStatus,
    ReconciliationStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.models.domain import (
    AuditEvent,
    Customer,
    RecoveryCase,
    RecoveryExecution,
    RecoveryWorkflow,
    Transaction,
    WorkflowStep,
)
from app.services.payment_reconciliation_service import PaymentReconciliationService
from app.workflows.adapters.base import ExecutionResult, PaymentExecutionAdapter, PaymentRetryRequest, PaymentStatusQuery


class MockReconciliationAdapter(PaymentExecutionAdapter):
    """Controlled mock adapter to simulate specific gateway states for reconciliation."""

    def __init__(self, target_status: ExecutionStatus) -> None:
        self.target_status = target_status

    def submit_retry(self, request: PaymentRetryRequest) -> ExecutionResult:
        return ExecutionResult(
            status=self.target_status,
            provider="razorpay",
            provider_payment_id="pay_recon_123",
            provider_order_id="order_recon_123",
            amount_minor=request.amount_minor,
            currency=request.currency,
            error_code=None,
            error_message_safe=None,
            raw_response_safe={},
            latency_ms=10,
        )

    def retrieve_status(self, query: PaymentStatusQuery) -> ExecutionResult:
        return ExecutionResult(
            status=self.target_status,
            provider="razorpay",
            provider_payment_id=query.provider_payment_id,
            provider_order_id="order_recon_123",
            amount_minor=250000,
            currency="INR",
            error_code=None if self.target_status != ExecutionStatus.FAILED else "PAYMENT_FAILED",
            error_message_safe=None,
            raw_response_safe={},
            latency_ms=10,
        )


@pytest.fixture
def db():
    """In-memory SQLite session with foreign key integrity."""
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


def seed_reconciliation_case(db, *, txn_status=TransactionStatus.FAILED, case_state=RecoveryCaseState.VERIFICATION_PENDING):
    now = utc_now()
    cust = Customer(
        id=uuid4(),
        provider="razorpay",
        external_customer_id=f"cust_{uuid4().hex[:8]}",
        email="recon@example.com",
        status=CustomerStatus.ACTIVE,
    )
    db.add(cust)
    db.flush()

    payment_ref = f"pay_{uuid4().hex[:10]}"
    txn = Transaction(
        id=uuid4(),
        customer_id=cust.id,
        provider="razorpay",
        external_transaction_id=payment_ref,
        amount_minor=250000,
        currency="INR",
        status=txn_status,
        occurred_at=now,
    )
    db.add(txn)
    db.flush()

    case = RecoveryCase(
        id=uuid4(),
        customer_id=cust.id,
        trigger_transaction_id=txn.id,
        case_key=f"case_{payment_ref}",
        state=case_state,
        priority=100,
        opened_at=now,
        last_state_changed_at=now,
        version=1,
    )
    db.add(case)
    db.flush()

    return cust, txn, case, payment_ref


def test_reconciliation_detects_and_resolves_provider_success(db):
    """Internal says FAILED / VERIFICATION_PENDING, but gateway says SUCCEEDED."""
    _, txn, case, _ = seed_reconciliation_case(
        db, txn_status=TransactionStatus.FAILED, case_state=RecoveryCaseState.VERIFICATION_PENDING
    )
    adapter = MockReconciliationAdapter(target_status=ExecutionStatus.SUCCEEDED)
    service = PaymentReconciliationService(db, adapter=adapter)

    report = service.reconcile_case(case.id, auto_resolve=True)

    assert report.status == ReconciliationStatus.RESOLVED
    assert "INTERNAL_UNRESOLVED_PROVIDER_SUCCEEDED" in report.discrepancies
    assert report.resolution_action == "RESOLVED_TO_SUCCEEDED"

    # Verify state was synchronized
    db.refresh(txn)
    db.refresh(case)
    assert txn.status == TransactionStatus.SUCCEEDED
    assert case.state == RecoveryCaseState.RECOVERED


def test_reconciliation_detects_and_resolves_provider_failure(db):
    """Internal says PENDING / VERIFICATION_PENDING, but gateway says FAILED."""
    _, txn, case, _ = seed_reconciliation_case(
        db, txn_status=TransactionStatus.PENDING, case_state=RecoveryCaseState.VERIFICATION_PENDING
    )
    adapter = MockReconciliationAdapter(target_status=ExecutionStatus.FAILED)
    service = PaymentReconciliationService(db, adapter=adapter)

    report = service.reconcile_case(case.id, auto_resolve=True)

    assert report.status == ReconciliationStatus.RESOLVED
    assert "INTERNAL_PENDING_PROVIDER_FAILED" in report.discrepancies
    assert report.resolution_action == "RESOLVED_TO_FAILED"

    db.refresh(txn)
    db.refresh(case)
    assert txn.status == TransactionStatus.FAILED
    assert case.state == RecoveryCaseState.RETRY_ELIGIBLE


def test_reconciliation_unknown_provider_status_escalates_case(db):
    """Gateway timeout / unknown status causes case to be escalated for manual investigation."""
    _, txn, case, _ = seed_reconciliation_case(
        db, txn_status=TransactionStatus.PENDING, case_state=RecoveryCaseState.VERIFICATION_PENDING
    )
    adapter = MockReconciliationAdapter(target_status=ExecutionStatus.UNKNOWN)
    service = PaymentReconciliationService(db, adapter=adapter)

    report = service.reconcile_case(case.id, auto_resolve=True)

    assert report.status == ReconciliationStatus.ESCALATED
    assert "PROVIDER_STATUS_UNKNOWN" in report.discrepancies

    db.refresh(case)
    assert case.state == RecoveryCaseState.ESCALATED


def test_reconciliation_emits_audit_trail(db):
    """Reconciliation emits a structured audit record."""
    _, _, case, _ = seed_reconciliation_case(
        db, txn_status=TransactionStatus.FAILED, case_state=RecoveryCaseState.VERIFICATION_PENDING
    )
    adapter = MockReconciliationAdapter(target_status=ExecutionStatus.SUCCEEDED)
    service = PaymentReconciliationService(db, adapter=adapter)

    service.reconcile_case(case.id, auto_resolve=True)

    audits = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.case_id == case.id, AuditEvent.event_type == "PAYMENT_RECONCILED"
            )
        ).all()
    )
    assert len(audits) >= 1
    audit = audits[-1]
    assert audit.payload_safe["reconciliation_status"] == ReconciliationStatus.RESOLVED.value
    assert "INTERNAL_UNRESOLVED_PROVIDER_SUCCEEDED" in audit.payload_safe["discrepancies"]
