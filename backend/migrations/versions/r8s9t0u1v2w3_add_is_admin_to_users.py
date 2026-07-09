"""add is_admin to users

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-07-06 00:00:00.000000

Adds a boolean ``is_admin`` column to ``users`` (default False) so the
admin dashboard (#116) can grant/revoke admin access at runtime. The
``ADMIN_USER_IDS`` env var (see :mod:`arena.settings`) is the bootstrap
mechanism for the first admin before any row can be flipped.
"""
from alembic import op
import sqlalchemy as sa


revision = 'r8s9t0u1v2w3'
down_revision = 'q7r8s9t0u1v2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_admin")