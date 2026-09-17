"""Add verified provider event and recovery evidence tables.
Revision ID: 0002_verified_recovery_intelligence
Revises: 0001_phase2_core_data
Author: Karthikeya
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_verified_recovery_intelligence"
down_revision = "0001_phase2_core_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_event_id", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("payload_safe", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_event_id", name="uq_provider_event"),
    )
    op.create_table(
        "recovery_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.String(length=200), nullable=False),
        sa.Column("provider_event_id", sa.String(length=200), nullable=False),
        sa.Column("failed_transaction_id", sa.String(length=200), nullable=False),
        sa.Column("successful_transaction_id", sa.String(length=200), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attribution_window_hours", sa.Integer(), nullable=False),
        sa.Column("attribution_reason", sa.String(length=200), nullable=False),
        sa.Column("attributable", sa.Boolean(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id", name="uq_recovery_evidence_provider_event"),
    )
    op.create_index(
        "ix_recovery_evidence_failed_transaction", "recovery_evidence", ["failed_transaction_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_recovery_evidence_failed_transaction", table_name="recovery_evidence")
    op.drop_table("recovery_evidence")
    op.drop_table("provider_webhook_events")
