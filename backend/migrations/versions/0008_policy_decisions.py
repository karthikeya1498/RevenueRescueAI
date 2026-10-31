"""Add policy decisions table for recovery policy engine auditing.

Revision ID: 0008_policy_decisions
Revises: 0007_customer_consents
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_policy_decisions"
down_revision = "0007_customer_consents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("proposed_action", sa.String(length=50), nullable=False),
        sa.Column("decision_status", sa.String(length=50), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("rule_results_json", sa.JSON(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.String(length=200), nullable=True),
        sa.Column("idempotency_key", sa.String(length=250), nullable=True),
        sa.Column("case_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["recovery_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["agent_decisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_policy_decision_case_id",
        "policy_decisions",
        ["case_id"],
    )
    op.create_index(
        "ix_policy_decision_status",
        "policy_decisions",
        ["decision_status"],
    )
    op.create_index(
        "ix_policy_decision_idempotency",
        "policy_decisions",
        ["case_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_policy_decision_idempotency", table_name="policy_decisions")
    op.drop_index("ix_policy_decision_status", table_name="policy_decisions")
    op.drop_index("ix_policy_decision_case_id", table_name="policy_decisions")
    op.drop_table("policy_decisions")
