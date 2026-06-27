"""Error log model — captures unhandled server-side errors with a UUID.

Every unhandled exception that bubbles up to the global exception handler
in :mod:`arena.error_handler` gets a UUID, the traceback is stored here,
and the same UUID is returned to the user in the 500 response (JSON for
API requests, HTML for browser requests). The UUID is what the user
quotes when they open a GitHub issue; the maintainer can then look up
the full traceback in the ``error_logs`` table to debug.

Storing the traceback in the DB (rather than only logging to disk)
makes the data trivially queryable from the admin SQL prompt and
survives log rotation/retention. The 500 response never echoes the
traceback to the user; the response is intentionally minimal so we
don't leak paths, secrets, or internal state to the wire.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from arena.models.base import Base


class ErrorLog(Base):
    __tablename__ = "error_logs"

    # Public ID — the UUID we show in the 500 response and in GitHub
    # issue titles. Random per error; never collides in practice.
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # The HTTP method + path the user hit. Useful for reproducing.
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)

    # The exception class name and a short message. The full traceback
    # is in 'traceback'.
    exception_type: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    traceback: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Optional: client IP (X-Forwarded-For aware) and User-Agent. Kept
    # short so a single row stays under a few KB.
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Raw query string at error time — exclude from any user-visible
    # rendering; we never log secrets, so OAuth codes etc. shouldn't
    # appear here, but be careful if you change that.
    query_string: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Free-form JSON for any extra context we want to attach (user id
    # once we have it, request id, etc). Null for anonymous errors.
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
