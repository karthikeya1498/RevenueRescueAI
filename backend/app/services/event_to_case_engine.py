"""Automatic case creation and matching engine for RevenueRescueAI.

Author: Karthikeya
Architectural layer: domain engine / application orchestration.

Transforms validated revenue-risk events into structured, trackable recovery cases:
1. Validates event eligibility for case creation or resolution.
2. Resolves or provisions Customer and Transaction entities safely.
3. Computes deterministic Case Identity Key for matching and deduplication.
4. Matches existing active cases or creates a new RecoveryCase in DETECTED state.
5. Calculates deterministic operational Priority (CasePrioritizer).
6. Evaluates independent Risk Tier (CaseRiskClassifier).
7. Records initial CaseStateTransition and immutable AuditEvent history.
8. Handles payment success resolutions and concurrent idempotency conflicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import utc_now
from app.core.enums import (
    ActorType,
    CanonicalEventType,
    CustomerStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.models.domain import (
    CaseStateTransition,
    Customer,
    ProviderWebhookEvent,
    RecoveryCase,
    Transaction,
)
from app.repositories.audit_events import AuditEventRepository
from app.repositories.customers import CustomerRepository
from app.repositories.recovery_cases import RecoveryCaseRepository
from app.repositories.transactions import TransactionRepository
from app.schemas.events import CanonicalEventDTO
from app.services.case_prioritizer import CasePrioritizer
from app.services.case_risk_classifier import CaseRiskClassifier

logger = logging.getLogger("revenuerescue.engine")

# States where a recovery case is considered resolved or stopped
TERMINAL_STATES = {
    RecoveryCaseState.RECOVERED,
    RecoveryCaseState.STOPPED,
    RecoveryCaseState.CLOSED,
}

# Events that represent genuine revenue risk and are eligible to create/update recovery cases
CASE_CREATION_ELIGIBLE_EVENTS = {
    CanonicalEventType.PAYMENT_FAILED.value,
    CanonicalEventType.SUBSCRIPTION_PAYMENT_FAILED.value,
    CanonicalEventType.CHECKOUT_ABANDONED.value,
    CanonicalEventType.INVOICE_OVERDUE.value,
}

# Events that resolve an active recovery case
CASE_RESOLUTION_EVENTS = {
    CanonicalEventType.PAYMENT_SUCCEEDED.value,
}


@dataclass(frozen=True)
class CaseProcessingOutcome:
    """Detailed result of processing an ingested event through the case engine."""

    outcome: str  # CASE_CREATED, CASE_UPDATED, CASE_RESOLVED, IGNORED, CONFLICT
    case_id: UUID | None = None
    case_key: str | None = None
    state: RecoveryCaseState | None = None
    priority: int | None = None
    risk_tier: str | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class EventToCaseEngine:
    """Core engine converting canonical revenue-risk events into recovery cases."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.case_repo = RecoveryCaseRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.transaction_repo = TransactionRepository(session)
        self.audit_repo = AuditEventRepository(session)

    @staticmethod
    def derive_case_key(event: CanonicalEventDTO) -> str:
        """Derive a deterministic business case key from event attributes.
        
        Guarantees that multiple events for the same subscription period, invoice,
        or checkout session map to the same conceptual business case.
        """
        if event.subscription_reference:
            billing_period = event.metadata.get("billing_period") or event.occurred_at.strftime("%Y%m")
            return f"CASE-SUB-{event.subscription_reference}-{billing_period}"
        elif event.invoice_reference:
            return f"CASE-INV-{event.invoice_reference}"
        elif event.checkout_session_id:
            return f"CASE-CHK-{event.checkout_session_id}"
        elif event.payment_reference:
            return f"CASE-TX-{event.provider}-{event.payment_reference}"
        else:
            return f"CASE-EVT-{event.provider}-{event.external_event_id}"

    def process_event(
        self,
        event: CanonicalEventDTO,
        raw_event_record: ProviderWebhookEvent | None = None,
        correlation_id: str | None = None,
    ) -> CaseProcessingOutcome:
        """Process an ingested event into case creation, update, or resolution."""
        corr_id = correlation_id or f"corr_{uuid4().hex[:12]}"
        event_type = event.event_type.strip().upper()

        # 1. Eligibility Check
        is_creation_eligible = event_type in CASE_CREATION_ELIGIBLE_EVENTS
        is_resolution_eligible = event_type in CASE_RESOLUTION_EVENTS

        if not (is_creation_eligible or is_resolution_eligible):
            logger.info("Event %s (type=%s) ignored for case creation.", event.external_event_id, event.event_type)
            return CaseProcessingOutcome(
                outcome="IGNORED",
                reason=f"Event type '{event.event_type}' does not trigger case management actions.",
            )

        # 2. Provision or resolve Customer
        customer = self._get_or_create_customer(event)

        # 3. Provision or resolve Trigger Transaction
        tx = self._get_or_create_transaction(event, customer)

        # 4. Derive Canonical Case Key
        case_key = self.derive_case_key(event)

        # 5. Existing Case Matching Lookup
        existing_case = self.case_repo.find_by_case_key(case_key)
        if existing_case is None and tx.id is not None:
            existing_case = self.case_repo.find_by_trigger_transaction_id(tx.id)

        # 6. Branch: Handle Payment Succeeded (Case Resolution)
        if is_resolution_eligible:
            return self._handle_payment_succeeded(
                event=event,
                existing_case=existing_case,
                tx=tx,
                correlation_id=corr_id,
            )

        # 7. Branch: Handle Revenue-Risk Failure (Creation or Update)
        if existing_case is not None:
            return self._handle_existing_case_update(
                event=event,
                case=existing_case,
                correlation_id=corr_id,
            )

        # 8. Create New Recovery Case
        return self._create_new_case(
            event=event,
            customer=customer,
            tx=tx,
            case_key=case_key,
            correlation_id=corr_id,
        )

    def _get_or_create_customer(self, event: CanonicalEventDTO) -> Customer:
        """Ensure a Customer aggregate exists for the event."""
        customer = self.customer_repo.find_by_external_id(event.provider, event.customer_reference)
        if customer is None:
            email = event.metadata.get("customer_email") or event.metadata.get("email")
            name = event.metadata.get("customer_name") or f"Customer {event.customer_reference}"
            customer = Customer(
                id=uuid4(),
                provider=event.provider,
                external_customer_id=event.customer_reference,
                email=str(email) if email else None,
                display_name=str(name) if name else None,
                status=CustomerStatus.ACTIVE,
                metadata_json=dict(event.metadata),
            )
            self.customer_repo.save(customer)
            self.session.flush()
        return customer

    def _get_or_create_transaction(self, event: CanonicalEventDTO, customer: Customer) -> Transaction:
        """Ensure a Transaction aggregate exists for the event."""
        tx_ref = (
            event.payment_reference
            or event.invoice_reference
            or event.checkout_session_id
            or f"tx_{event.external_event_id}"
        )
        tx = self.transaction_repo.find_by_external_id(event.provider, tx_ref)
        if tx is None:
            is_succeeded = event.event_type.strip().upper() in CASE_RESOLUTION_EVENTS
            status = TransactionStatus.SUCCEEDED if is_succeeded else TransactionStatus.FAILED
            tx = Transaction(
                id=uuid4(),
                customer_id=customer.id,
                provider=event.provider,
                external_transaction_id=tx_ref,
                amount_minor=event.amount_minor,
                currency=event.currency,
                status=status,
                failure_code=event.failure_code,
                failure_message_safe=event.failure_message,
                occurred_at=event.occurred_at,
                metadata_json=dict(event.metadata),
            )
            self.transaction_repo.save(tx)
            self.session.flush()
        return tx

    def _handle_payment_succeeded(
        self,
        event: CanonicalEventDTO,
        existing_case: RecoveryCase | None,
        tx: Transaction,
        correlation_id: str,
    ) -> CaseProcessingOutcome:
        """Resolve an active recovery case upon verified payment success."""
        if existing_case is None:
            logger.info("Payment succeeded event %s has no active recovery case to resolve.", event.external_event_id)
            return CaseProcessingOutcome(
                outcome="IGNORED",
                reason="No active recovery case matching succeeded payment reference.",
            )

        if existing_case.state in TERMINAL_STATES:
            logger.info("Case %s is already in terminal state %s; ignoring success.", existing_case.case_key, existing_case.state)
            return CaseProcessingOutcome(
                outcome="IGNORED",
                case_id=existing_case.id,
                case_key=existing_case.case_key,
                state=existing_case.state,
                reason=f"Recovery case is already terminal ({existing_case.state.value}).",
            )

        # Transition active case to RECOVERED
        from_state = existing_case.state
        now = utc_now()
        existing_case.state = RecoveryCaseState.RECOVERED
        existing_case.last_state_changed_at = now
        existing_case.closed_at = now
        existing_case.version += 1

        # Mark trigger transaction as SUCCEEDED
        tx.status = TransactionStatus.SUCCEEDED

        # Record FSM State Transition
        trans_seq = (
            self.session.scalar(
                select(func.max(CaseStateTransition.sequence_number)).where(
                    CaseStateTransition.case_id == existing_case.id
                )
            )
            or 0
        ) + 1

        transition_record = CaseStateTransition(
            id=uuid4(),
            case_id=existing_case.id,
            from_state=from_state,
            to_state=RecoveryCaseState.RECOVERED,
            reason_code="PAYMENT_SUCCEEDED_VERIFIED",
            actor_type=ActorType.PROVIDER,
            correlation_id=correlation_id,
            occurred_at=now,
            sequence_number=trans_seq,
            metadata_json={
                "event_id": event.external_event_id,
                "provider": event.provider,
                "amount_minor": event.amount_minor,
                "currency": event.currency,
            },
        )
        self.session.add(transition_record)

        # Record Compliance Audit Event
        self.audit_repo.record(
            case_id=existing_case.id,
            event_type="CASE_RECOVERED",
            actor_type=ActorType.PROVIDER,
            correlation_id=correlation_id,
            payload_safe={
                "source_event_id": event.external_event_id,
                "payment_reference": tx.external_transaction_id,
                "recovered_amount_minor": event.amount_minor,
                "currency": event.currency,
                "from_state": from_state.value,
                "to_state": RecoveryCaseState.RECOVERED.value,
            },
            from_state=from_state,
            to_state=RecoveryCaseState.RECOVERED,
            actor_id=f"provider.{event.provider}",
        )

        self.session.flush()

        logger.info("Case %s successfully resolved to RECOVERED by event %s", existing_case.case_key, event.external_event_id)
        return CaseProcessingOutcome(
            outcome="CASE_RESOLVED",
            case_id=existing_case.id,
            case_key=existing_case.case_key,
            state=RecoveryCaseState.RECOVERED,
            reason="Case successfully resolved following verified payment confirmation.",
            details={"recovered_amount_minor": event.amount_minor, "currency": event.currency},
        )

    def _handle_existing_case_update(
        self,
        event: CanonicalEventDTO,
        case: RecoveryCase,
        correlation_id: str,
    ) -> CaseProcessingOutcome:
        """Handle new failure event arriving for an existing recovery case."""
        if case.state in TERMINAL_STATES:
            # Financial integrity: Do not resurrect terminal cases without explicit policy
            logger.info("Failure event received for terminal case %s (%s). Preserving history.", case.case_key, case.state)
            return CaseProcessingOutcome(
                outcome="IGNORED",
                case_id=case.id,
                case_key=case.case_key,
                state=case.state,
                reason=f"Recovery case is already in terminal state '{case.state.value}'. Historical resolution preserved.",
            )

        # Out-of-order protection: Never downgrade or update a case whose transaction already succeeded
        tx = self.session.get(Transaction, case.trigger_transaction_id)
        if tx is not None and tx.status == TransactionStatus.SUCCEEDED:
            logger.info(
                "Stale failure event %s received for case %s with already SUCCEEDED transaction. Preserving success.",
                event.external_event_id,
                case.case_key,
            )
            return CaseProcessingOutcome(
                outcome="IGNORED",
                case_id=case.id,
                case_key=case.case_key,
                state=case.state,
                reason="Stale failure event ignored; associated transaction has already succeeded.",
            )


        # Update metadata for active case
        now = utc_now()
        meta = dict(case.metadata_json)
        previous_failures = meta.get("failure_count", 1)
        new_failure_count = previous_failures + 1
        meta["failure_count"] = new_failure_count
        meta["latest_failure_event_id"] = event.external_event_id
        meta["latest_failure_code"] = event.failure_code
        meta["latest_failure_message"] = event.failure_message

        # Re-evaluate priority with aged duration and multiple failures
        p_res = CasePrioritizer.calculate_priority(
            amount_minor=event.amount_minor,
            currency=event.currency,
            failure_code=event.failure_code,
            event_type=event.event_type,
            opened_at=case.opened_at,
            as_of=now,
        )
        case.priority = p_res.priority
        meta["priority_reason"] = p_res.reason
        meta["priority_factors"] = p_res.factors

        case.metadata_json = meta
        case.last_state_changed_at = now
        case.version += 1

        # Audit event recording update
        self.audit_repo.record(
            case_id=case.id,
            event_type="CASE_UPDATED",
            actor_type=ActorType.SYSTEM,
            correlation_id=correlation_id,
            payload_safe={
                "source_event_id": event.external_event_id,
                "failure_count": new_failure_count,
                "latest_failure_code": event.failure_code,
                "updated_priority": p_res.priority,
            },
            from_state=case.state,
            to_state=case.state,
            actor_id="system.case_engine",
        )

        self.session.flush()

        logger.info("Case %s updated with subsequent failure %s (failures=%d, priority=%d)", case.case_key, event.external_event_id, new_failure_count, case.priority)
        return CaseProcessingOutcome(
            outcome="CASE_UPDATED",
            case_id=case.id,
            case_key=case.case_key,
            state=case.state,
            priority=case.priority,
            reason=f"Case updated with subsequent failure event. Total failures: {new_failure_count}.",
            details={"failure_count": new_failure_count, "priority": case.priority},
        )

    def _create_new_case(
        self,
        event: CanonicalEventDTO,
        customer: Customer,
        tx: Transaction,
        case_key: str,
        correlation_id: str,
    ) -> CaseProcessingOutcome:
        """Create a new RecoveryCase in DETECTED state with deterministic priority and risk tier."""
        now = utc_now()

        # 1. Calculate deterministic priority score
        p_res = CasePrioritizer.calculate_priority(
            amount_minor=event.amount_minor,
            currency=event.currency,
            failure_code=event.failure_code,
            event_type=event.event_type,
            opened_at=now,
            as_of=now,
        )

        # 2. Calculate deterministic risk tier
        r_res = CaseRiskClassifier.classify_risk(
            amount_minor=event.amount_minor,
            currency=event.currency,
            failure_code=event.failure_code,
            event_type=event.event_type,
            customer_tier=event.metadata.get("customer_tier"),
        )

        # 3. Assemble metadata
        case_metadata = dict(event.metadata)
        case_metadata.update({
            "source_event_id": event.external_event_id,
            "provider": event.provider,
            "event_type": event.event_type,
            "failure_code": event.failure_code,
            "failure_message": event.failure_message,
            "failure_count": 1,
            "risk_tier": r_res.risk_tier.value,
            "risk_reason": r_res.reason,
            "risk_factors": r_res.factors,
            "priority_reason": p_res.reason,
            "priority_factors": p_res.factors,
            "amount_minor": event.amount_minor,
            "currency": event.currency,
        })

        case_id = uuid4()
        new_case = RecoveryCase(
            id=case_id,
            customer_id=customer.id,
            trigger_transaction_id=tx.id,
            case_key=case_key,
            state=RecoveryCaseState.DETECTED,
            priority=p_res.priority,
            opened_at=now,
            last_state_changed_at=now,
            closed_at=None,
            version=1,
            metadata_json=case_metadata,
        )

        try:
            with self.session.begin_nested():
                self.case_repo.save(new_case)
                self.session.flush()
        except IntegrityError:
            # Concurrency safety: Another worker inserted this case_key concurrently
            logger.warning("Concurrent case creation conflict on case_key %s; falling back to lookup.", case_key)
            existing = self.case_repo.find_by_case_key(case_key)
            if existing is not None:
                return self._handle_existing_case_update(event, existing, correlation_id)
            raise

        # 4. Record Initial State Transition
        trans_record = CaseStateTransition(
            id=uuid4(),
            case_id=new_case.id,
            from_state=None,
            to_state=RecoveryCaseState.DETECTED,
            reason_code="AUTOMATIC_EVENT_INGESTION",
            actor_type=ActorType.SYSTEM,
            correlation_id=correlation_id,
            occurred_at=now,
            sequence_number=1,
            metadata_json={
                "source_event_id": event.external_event_id,
                "amount_minor": event.amount_minor,
                "currency": event.currency,
                "risk_tier": r_res.risk_tier.value,
            },
        )
        self.session.add(trans_record)

        # 5. Record Initial Audit Event
        self.audit_repo.record(
            case_id=new_case.id,
            event_type="CASE_OPENED",
            actor_type=ActorType.SYSTEM,
            correlation_id=correlation_id,
            payload_safe={
                "source_event_id": event.external_event_id,
                "event_type": event.event_type,
                "amount_minor": event.amount_minor,
                "currency": event.currency,
                "case_key": case_key,
                "initial_priority": p_res.priority,
                "risk_tier": r_res.risk_tier.value,
                "priority_reason": p_res.reason,
                "risk_reason": r_res.reason,
            },
            from_state=None,
            to_state=RecoveryCaseState.DETECTED,
            actor_id="system.case_engine",
        )

        self.session.flush()

        logger.info(
            "New recovery case created: id=%s, key=%s, priority=%d, risk=%s, amount=%s %d",
            new_case.id,
            case_key,
            p_res.priority,
            r_res.risk_tier.value,
            event.currency,
            event.amount_minor,
        )

        return CaseProcessingOutcome(
            outcome="CASE_CREATED",
            case_id=new_case.id,
            case_key=new_case.case_key,
            state=RecoveryCaseState.DETECTED,
            priority=p_res.priority,
            risk_tier=r_res.risk_tier.value,
            reason=f"Recovery case opened. Priority: {p_res.priority} ({p_res.reason}). Risk: {r_res.risk_tier.value.upper()}.",
            details={
                "amount_minor": event.amount_minor,
                "currency": event.currency,
                "priority": p_res.priority,
                "risk_tier": r_res.risk_tier.value,
            },
        )
