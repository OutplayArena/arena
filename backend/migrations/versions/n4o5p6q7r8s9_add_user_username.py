"""add username to users

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-07-01 00:00:00.000000

Stores a provider-specific public display handle alongside each user:
  - GitHub: the login handle (e.g. "herbertw", shown as @herbertw)
  - Google: the given_name / first name only (e.g. "Alice")

Never set to email or any other private identifier.  Used for leaderboard
attribution when a user's public session results are shown to others.
"""
from alembic import op
import sqlalchemy as sa


revision = 'n4o5p6q7r8s9'
down_revision = 'm3n4o5p6q7r8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("username", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "username")
