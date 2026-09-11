"""Phase 2 SQLAlchemy domain models.

Author: Karthikeya
Architectural layer: persistence models.

These models persist state and history only. They do not call providers, reason
with an LLM, or execute recovery actions.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.enums import (
    ActionType,
    ActorType,
    CustomerStatus,
    DecisionValidationStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    TransactionStatus,
)


def enum_values(enum_type: type) -> list[str]:
    """Return persisted enum values rather than Python member names."""

    return [member.value for member in enum_type]


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("provider", "external_customer_id", name="uq_customer_provider_external"),
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="synthetic")
    external_customer_id: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[CustomerStatus] = mapped_column(default=CustomerStatus.ACTIVE, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="customer")
    recovery_cases: Mapped[list["RecoveryCase"]] = relationship(back_populates="customer")


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_transaction_id", name="uq_transaction_provider_external"
        ),
        CheckConstraint("amount_minor >= 0", name="ck_transaction_amount_nonnegative"),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)", name="ck_transaction_currency"
        ),
        Index("ix_transaction_status_occurred", "status", "occurred_at"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="synthetic")
    external_transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_minor: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message_safe: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="transactions")
    recovery_cases: Mapped[list["RecoveryCase"]] = relationship(
        back_populates="trigger_transaction"
    )


class RecoveryCase(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recovery_cases"
    __table_args__ = (
        UniqueConstraint("case_key", name="uq_recovery_case_key"),
        Index("ix_recovery_case_state_changed", "state", "last_state_changed_at"),
        Index("ix_recovery_case_customer", "customer_id"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    trigger_transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=False
    )
    case_key: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[RecoveryCaseState] = mapped_column(
        nullable=False, default=RecoveryCaseState.DETECTED
    )
    priority: Mapped[int] = mapped_column(nullable=False, default=100)
    opened_at: Mapped[datetime] = mapped_column(nullable=False)
    last_state_changed_at: Mapped[datetime] = mapped_column(nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column()
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    customer: Mapped[Customer] = relationship(back_populates="recovery_cases")
    trigger_transaction: Mapped[Transaction] = relationship(back_populates="recovery_cases")
    attempts: Mapped[list["RecoveryAttempt"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["AgentDecision"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    transitions: Mapped[list["CaseStateTransition"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class RecoveryAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recovery_attempts"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence_number", name="uq_attempt_case_sequence"),
        UniqueConstraint("idempotency_key", name="uq_attempt_idempotency_key"),
        Index("ix_attempt_case_sequence", "case_id", "sequence_number"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[RecoveryAttemptStatus] = mapped_column(nullable=False)
    action_type: Mapped[ActionType] = mapped_column(nullable=False, default=ActionType.NONE)
    started_at: Mapped[datetime | None] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column()
    outcome: Mapped[str | None] = mapped_column(String(100))
    provider_reference: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(250), nullable=False)
    error_class: Mapped[str | None] = mapped_column(String(120))
    error_safe_message: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    case: Mapped[RecoveryCase] = relationship(back_populates="attempts")
    decision: Mapped["AgentDecision | None"] = relationship(back_populates="attempt", uselist=False)


class AgentDecision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_decisions"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_decision_confidence",
        ),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("recovery_attempts.id", ondelete="SET NULL")
    )
    decision_version: Mapped[int] = mapped_column(nullable=False, default=1)
    action_type: Mapped[ActionType] = mapped_column(nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    rationale_safe: Mapped[str | None] = mapped_column(String(2000))
    confidence: Mapped[Decimal | None] = mapped_column()
    raw_response_hash: Mapped[str | None] = mapped_column(String(128))
    validation_status: Mapped[DecisionValidationStatus] = mapped_column(
        nullable=False, default=DecisionValidationStatus.NOT_VALIDATED
    )

    case: Mapped[RecoveryCase] = relationship(back_populates="decisions")
    attempt: Mapped[RecoveryAttempt | None] = relationship(back_populates="decision")


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence_number", name="uq_audit_case_sequence"),
        Index("ix_audit_case_sequence", "case_id", "sequence_number"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    from_state: Mapped[RecoveryCaseState | None] = mapped_column()
    to_state: Mapped[RecoveryCaseState | None] = mapped_column()
    actor_type: Mapped[ActorType] = mapped_column(nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(200))
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_time: Mapped[datetime] = mapped_column(nullable=False)
    payload_safe: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)

    case: Mapped[RecoveryCase] = relationship(back_populates="audit_events")


class CaseStateTransition(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "case_state_transitions"
    __table_args__ = (Index("ix_transition_case_occurred", "case_id", "occurred_at"),)

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[RecoveryCaseState | None] = mapped_column()
    to_state: Mapped[RecoveryCaseState] = mapped_column(nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    case: Mapped[RecoveryCase] = relationship(back_populates="transitions")
