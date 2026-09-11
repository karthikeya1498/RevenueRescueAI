"""Create Phase 2 core data and state tables.

Revision ID: 0001_phase2_core_data
Revises:
Author: Karthikeya
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_phase2_core_data"
down_revision = None
branch_labels = None
depends_on = None


def enum(name: str, values: list[str]) -> sa.Enum:
    """Create a portable non-native enum for SQLite and PostgreSQL-shaped use."""

    return sa.Enum(*values, name=name, native_enum=False, validate_strings=True)


def upgrade() -> None:
    """Create the initial Phase 2 relational schema."""

    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_customer_id", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column(
            "status", enum("customer_status", ["active", "inactive", "restricted"]), nullable=False
        ),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "external_customer_id", name="uq_customer_provider_external"
        ),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_transaction_id", sa.String(length=128), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "status",
            enum(
                "transaction_status",
                [
                    "created",
                    "authorized",
                    "succeeded",
                    "failed",
                    "pending",
                    "cancelled",
                    "refunded",
                    "unknown",
                ],
            ),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message_safe", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_minor >= 0", name="ck_transaction_amount_nonnegative"),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)", name="ck_transaction_currency"
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "external_transaction_id", name="uq_transaction_provider_external"
        ),
    )
    op.create_index("ix_transaction_status_occurred", "transactions", ["status", "occurred_at"])
    op.create_table(
        "recovery_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("trigger_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("case_key", sa.String(length=200), nullable=False),
        sa.Column(
            "state",
            enum(
                "recovery_case_state",
                [
                    "detected",
                    "context_ready",
                    "awaiting_decision",
                    "action_pending",
                    "verification_pending",
                    "recovered",
                    "retry_eligible",
                    "escalated",
                    "stopped",
                    "closed",
                ],
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_state_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["trigger_transaction_id"], ["transactions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_key", name="uq_recovery_case_key"),
    )
    op.create_index(
        "ix_recovery_case_state_changed", "recovery_cases", ["state", "last_state_changed_at"]
    )
    op.create_index("ix_recovery_case_customer", "recovery_cases", ["customer_id"])
    op.create_table(
        "recovery_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            enum(
                "recovery_attempt_status",
                ["planned", "started", "succeeded", "failed", "uncertain", "cancelled"],
            ),
            nullable=False,
        ),
        sa.Column(
            "action_type",
            enum(
                "action_type",
                ["none", "retry_payment", "send_reminder", "request_operator_review", "stop"],
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(length=100), nullable=True),
        sa.Column("provider_reference", sa.String(length=200), nullable=True),
        sa.Column("idempotency_key", sa.String(length=250), nullable=False),
        sa.Column("error_class", sa.String(length=120), nullable=True),
        sa.Column("error_safe_message", sa.String(length=500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["recovery_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "sequence_number", name="uq_attempt_case_sequence"),
        sa.UniqueConstraint("idempotency_key", name="uq_attempt_idempotency_key"),
    )
    op.create_index("ix_attempt_case_sequence", "recovery_attempts", ["case_id", "sequence_number"])
    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("decision_version", sa.Integer(), nullable=False),
        sa.Column(
            "action_type",
            enum(
                "decision_action_type",
                ["none", "retry_payment", "send_reminder", "request_operator_review", "stop"],
            ),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(length=120), nullable=False),
        sa.Column("rationale_safe", sa.String(length=2000), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("raw_response_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "validation_status",
            enum(
                "decision_validation_status",
                ["not_validated", "valid", "invalid", "rejected_by_policy"],
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_decision_confidence",
        ),
        sa.ForeignKeyConstraint(["attempt_id"], ["recovery_attempts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["case_id"], ["recovery_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column(
            "from_state",
            enum(
                "audit_from_state",
                [
                    "detected",
                    "context_ready",
                    "awaiting_decision",
                    "action_pending",
                    "verification_pending",
                    "recovered",
                    "retry_eligible",
                    "escalated",
                    "stopped",
                    "closed",
                ],
            ),
            nullable=True,
        ),
        sa.Column(
            "to_state",
            enum(
                "audit_to_state",
                [
                    "detected",
                    "context_ready",
                    "awaiting_decision",
                    "action_pending",
                    "verification_pending",
                    "recovered",
                    "retry_eligible",
                    "escalated",
                    "stopped",
                    "closed",
                ],
            ),
            nullable=True,
        ),
        sa.Column(
            "actor_type",
            enum("actor_type", ["system", "operator", "agent", "provider", "test"]),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(length=200), nullable=True),
        sa.Column("correlation_id", sa.String(length=200), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_safe", sa.JSON(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["recovery_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "sequence_number", name="uq_audit_case_sequence"),
    )
    op.create_index("ix_audit_case_sequence", "audit_events", ["case_id", "sequence_number"])
    op.create_table(
        "case_state_transitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column(
            "from_state",
            enum(
                "transition_from_state",
                [
                    "detected",
                    "context_ready",
                    "awaiting_decision",
                    "action_pending",
                    "verification_pending",
                    "recovered",
                    "retry_eligible",
                    "escalated",
                    "stopped",
                    "closed",
                ],
            ),
            nullable=True,
        ),
        sa.Column(
            "to_state",
            enum(
                "transition_to_state",
                [
                    "detected",
                    "context_ready",
                    "awaiting_decision",
                    "action_pending",
                    "verification_pending",
                    "recovered",
                    "retry_eligible",
                    "escalated",
                    "stopped",
                    "closed",
                ],
            ),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(length=120), nullable=False),
        sa.Column(
            "actor_type",
            enum("transition_actor_type", ["system", "operator", "agent", "provider", "test"]),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["recovery_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transition_case_occurred", "case_state_transitions", ["case_id", "occurred_at"]
    )


def downgrade() -> None:
    """Drop the Phase 2 schema in reverse dependency order."""

    op.drop_index("ix_transition_case_occurred", table_name="case_state_transitions")
    op.drop_table("case_state_transitions")
    op.drop_index("ix_audit_case_sequence", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("agent_decisions")
    op.drop_index("ix_attempt_case_sequence", table_name="recovery_attempts")
    op.drop_table("recovery_attempts")
    op.drop_index("ix_recovery_case_customer", table_name="recovery_cases")
    op.drop_index("ix_recovery_case_state_changed", table_name="recovery_cases")
    op.drop_table("recovery_cases")
    op.drop_index("ix_transaction_status_occurred", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("customers")
