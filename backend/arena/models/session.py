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
    # False = private (only visible to the owning user); True = contributes to
    # the global public leaderboard, attributed with the owner's username.
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
