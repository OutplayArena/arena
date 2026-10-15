"""Owner-only, terminal-session research reports and cursor-based trace exports."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arena.auth.dependencies import require_user
from arena.db import async_session, get_db
from arena.models.session import SessionModel
from arena.models.telemetry_event import TelemetryEvent
from arena.models.user import User
from arena.telemetry.capture import EVENT_TYPES, SCHEMA_VERSION
from arena.telemetry.report import (
    TERMINAL_STATUSES,
    ResearchReportBuilder,
    event_to_dict,
)

router = APIRouter(tags=["research telemetry"])
_CHUNK_SIZE = 500
TelemetryDb = Annotated[AsyncSession, Depends(get_db)]
ResearchUser = Annotated[User, Depends(require_user)]


async def _owned_terminal_session(
    session_id: str, db: AsyncSession, user: User
) -> SessionModel:
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    row = result.scalar_one_or_none()
    # Public leaderboard participation is not consent to publish private traces.
    if row is None or row.user_id is None or str(row.user_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Session not found")
    if row.status not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Research telemetry is available after the session completes or fails.",
        )
    return row


async def _last_event_id(db: AsyncSession, session_id: str) -> int:
    result = await db.execute(
        select(func.max(TelemetryEvent.id)).where(
            TelemetryEvent.session_id == session_id
        )
    )
    return result.scalar_one_or_none() or 0


async def _iter_events(
    db: AsyncSession,
    session_id: str,
    through_id: int,
) -> AsyncIterator[TelemetryEvent]:
    after_id = 0
    while after_id < through_id:
        result = await db.execute(
            select(TelemetryEvent)
            .where(
                TelemetryEvent.session_id == session_id,
                TelemetryEvent.id > after_id,
                TelemetryEvent.id <= through_id,
            )
            .order_by(TelemetryEvent.id)
            .limit(_CHUNK_SIZE)
        )
        rows = result.scalars().all()
        if not rows:
            break
        for event in rows:
            yield event
        after_id = rows[-1].id


async def _build_report(db: AsyncSession, row: SessionModel, through_id: int) -> dict:
    builder = ResearchReportBuilder(row)
    async for event in _iter_events(db, row.id, through_id):
        builder.add_event(event)
    return builder.finish()


@router.get("/session/{session_id}/telemetry")
async def get_telemetry_report(
    session_id: str,
    db: TelemetryDb,
    user: ResearchUser,
    response: Response,
):
    row = await _owned_terminal_session(session_id, db, user)
    through_id = await _last_event_id(db, row.id)
    response.headers["Cache-Control"] = "no-store"
    return await _build_report(db, row, through_id)


@router.get("/session/{session_id}/telemetry/events")
async def get_telemetry_events(
    session_id: str,
    db: TelemetryDb,
    user: ResearchUser,
    response: Response,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    event_type: str | None = Query(default=None),
):
    row = await _owned_terminal_session(session_id, db, user)
    if event_type is not None and event_type not in EVENT_TYPES:
        raise HTTPException(status_code=422, detail="Unknown telemetry event_type")
    query = select(TelemetryEvent).where(
        TelemetryEvent.session_id == row.id,
        TelemetryEvent.id > after_id,
    )
    if event_type is not None:
        query = query.where(TelemetryEvent.event_type == event_type)
    result = await db.execute(query.order_by(TelemetryEvent.id).limit(limit + 1))
    rows = result.scalars().all()
    page = rows[:limit]
    response.headers["Cache-Control"] = "no-store"
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": row.id,
        "events": [
            event_to_dict(event, row.player_tokens_json or {}) for event in page
        ],
        "next_after_id": page[-1].id if len(rows) > limit else None,
    }


@router.get("/session/{session_id}/telemetry/export")
async def export_telemetry(
    session_id: str,
    db: TelemetryDb,
    user: ResearchUser,
    format: Literal["json", "jsonl"] = Query(default="json"),
):
    row = await _owned_terminal_session(session_id, db, user)
    through_id = await _last_event_id(db, row.id)
    report = await _build_report(db, row, through_id)
    # The session identifier is user-controlled in the URL; use a fixed,
    # header-safe download name rather than interpolating it into a header.
    headers = {
        "Content-Disposition": 'attachment; filename="arena-telemetry.' + format + '"',
        "Cache-Control": "no-store",
    }
    if format == "json":
        return JSONResponse(content=report, headers=headers)

    async def records() -> AsyncIterator[str]:
        yield (
            json.dumps(
                {"record_type": "manifest", **report, "through_event_id": through_id},
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        )
        # Own the streaming connection so exports work across FastAPI versions
        # whose request dependency cleanup runs before the stream is consumed.
        async with async_session() as export_db:
            async for event in _iter_events(export_db, row.id, through_id):
                yield (
                    json.dumps(
                        {
                            "record_type": "event",
                            **event_to_dict(event, row.player_tokens_json or {}),
                        },
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                    + "\n"
                )

    return StreamingResponse(
        records(), media_type="application/x-ndjson", headers=headers
    )
