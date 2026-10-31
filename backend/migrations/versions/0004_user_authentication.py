"""Add user authentication and RBAC table.

Revision ID: 0004_user_authentication
Revises: 0003_transition_sequence
Author: Karthikeya
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_user_authentication"
down_revision = "0003_transition_sequence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="ROLE_OPERATOR"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_user_email"),
    )
    op.create_index("ix_user_email", "users", ["email"])
    op.create_index("ix_user_role", "users", ["role"])


def downgrade() -> None:
    op.drop_index("ix_user_role", table_name="users")
    op.drop_index("ix_user_email", table_name="users")
    op.drop_table("users")
