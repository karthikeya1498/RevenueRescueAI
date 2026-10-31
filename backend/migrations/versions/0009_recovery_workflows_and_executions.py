"""Add recovery workflows, steps, and executions for bounded workflow orchestration.

Revision ID: 0009_recovery_workflows_and_executions
Revises: 0008_policy_decisions
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_recovery_workflows_and_executions"
down_revision = "0008_policy_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. recovery_workflows
    op.create_table(
        "recovery_workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("policy_decision_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("strategy", sa.String(length=100), nullable=False),
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["recovery_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_decision_id"], ["policy_decisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_case_status", "recovery_workflows", ["case_id", "status"])
    op.create_index("ix_workflow_policy_decision", "recovery_workflows", ["policy_decision_id"])

    # 2. workflow_steps
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=250), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("execution_result_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["recovery_workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "step_index", name="uq_step_workflow_index"),
        sa.UniqueConstraint("idempotency_key", name="uq_step_idempotency_key"),
    )
    op.create_index("ix_step_workflow_status", "workflow_steps", ["workflow_id", "status"])

    # 3. recovery_executions
    op.create_table(
        "recovery_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("step_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_reference", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("idempotency_key", sa.String(length=250), nullable=False),
        sa.Column("request_payload_safe", sa.JSON(), nullable=False),
        sa.Column("response_payload_safe", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message_safe", sa.String(length=500), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["step_id"], ["workflow_steps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["recovery_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_recovery_execution_idempotency"),
    )
    op.create_index("ix_recovery_execution_case", "recovery_executions", ["case_id"])
    op.create_index("ix_recovery_execution_external_ref", "recovery_executions", ["external_reference"])
    op.create_index("ix_recovery_execution_status", "recovery_executions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_recovery_execution_status", table_name="recovery_executions")
    op.drop_index("ix_recovery_execution_external_ref", table_name="recovery_executions")
    op.drop_index("ix_recovery_execution_case", table_name="recovery_executions")
    op.drop_table("recovery_executions")

    op.drop_index("ix_step_workflow_status", table_name="workflow_steps")
    op.drop_table("workflow_steps")

    op.drop_index("ix_workflow_policy_decision", table_name="recovery_workflows")
    op.drop_index("ix_workflow_case_status", table_name="recovery_workflows")
    op.drop_table("recovery_workflows")
