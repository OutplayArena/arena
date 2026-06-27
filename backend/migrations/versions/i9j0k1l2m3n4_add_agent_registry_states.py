"""add agent_registry_states table

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-06-27 08:45:00.000000

The ``AgentRegistryState`` model has been in the codebase since
``d4569ee22af1`` but no migration ever created the underlying
``agent_registry_states`` table. The startup loader in
:func:`arena.main._load_registries_from_db` therefore logged a
``relation does not exist`` warning on every fresh install and
fell back to an empty in-memory registry, which silently broke
the cross-restart leaderboard persistence path.

Add the table so the model and the schema agree.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_registry_states",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("state_json", postgresql.JSONB, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_registry_states")
