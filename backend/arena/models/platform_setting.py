"""Platform-wide runtime settings, stored in the database.

A simple key/value table editable at runtime via the admin dashboard
(#116). The concurrency-queue admission gate (#117) reads the
``max_concurrent_sessions`` and ``max_concurrent_sessions_per_user`` keys
from here, falling back to env-var defaults (see :mod:`arena.settings`)
when a row is absent.

Only textual values are stored; callers coerce to the needed type via
``get_platform_setting``'s ``cast`` parameter. This keeps the schema
migration-free when new settings are added — a new key is just a new row.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from arena.models.base import Base


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )


__all__ = ["PlatformSetting"]