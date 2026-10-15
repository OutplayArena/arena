"""Durable, versioned research events. Insert events; never update them."""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from arena.models.base import Base


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    __table_args__ = (
        Index("ix_telemetry_events_session_id_id", "session_id", "id"),
        CheckConstraint(
            "schema_version = 1", name="ck_telemetry_events_schema_version"
        ),
        CheckConstraint(
            "event_type IN ('session.created', 'action.accepted', 'action.rejected', "
            "'round.completed', 'session.completed', 'session.failed')",
            name="ck_telemetry_events_event_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    player_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    round_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)


@event.listens_for(TelemetryEvent, "before_update")
def _prevent_event_update(mapper, connection, target) -> None:
    raise ValueError("telemetry events are immutable; append a new event instead")
