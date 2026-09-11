"""Deterministic synthetic data generator for Phase 2 tests and local development.

Author: Karthikeya
Architectural layer: test/support data generation.

All records are synthetic, namespaced, and provider-labelled. This module does
not call payment systems or infer real customer behavior.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid5

from sqlalchemy.orm import Session

from app.core.enums import (
    ActionType,
    ActorType,
    CustomerStatus,
    DecisionValidationStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    TransactionStatus,
)
from app.models.domain import (
    AgentDecision,
    AuditEvent,
    Customer,
    RecoveryAttempt,
    RecoveryCase,
    Transaction,
)

_NAMESPACE = UUID("3d4d8d2e-0b0a-5c0a-bf6d-1e3d331b8b50")
_FIXED_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SyntheticDataset:
    """Objects inserted by one deterministic fixture run."""

    customers: list[Customer]
    transactions: list[Transaction]
    cases: list[RecoveryCase]
    attempts: list[RecoveryAttempt]
    decisions: list[AgentDecision]
    audit_events: list[AuditEvent]


def synthetic_uuid(seed: str, value: str) -> UUID:
    """Return a stable UUID for a fixture seed and logical record name."""

    return uuid5(_NAMESPACE, f"{seed}:{value}")


def build_synthetic_dataset(seed: int = 42) -> SyntheticDataset:
    """Build, but do not persist, a deterministic Phase 2 scenario dataset."""

    prefix = f"seed-{seed}"
    customers = [
        Customer(
            id=synthetic_uuid(prefix, "customer-001"),
            provider="synthetic",
            external_customer_id="synthetic_customer_001",
            email="customer001@example.test",
            display_name="Synthetic Customer 001",
            status=CustomerStatus.ACTIVE,
            metadata_json={"synthetic": True, "scenario": "complete_context"},
        ),
        Customer(
            id=synthetic_uuid(prefix, "customer-002"),
            provider="synthetic",
            external_customer_id="synthetic_customer_002",
            email=None,
            display_name=None,
            status=CustomerStatus.ACTIVE,
            metadata_json={"synthetic": True, "scenario": "missing_context"},
        ),
        Customer(
            id=synthetic_uuid(prefix, "customer-003"),
            provider="synthetic",
            external_customer_id="synthetic_customer_003",
            email="customer003@example.test",
            display_name="Synthetic Customer 003",
            status=CustomerStatus.ACTIVE,
            metadata_json={"synthetic": True, "scenario": "uncertain_outcome"},
        ),
    ]

    transactions = [
        Transaction(
            id=synthetic_uuid(prefix, "transaction-001"),
            customer_id=customers[0].id,
            provider="synthetic",
            external_transaction_id="synthetic_txn_001",
            amount_minor=4999,
            currency="INR",
            status=TransactionStatus.FAILED,
            failure_code="insufficient_funds",
            failure_message_safe="The synthetic payment was declined.",
            occurred_at=_FIXED_NOW,
            metadata_json={"synthetic": True, "scenario": "complete_context"},
        ),
        Transaction(
            id=synthetic_uuid(prefix, "transaction-002"),
            customer_id=customers[1].id,
            provider="synthetic",
            external_transaction_id="synthetic_txn_002",
            amount_minor=1299,
            currency="INR",
            status=TransactionStatus.FAILED,
            failure_code="provider_declined",
            failure_message_safe="The synthetic payment was declined.",
            occurred_at=_FIXED_NOW,
            metadata_json={"synthetic": True, "scenario": "missing_context"},
        ),
        Transaction(
            id=synthetic_uuid(prefix, "transaction-003"),
            customer_id=customers[2].id,
            provider="synthetic",
            external_transaction_id="synthetic_txn_003",
            amount_minor=7999,
            currency="INR",
            status=TransactionStatus.PENDING,
            failure_code=None,
            failure_message_safe=None,
            occurred_at=_FIXED_NOW,
            metadata_json={"synthetic": True, "scenario": "uncertain_outcome"},
        ),
    ]

    cases = [
        RecoveryCase(
            id=synthetic_uuid(prefix, "case-001"),
            customer_id=customers[0].id,
            trigger_transaction_id=transactions[0].id,
            case_key=f"synthetic:{seed}:failed:001",
            state=RecoveryCaseState.DETECTED,
            priority=100,
            opened_at=_FIXED_NOW,
            last_state_changed_at=_FIXED_NOW,
            version=1,
            metadata_json={"synthetic": True, "scenario": "complete_context"},
        ),
        RecoveryCase(
            id=synthetic_uuid(prefix, "case-002"),
            customer_id=customers[1].id,
            trigger_transaction_id=transactions[1].id,
            case_key=f"synthetic:{seed}:failed:002",
            state=RecoveryCaseState.ESCALATED,
            priority=80,
            opened_at=_FIXED_NOW,
            last_state_changed_at=_FIXED_NOW,
            version=1,
            metadata_json={"synthetic": True, "scenario": "missing_context"},
        ),
        RecoveryCase(
            id=synthetic_uuid(prefix, "case-003"),
            customer_id=customers[2].id,
            trigger_transaction_id=transactions[2].id,
            case_key=f"synthetic:{seed}:pending:003",
            state=RecoveryCaseState.VERIFICATION_PENDING,
            priority=90,
            opened_at=_FIXED_NOW,
            last_state_changed_at=_FIXED_NOW,
            version=1,
            metadata_json={"synthetic": True, "scenario": "uncertain_outcome"},
        ),
    ]

    attempts = [
        RecoveryAttempt(
            id=synthetic_uuid(prefix, "attempt-003"),
            case_id=cases[2].id,
            sequence_number=1,
            status=RecoveryAttemptStatus.UNCERTAIN,
            action_type=ActionType.RETRY_PAYMENT,
            started_at=_FIXED_NOW,
            idempotency_key=f"synthetic:{seed}:attempt:003:1",
            outcome="provider_timeout",
            error_class="timeout",
            error_safe_message="Synthetic provider outcome is uncertain.",
            metadata_json={"synthetic": True},
        )
    ]
    decisions = [
        AgentDecision(
            id=synthetic_uuid(prefix, "decision-003"),
            case_id=cases[2].id,
            attempt_id=attempts[0].id,
            decision_version=1,
            action_type=ActionType.RETRY_PAYMENT,
            reason_code="synthetic_uncertain_retry",
            rationale_safe="Synthetic fixture decision; not generated by an agent.",
            confidence=0.75,
            raw_response_hash="synthetic-hash-003",
            validation_status=DecisionValidationStatus.VALID,
        )
    ]
    audit_events = [
        AuditEvent(
            id=synthetic_uuid(prefix, "audit-002"),
            case_id=cases[1].id,
            event_type="case_escalated",
            from_state=RecoveryCaseState.DETECTED,
            to_state=RecoveryCaseState.ESCALATED,
            actor_type=ActorType.TEST,
            actor_id="synthetic-fixture",
            correlation_id=f"synthetic:{seed}:correlation:002",
            event_time=_FIXED_NOW,
            payload_safe={"reason": "missing_context", "synthetic": True},
            sequence_number=1,
        ),
        AuditEvent(
            id=synthetic_uuid(prefix, "audit-003"),
            case_id=cases[2].id,
            event_type="verification_pending",
            from_state=RecoveryCaseState.ACTION_PENDING,
            to_state=RecoveryCaseState.VERIFICATION_PENDING,
            actor_type=ActorType.TEST,
            actor_id="synthetic-fixture",
            correlation_id=f"synthetic:{seed}:correlation:003",
            event_time=_FIXED_NOW,
            payload_safe={"outcome": "uncertain", "synthetic": True},
            sequence_number=1,
        ),
    ]
    return SyntheticDataset(customers, transactions, cases, attempts, decisions, audit_events)


def seed_synthetic_data(session: Session, seed: int = 42) -> SyntheticDataset:
    """Persist one deterministic fixture dataset and return its object groups."""

    dataset = build_synthetic_dataset(seed)
    for group in (
        dataset.customers,
        dataset.transactions,
        dataset.cases,
        dataset.attempts,
        dataset.decisions,
        dataset.audit_events,
    ):
        session.add_all(group)
        session.flush()
    return dataset
