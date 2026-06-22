from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from arena.models.base import Base


class AgentRegistryState(Base):
    __tablename__ = "agent_registry_states"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
