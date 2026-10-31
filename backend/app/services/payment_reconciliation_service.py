"""Payment Status Reconciliation Service.

Author: Karthikeya
Architectural layer: domain service / financial reconciliation.

Compares internal transactions, recovery executions, and webhook receipts against
authoritative provider payment records to detect and resolve discrepancies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import utc_now
from app.core.enums import (
    ActorType,
    ExecutionStatus,
    ReconciliationStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.models.domain import (
    AuditEvent,
    ProviderWebhookEvent,
    RecoveryCase,
    RecoveryExecution,
    Transaction,
)
from app.repositories.audit_events import AuditEventRepository
from app.repositories.workflows import RecoveryExecutionRepository
from app.workflows.adapters.base import PaymentExecutionAdapter, PaymentStatusQuery
from app.workflows.adapters.razorpay_adapter import RazorpaySandboxPaymentAdapter
from app.workflows.vertical_recovery import CaseTransitionService

logger = logging.getLogger("revenuerescue.reconciliation")


@dataclass(frozen=True)
class ReconciliationReport:
    """Structured reconciliation audit report for a recovery case."""

    case_id: UUID
    transaction_id: UUID
    internal_status: TransactionStatus
    provider_status: ExecutionStatus
    status: ReconciliationStatus
    discrepancies: list[str]
    resolution_action: str | None
    reconciled_at: datetime = field(default_factory=utc_now)
    details: dict[str, Any] = field(default_factory=dict)


class PaymentReconciliationService:
    """Reconciles internal transaction and execution state with gateway truth."""

    def __init__(
        self,
        session: Session,
        adapter: PaymentExecutionAdapter | None = None,
    ) -> None:
        self.session = session
        self.adapter = adapter or RazorpaySandboxPaymentAdapter()
        self.execution_repo = RecoveryExecutionRepository(session)
        self.audit_repo = AuditEventRepository(session)
        self.transition_service = CaseTransitionService(session)

    def reconcile_case(
        self,
        case_id: UUID,
        *,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        auto_resolve: bool = True,
    ) -> ReconciliationReport:
        """Perform reconciliation for a single case and its trigger transaction."""
        case = self.session.get(RecoveryCase, case_id)
        if case is None:
            raise ValueError(f"RecoveryCase not found: {case_id}")

        txn = self.session.get(Transaction, case.trigger_transaction_id)
        if txn is None:
            raise ValueError(f"Transaction not found: {case.trigger_transaction_id}")

        now = utc_now()
        corr_id = correlation_id or f"recon_{case.id.hex[:10]}"
        discrepancies: list[str] = []
        resolution_action: str | None = None

        # 1. Fetch latest recovery execution for this case
        executions = self.execution_repo.find_by_case(case.id)
        latest_exec = executions[0] if executions else None

        # 2. Determine external provider reference
        provider_ref = None
        if latest_exec and latest_exec.external_reference:
            provider_ref = latest_exec.external_reference
        elif txn.external_transaction_id and not txn.external_transaction_id.startswith("tx_"):
            provider_ref = txn.external_transaction_id

        # 3. Query gateway for authoritative status
        provider_status = ExecutionStatus.UNKNOWN
        if provider_ref:
            query = PaymentStatusQuery(provider_payment_id=provider_ref, correlation_id=corr_id)
            exec_res = self.adapter.retrieve_status(query)
            provider_status = exec_res.status
        else:
            discrepancies.append("MISSING_PROVIDER_PAYMENT_REFERENCE")

        # 4. Check webhook event history for conflicting signals
        webhooks = list(
            self.session.scalars(
                select(ProviderWebhookEvent)
                .where(ProviderWebhookEvent.external_event_id.like(f"%{provider_ref or ''}%"))
                .order_by(desc(ProviderWebhookEvent.created_at))
            ).all()
        )
        if len(webhooks) > 1:
            types = {w.event_type for w in webhooks}
            if "PAYMENT_SUCCEEDED" in types and "PAYMENT_FAILED" in types:
                discrepancies.append("CONFLICTING_WEBHOOK_EVENT_HISTORY")

        # 5. Detect state discrepancies between internal and provider
        if txn.status in (TransactionStatus.FAILED, TransactionStatus.PENDING) and provider_status == ExecutionStatus.SUCCEEDED:
            discrepancies.append("INTERNAL_UNRESOLVED_PROVIDER_SUCCEEDED")
            if auto_resolve:
                # Provider reports success! Transition transaction and case
                txn.status = TransactionStatus.SUCCEEDED
                if case.state not in (RecoveryCaseState.RECOVERED, RecoveryCaseState.CLOSED):
                    # Transition case to RECOVERED or VERIFICATION_PENDING
                    if case.state == RecoveryCaseState.VERIFICATION_PENDING:
                        self.transition_service.transition(
                            case,
                            RecoveryCaseState.RECOVERED,
                            reason_code="reconciled_provider_success",
                            actor_type=ActorType.SYSTEM,
                            actor_id=actor_id,
                            correlation_id=corr_id,
                        )
                    else:
                        case.state = RecoveryCaseState.RECOVERED
                        case.closed_at = now
                resolution_action = "RESOLVED_TO_SUCCEEDED"

        elif txn.status == TransactionStatus.PENDING and provider_status == ExecutionStatus.FAILED:
            discrepancies.append("INTERNAL_PENDING_PROVIDER_FAILED")
            if auto_resolve:
                txn.status = TransactionStatus.FAILED
                if case.state == RecoveryCaseState.VERIFICATION_PENDING:
                    self.transition_service.transition(
                        case,
                        RecoveryCaseState.RETRY_ELIGIBLE,
                        reason_code="reconciled_provider_failure",
                        actor_type=ActorType.SYSTEM,
                        actor_id=actor_id,
                        correlation_id=corr_id,
                    )
                resolution_action = "RESOLVED_TO_FAILED"

        elif provider_status == ExecutionStatus.UNKNOWN:
            discrepancies.append("PROVIDER_STATUS_UNKNOWN")
            if auto_resolve and case.state not in (RecoveryCaseState.ESCALATED, RecoveryCaseState.CLOSED):
                self.transition_service.transition(
                    case,
                    RecoveryCaseState.ESCALATED,
                    reason_code="reconciliation_outcome_unknown",
                    actor_type=ActorType.SYSTEM,
                    actor_id=actor_id,
                    correlation_id=corr_id,
                )
                resolution_action = "ESCALATED_FOR_MANUAL_REVIEW"

        # 6. Determine final reconciliation classification
        if not discrepancies:
            recon_status = ReconciliationStatus.MATCHED
        elif resolution_action and "ESCALATED" in resolution_action:
            recon_status = ReconciliationStatus.ESCALATED
        elif resolution_action:
            recon_status = ReconciliationStatus.RESOLVED
        else:
            recon_status = ReconciliationStatus.DISCREPANCY_DETECTED

        # 7. Persist AuditEvent
        self.session.add(
            AuditEvent(
                case_id=case.id,
                event_type="PAYMENT_RECONCILED",
                from_state=case.state,
                to_state=case.state,
                actor_type=ActorType.SYSTEM,
                actor_id=actor_id,
                correlation_id=corr_id,
                event_time=now,
                payload_safe={
                    "reconciliation_status": recon_status.value,
                    "internal_status": txn.status.value,
                    "provider_status": provider_status.value,
                    "discrepancies": discrepancies,
                    "resolution_action": resolution_action,
                },
                sequence_number=len(case.audit_events) + 1,
            )
        )
        self.session.commit()

        return ReconciliationReport(
            case_id=case.id,
            transaction_id=txn.id,
            internal_status=txn.status,
            provider_status=provider_status,
            status=recon_status,
            discrepancies=discrepancies,
            resolution_action=resolution_action,
            reconciled_at=now,
            details={"provider_ref": provider_ref, "executions_count": len(executions)},
        )

    def reconcile_pending_cases(self, limit: int = 50) -> list[ReconciliationReport]:
        """Find cases pending verification and reconcile them with gateway state."""
        stmt = (
            select(RecoveryCase)
            .where(RecoveryCase.state == RecoveryCaseState.VERIFICATION_PENDING)
            .order_by(RecoveryCase.last_state_changed_at.asc())
            .limit(limit)
        )
        cases = list(self.session.scalars(stmt).all())
        reports: list[ReconciliationReport] = []
        for c in cases:
            report = self.reconcile_case(c.id)
            reports.append(report)
        return reports
