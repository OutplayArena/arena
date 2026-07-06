"""add matchmaking tables

Revision ID: s9t0u1v2w3x4
Revises: q7r8s9t0u1v2
Create Date: 2026-07-06 00:00:00.000000

Adds the matchmaking data model (#96): ``matches`` (the waiting-phase
lobby container) + ``match_participants`` (join table tracking who claimed
which slot). Also adds a nullable ``match_id`` backref on ``sessions`` so
the participant-hardening check on state/observation endpoints can look
up which match spawned a given session.

A ``SessionModel`` row is created only when a match fills and the game
starts; the match row persists as a back-reference. The unique constraints
on ``match_participants`` ((match_id, slot) and (match_id, user_id)) make
the join endpoint race-safe at the DB level.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 's9t0u1v2w3x4'
down_revision = 'q7r8s9t0u1v2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("host_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("game_type", sa.String(length=64), nullable=False),
        sa.Column("config_json", postgresql.JSONB, nullable=False),
        sa.Column("config_hash", sa.String(length=128), nullable=False),
        sa.Column("agents_json", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="waiting"),
        sa.Column("invite_code", sa.String(length=32), nullable=False),
        sa.Column("total_slots", sa.Integer, nullable=False),
        sa.Column("filled_slots", sa.Integer, nullable=False, server_default="0"),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_matches_invite_code", "matches", ["invite_code"])

    op.create_table(
        "match_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "match_id",
            sa.String(length=36),
            sa.ForeignKey("matches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot", sa.String(length=16), nullable=False),
        sa.Column("player_token", sa.String(length=256), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("match_id", "slot", name="uq_match_slot"),
        sa.UniqueConstraint("match_id", "user_id", name="uq_match_user"),
    )

    op.add_column(
        "sessions",
        sa.Column("match_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "match_id")
    op.drop_table("match_participants")
    op.drop_constraint("matches", "uq_matches_invite_code", type_="unique")
    op.drop_table("matches")