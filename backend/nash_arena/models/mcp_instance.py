from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from nash_arena.models.base import Base


class McpInstance(Base):
    __tablename__ = "mcp_instances"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=lambda: None
    )
    key_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("mcp_auth_keys.id"), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="starting")
    runtime: Mapped[str] = mapped_column(String(20), nullable=False, default="k8s")
    container_name: Mapped[str] = mapped_column(String(128), nullable=False)
    dns_name: Mapped[str] = mapped_column(String(256), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=8001)
    public_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
