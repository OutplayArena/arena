"""repurpose api_keys table and replace agent_a/b with agents_json

Revision ID: b3c5d6e7f002
Revises: a2d3e4f5b001
Create Date: 2026-05-30 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b3c5d6e7f002'
down_revision: Union[str, Sequence[str], None] = 'a2d3e4f5b001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("api_keys", "provider")
    op.drop_column("api_keys", "key_value")
    op.add_column(
        "api_keys",
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("key_prefix", sa.String(12), nullable=False),
    )
    op.add_column(
        "api_keys",
        sa.Column("name", sa.String(128), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "api_keys",
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE api_keys SET user_id = '00000000-0000-0000-0000-000000000001' WHERE user_id IS NULL"
    )
    op.alter_column("api_keys", "user_id", nullable=False)

    op.drop_column("sessions", "agent_b")
    op.drop_column("sessions", "agent_a")
    op.add_column(
        "sessions",
        sa.Column("agents_json", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "agents_json")
    op.add_column(
        "sessions",
        sa.Column("agent_a", sa.String(128), nullable=True),
    )
    op.add_column(
        "sessions",
        sa.Column("agent_b", sa.String(128), nullable=True),
    )

    op.alter_column("api_keys", "user_id", nullable=True)
    op.drop_column("api_keys", "expires_at")
    op.drop_column("api_keys", "last_used_at")
    op.drop_column("api_keys", "is_active")
    op.drop_column("api_keys", "name")
    op.drop_column("api_keys", "key_prefix")
    op.drop_column("api_keys", "key_hash")
    op.add_column(
        "api_keys",
        sa.Column("provider", sa.String(64), nullable=False),
    )
    op.add_column(
        "api_keys",
        sa.Column("key_value", sa.String(1024), nullable=False),
    )
