"""add status, error_message, and locked columns to sessions

Revision ID: c4d5e6f7g003
Revises: b3c5d6e7f002
Create Date: 2026-05-31 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7g003"
down_revision: Union[str, Sequence[str], None] = "b3c5d6e7f002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
    )
    op.add_column(
        "sessions",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute(
        "UPDATE sessions SET status = 'completed' WHERE state_json->>'phase' = 'complete'"
    )
    op.execute(
        "UPDATE sessions SET status = 'running' WHERE state_json->>'phase' = 'awaiting_action' AND jsonb_array_length(state_json->'history') > 0"
    )


def downgrade() -> None:
    op.drop_column("sessions", "locked")
    op.drop_column("sessions", "error_message")
    op.drop_column("sessions", "status")
