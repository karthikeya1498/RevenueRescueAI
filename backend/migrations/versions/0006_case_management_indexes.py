"""Add operational priority and state index for recovery case queue ordering.

Revision ID: 0006_case_management_indexes
Revises: 0005_event_ingestion_enhancements
Author: Karthikeya
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_case_management_indexes"
down_revision = "0005_event_ingestion_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_recovery_case_priority_state",
        "recovery_cases",
        ["priority", "state"],
    )
    op.create_index(
        "ix_recovery_case_priority_opened",
        "recovery_cases",
        ["priority", "opened_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_recovery_case_priority_opened", table_name="recovery_cases")
    op.drop_index("ix_recovery_case_priority_state", table_name="recovery_cases")
