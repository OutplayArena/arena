"""add is_public to sessions

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-07-01 00:00:00.000000

Adds an is_public flag to every game session (default False = private).
Only sessions where is_public=True contribute to the global leaderboard.
Users toggle visibility from their History page; the change triggers a
full registry rebuild so the leaderboard always reflects the correct set
of public sessions.
"""
from alembic import op
import sqlalchemy as sa


revision = 'm3n4o5p6q7r8'
down_revision = 'l2m3n4o5p6q7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("sessions", "is_public")
