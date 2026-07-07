"""add platform_settings table

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-07-06 00:00:00.000000

Adds a key/value ``platform_settings`` table editable at runtime via the
admin dashboard (#116). Seeded with the concurrency-queue defaults from
#117 so the admission gate has values to read before any admin touches
the UI. New settings can be added later without a migration — a new key
is just a new row.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'q7r8s9t0u1v2'
down_revision = 'p6q7r8s9t0u1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Seed the concurrency-queue defaults so #117's admission gate has a
    # value to read before any admin edits the row. Values mirror the
    # pydantic-settings defaults in arena.settings.Settings.
    op.bulk_insert(
        sa.table(
            "platform_settings",
            sa.column("key", sa.String),
            sa.column("value", sa.Text),
        ),
        [
            {"key": "max_concurrent_sessions", "value": "50"},
            {"key": "max_concurrent_sessions_per_user", "value": "5"},
            {"key": "login_enabled", "value": "true"},
        ],
    )


def downgrade() -> None:
    op.drop_table("platform_settings")