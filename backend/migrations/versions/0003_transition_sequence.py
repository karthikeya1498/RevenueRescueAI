"""Add durable lifecycle transition sequence numbers.
Revision ID: 0003_transition_sequence
Revises: 0002_verified_recovery_intelligence
Author: Karthikeya
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_transition_sequence"
down_revision = "0002_verified_recovery_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_state_transitions",
        sa.Column("sequence_number", sa.Integer(), nullable=True),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, case_id FROM case_state_transitions ORDER BY case_id, occurred_at, id")
    ).fetchall()
    counters: dict[str, int] = {}
    for row in rows:
        case_key = str(row.case_id)
        counters[case_key] = counters.get(case_key, 0) + 1
        connection.execute(
            sa.text(
                "UPDATE case_state_transitions "
                "SET sequence_number = :sequence_number WHERE id = :id"
            ),
            {"sequence_number": counters[case_key], "id": row.id},
        )
    with op.batch_alter_table("case_state_transitions") as batch:
        batch.alter_column("sequence_number", existing_type=sa.Integer(), nullable=False)
        batch.create_unique_constraint(
            "uq_transition_case_sequence", ["case_id", "sequence_number"]
        )


def downgrade() -> None:
    with op.batch_alter_table("case_state_transitions") as batch:
        batch.drop_constraint("uq_transition_case_sequence", type_="unique")
        batch.drop_column("sequence_number")
