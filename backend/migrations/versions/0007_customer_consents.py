"""Add customer consents table for recovery policy compliance.

Revision ID: 0007_customer_consents
Revises: 0006_case_management_indexes
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_customer_consents"
down_revision = "0006_case_management_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("consent_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("merchant_id", sa.String(length=128), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("evidence_reference", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_consent_customer_type",
        "customer_consents",
        ["customer_id", "consent_type"],
    )
    op.create_index(
        "ix_consent_customer_status",
        "customer_consents",
        ["customer_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_consent_customer_status", table_name="customer_consents")
    op.drop_index("ix_consent_customer_type", table_name="customer_consents")
    op.drop_table("customer_consents")
