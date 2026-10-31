"""Add event ingestion status and indexing to provider_webhook_events.

Revision ID: 0005_event_ingestion_enhancements
Revises: 0004_user_authentication
Author: Karthikeya
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_event_ingestion_enhancements"
down_revision = "0004_user_authentication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_webhook_events",
        sa.Column(
            "ingestion_status",
            sa.String(length=32),
            nullable=False,
            server_default="ACCEPTED",
        ),
    )
    op.create_index(
        "ix_webhook_event_type_created",
        "provider_webhook_events",
        ["event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_event_type_created", table_name="provider_webhook_events")
    op.drop_column("provider_webhook_events", "ingestion_status")
