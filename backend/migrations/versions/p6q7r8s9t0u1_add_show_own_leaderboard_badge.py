"""add show_own_leaderboard_badge to users

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-07-02 00:00:00.000000

Adds a personal display preference letting a user opt in to seeing a "You"
badge highlighting their own rows on the leaderboard. Defaults to False
(hidden) for both new and existing users, so nobody sees the badge until
they explicitly enable it from Settings.
"""
from alembic import op
import sqlalchemy as sa


revision = 'p6q7r8s9t0u1'
down_revision = 'o5p6q7r8s9t0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "show_own_leaderboard_badge",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "show_own_leaderboard_badge")
