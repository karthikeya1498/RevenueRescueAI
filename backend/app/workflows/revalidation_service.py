"""Workflow Pre-Execution Revalidation Service.

Author: Karthikeya
Architectural layer: workflow guardrails / pre-dispatch gatekeeper.

Enforces fail-closed validation immediately before financial or communication dispatches:
- Consent is still actively GRANTED and not expired/revoked.
- Transaction has not already succeeded through an alternate channel.
- Retry attempt limits are strictly respected.
- Prior executions do not have an unresolved UNKNOWN timeout outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utc_now
from app.core.enums import (
    ActionType,
    ConsentStatus,
    ConsentType,
    ExecutionStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.models.domain import CustomerConsent, RecoveryCase, RecoveryExecution, Transaction


@dataclass(frozen=True)
class RevalidationResult:
    """Outcome of pre-execution guardrail check."""

    allowed: bool
    reason_code: str
    message: str


class WorkflowRevalidationService:
    """Pre-execution guardrail service enforcing runtime financial safety."""

    def __init__(self, session: Session, max_retry_attempts: int = 4) -> None:
        self.session = session
        self.max_retry_attempts = max_retry_attempts

    def revalidate_for_execution(
        self,
        case_id: UUID,
        action_type: ActionType,
    ) -> RevalidationResult:
        """Run fail-closed validation checks immediately before executing an action."""
        case = self.session.get(RecoveryCase, case_id)
        if case is None:
            return RevalidationResult(False, "CASE_NOT_FOUND", "RecoveryCase does not exist.")

        # 1. State must be actionable
        if case.state != RecoveryCaseState.ACTION_PENDING:
            return RevalidationResult(
                False,
                "CASE_NOT_ACTION_PENDING",
                f"Case state '{case.state}' is not actionable.",
            )

        # 2. Trigger transaction must not have already succeeded
        txn = self.session.get(Transaction, case.trigger_transaction_id)
        if txn and txn.status == TransactionStatus.SUCCEEDED:
            return RevalidationResult(
                False,
                "PAYMENT_ALREADY_SUCCEEDED",
                "Transaction has already succeeded; recovery retry aborted.",
            )

        # 3. Check for unresolved UNKNOWN executions for this case
        unknown_exec = self.session.scalar(
            select(RecoveryExecution)
            .where(
                RecoveryExecution.case_id == case.id,
                RecoveryExecution.status == ExecutionStatus.UNKNOWN,
            )
            .limit(1)
        )
        if unknown_exec is not None:
            return RevalidationResult(
                False,
                "UNRESOLVED_UNKNOWN_OUTCOME",
                f"Prior execution {unknown_exec.id} is in UNKNOWN status. Reconciliation required before retrying.",
            )

        # 4. Action-specific validation
        if action_type == ActionType.RETRY_PAYMENT:
            # Check retry attempt limits
            attempt_count = len(case.attempts)
            if attempt_count >= self.max_retry_attempts:
                return RevalidationResult(
                    False,
                    "RETRY_LIMIT_EXCEEDED",
                    f"Retry attempt count ({attempt_count}) has reached maximum ({self.max_retry_attempts}).",
                )

            # Check recurring billing customer consent
            now = utc_now()
            consent_stmt = select(CustomerConsent).where(
                CustomerConsent.customer_id == case.customer_id,
                CustomerConsent.consent_type == ConsentType.RECURRING_BILLING,
                CustomerConsent.status == ConsentStatus.GRANTED,
            )
            consent = self.session.scalar(consent_stmt)
            if consent is None:
                return RevalidationResult(
                    False,
                    "MISSING_RECURRING_CONSENT",
                    "No active RECURRING_BILLING consent found for customer.",
                )

            if consent.expires_at and consent.expires_at < now:
                return RevalidationResult(
                    False,
                    "CONSENT_EXPIRED",
                    f"Customer recurring billing consent expired at {consent.expires_at.isoformat()}.",
                )

            if consent.revoked_at is not None:
                return RevalidationResult(
                    False,
                    "CONSENT_REVOKED",
                    "Customer recurring billing consent was revoked.",
                )

        elif action_type == ActionType.SEND_REMINDER:
            # Check communication consent
            comm_stmt = select(CustomerConsent).where(
                CustomerConsent.customer_id == case.customer_id,
                CustomerConsent.consent_type.in_(
                    [ConsentType.COMMUNICATION_EMAIL, ConsentType.COMMUNICATION_SMS]
                ),
                CustomerConsent.status == ConsentStatus.GRANTED,
            )
            comm_consent = self.session.scalar(comm_stmt)
            if comm_consent is None:
                return RevalidationResult(
                    False,
                    "MISSING_COMMUNICATION_CONSENT",
                    "No active communication consent found for customer.",
                )

        return RevalidationResult(True, "VALIDATION_PASSED", "All pre-execution guardrails passed.")
