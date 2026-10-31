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
    ConsentStatus,
    ConsentType,
    CustomerStatus,
    DecisionValidationStatus,
    ExecutionStatus,
    PolicyDecisionStatus,
    ReconciliationStatus,
    RecoveryAttemptStatus,
    RecoveryCaseState,
    TransactionStatus,
    UserRole,
    UserStatus,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowStepType,
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
    consents: Mapped[list["CustomerConsent"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class CustomerConsent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_consents"
    __table_args__ = (
        Index("ix_consent_customer_type", "customer_id", "consent_type"),
        Index("ix_consent_customer_status", "customer_id", "status"),
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    consent_type: Mapped[ConsentType] = mapped_column(nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(nullable=False, default=ConsentStatus.GRANTED)
    merchant_id: Mapped[str | None] = mapped_column(String(128))
    granted_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column()
    expires_at: Mapped[datetime | None] = mapped_column()
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="checkout_agreement")
    evidence_reference: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    customer: Mapped[Customer] = relationship(back_populates="consents")


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
    policy_decisions: Mapped[list["PolicyDecision"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    workflows: Mapped[list["RecoveryWorkflow"]] = relationship(
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


class PolicyDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable audit record of an authoritative policy engine evaluation."""

    __tablename__ = "policy_decisions"
    __table_args__ = (
        Index("ix_policy_decision_case_id", "case_id"),
        Index("ix_policy_decision_status", "decision_status"),
        Index("ix_policy_decision_idempotency", "case_id", "idempotency_key"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False
    )
    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_decisions.id", ondelete="CASCADE"), nullable=False
    )
    proposed_action: Mapped[ActionType] = mapped_column(nullable=False)
    decision_status: Mapped[PolicyDecisionStatus] = mapped_column(nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    rule_results_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(nullable=False, default=ActorType.SYSTEM)
    actor_id: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str | None] = mapped_column(String(250))
    case_version: Mapped[int] = mapped_column(nullable=False, default=1)
    evaluated_at: Mapped[datetime] = mapped_column(nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    case: Mapped[RecoveryCase] = relationship(back_populates="policy_decisions")
    recommendation: Mapped[AgentDecision] = relationship()


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
    __table_args__ = (
        UniqueConstraint("case_id", "sequence_number", name="uq_transition_case_sequence"),
        Index("ix_transition_case_occurred", "case_id", "occurred_at"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[RecoveryCaseState | None] = mapped_column()
    to_state: Mapped[RecoveryCaseState] = mapped_column(nullable=False)
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_type: Mapped[ActorType] = mapped_column(nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    case: Mapped[RecoveryCase] = relationship(back_populates="transitions")


class ProviderWebhookEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable provider event receipt used for idempotency and replay safety."""

    __tablename__ = "provider_webhook_events"
    __table_args__ = (UniqueConstraint("provider", "external_event_id", name="uq_provider_event"),)

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    signature_verified: Mapped[bool] = mapped_column(nullable=False, default=False)
    processed: Mapped[bool] = mapped_column(nullable=False, default=False)
    ingestion_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACCEPTED")
    payload_safe: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RecoveryEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Verified evidence linking a provider success to a recovery intervention."""

    __tablename__ = "recovery_evidence"
    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_recovery_evidence_provider_event"),
        Index("ix_recovery_evidence_failed_transaction", "failed_transaction_id"),
        CheckConstraint("amount_minor >= 0", name="ck_recovery_evidence_amount_nonnegative"),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="ck_recovery_evidence_currency",
        ),
    )

    intervention_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    failed_transaction_id: Mapped[str] = mapped_column(String(200), nullable=False)
    successful_transaction_id: Mapped[str] = mapped_column(String(200), nullable=False)
    amount_minor: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(nullable=False)
    attribution_window_hours: Mapped[int] = mapped_column(nullable=False, default=72)
    attribution_reason: Mapped[str] = mapped_column(String(200), nullable=False)
    attributable: Mapped[bool] = mapped_column(nullable=False, default=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User account model for authentication, authorization, and RBAC."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_user_email"),
        Index("ix_user_email", "email"),
        Index("ix_user_role", "role"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(default=UserRole.OPERATOR, nullable=False)
    status: Mapped[UserStatus] = mapped_column(default=UserStatus.ACTIVE, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column()


class RecoveryWorkflow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Orchestrated recovery workflow executing authorized bounded steps."""

    __tablename__ = "recovery_workflows"
    __table_args__ = (
        Index("ix_workflow_case_status", "case_id", "status"),
        Index("ix_workflow_policy_decision", "policy_decision_id"),
    )

    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False
    )
    policy_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("policy_decisions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        nullable=False, default=WorkflowStatus.PENDING
    )
    strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    current_step_index: Mapped[int] = mapped_column(nullable=False, default=0)
    max_steps: Mapped[int] = mapped_column(nullable=False, default=10)
    scheduled_for: Mapped[datetime | None] = mapped_column()
    expires_at: Mapped[datetime | None] = mapped_column()
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    case: Mapped[RecoveryCase] = relationship(back_populates="workflows")
    policy_decision: Mapped[PolicyDecision] = relationship()
    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.step_index",
    )


class WorkflowStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Discrete, idempotent execution step within a recovery workflow."""

    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_index", name="uq_step_workflow_index"),
        UniqueConstraint("idempotency_key", name="uq_step_idempotency_key"),
        Index("ix_step_workflow_status", "workflow_id", "status"),
    )

    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_workflows.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(nullable=False)
    step_type: Mapped[WorkflowStepType] = mapped_column(nullable=False)
    status: Mapped[WorkflowStepStatus] = mapped_column(
        nullable=False, default=WorkflowStepStatus.PENDING
    )
    idempotency_key: Mapped[str] = mapped_column(String(250), nullable=False)
    action_type: Mapped[ActionType] = mapped_column(nullable=False, default=ActionType.NONE)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_result_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(String(500))
    executed_at: Mapped[datetime | None] = mapped_column()

    workflow: Mapped[RecoveryWorkflow] = relationship(back_populates="steps")
    executions: Mapped[list["RecoveryExecution"]] = relationship(
        back_populates="step", cascade="all, delete-orphan"
    )


class RecoveryExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Execution outcome record dispatched via a controlled gateway adapter."""

    __tablename__ = "recovery_executions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_recovery_execution_idempotency"),
        Index("ix_recovery_execution_case", "case_id"),
        Index("ix_recovery_execution_external_ref", "external_reference"),
        Index("ix_recovery_execution_status", "status"),
    )

    step_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="razorpay")
    external_reference: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[ExecutionStatus] = mapped_column(
        nullable=False, default=ExecutionStatus.PENDING
    )
    amount_minor: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(250), nullable=False)
    request_payload_safe: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    response_payload_safe: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message_safe: Mapped[str | None] = mapped_column(String(500))
    latency_ms: Mapped[int | None] = mapped_column()
    executed_at: Mapped[datetime] = mapped_column(nullable=False)

    step: Mapped[WorkflowStep] = relationship(back_populates="executions")
    case: Mapped[RecoveryCase] = relationship()

