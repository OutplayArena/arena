"""Add durable versioned research telemetry.

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "t0u1v2w3x4y5"
down_revision = "s9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("player_id", sa.String(100), nullable=True),
        sa.Column("round_number", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.String(200), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "schema_version = 1", name="ck_telemetry_events_schema_version"
        ),
        sa.CheckConstraint(
            "event_type IN ('session.created', 'action.accepted', 'action.rejected', "
            "'round.completed', 'session.completed', 'session.failed')",
            name="ck_telemetry_events_event_type",
        ),
    )
    op.create_index(
        "ix_telemetry_events_session_id_id", "telemetry_events", ["session_id", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_telemetry_events_session_id_id", table_name="telemetry_events")
    op.drop_table("telemetry_events")
