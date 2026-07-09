from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from arena.models.base import Base


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    player_tokens_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    agents_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    messages_json: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    wandb_run_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # W&B project/entity/run_name/tags requested at session creation.
    # Stored here so stateless workers can log at game-end without re-parsing
    # the original request.  Never contains an API key.
    wandb_config_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # False = private (only visible to the owning user); True = contributes to
    # the global public leaderboard, attributed with the owner's username.
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Backref to the Match that spawned this session (#96). Set when a
    # matchmaking match fills and the session is created. Used by the
    # participant-hardening check on state/observation endpoints.
    match_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
