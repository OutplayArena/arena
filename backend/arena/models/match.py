"""Matchmaking models for cross-user game sessions (#96).

A ``Match`` is a waiting-phase container: it lives in the lobby until all
open slots are claimed, at which point a real ``SessionModel`` row is
created (via :class:`GameSession.create`) and the match transitions to
``running``. The match row persists afterwards as a back-reference
(``SessionModel.match_id``) so participant hardening can look it up.

``MatchParticipant`` is the join table: one row per (match, user, slot).
A unique constraint on ``(match_id, slot)`` makes the join endpoint
race-safe at the DB level (two concurrent joins → one INSERT succeeds,
the other gets an IntegrityError → 409). A unique constraint on
``(match_id, user_id)`` prevents the same user from claiming two slots
in the same match.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from arena.models.base import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    host_user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    game_type: Mapped[str] = mapped_column(String(64), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    agents_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # waiting | ready | running | cancelled | expired
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")

    invite_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    total_slots: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_slots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Pre-allocated so the host's nks_ token can be derived immediately.
    # Set when the game starts.
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class MatchParticipant(Base):
    __tablename__ = "match_participants"
    __table_args__ = (
        UniqueConstraint("match_id", "slot", name="uq_match_slot"),
        UniqueConstraint("match_id", "user_id", name="uq_match_user"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    match_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    # The host pre-mints the host's token; joiners mint theirs on claim.
    player_token: Mapped[str] = mapped_column(String(256), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["Match", "MatchParticipant"]