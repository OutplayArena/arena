"""add api_keys table and session agent columns

Revision ID: a2d3e4f5b001
Revises: e8f3b2c1a001
Create Date: 2026-05-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a2d3e4f5b001'
down_revision: Union[str, Sequence[str], None] = 'e8f3b2c1a001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("key_value", sa.String(1024), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.add_column(
        "sessions",
        sa.Column("agent_a", sa.String(128), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("agent_b", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "agent_b")
    op.drop_column("sessions", "agent_a")
    op.drop_table("api_keys")
