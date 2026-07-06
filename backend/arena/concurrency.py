"""Game concurrency queue (#117): admission gate + background drainer.

The admission gate runs at session-creation time inside ``POST /experiment``.
It counts sessions with status ``ready`` or ``running`` (the "active" set)
globally and per-user against the limits stored in ``platform_settings``
(env-var fallback via :mod:`arena.settings`). When a limit would be
exceeded the new session is persisted with ``status='queued'`` and the
endpoint returns 202 with a queue position; otherwise it's business as
usual (``status='ready'``).

The drainer is a single in-process ``asyncio`` loop started from the
FastAPI lifespan (modeled on ``_gdpr_purge_loop``). Every few seconds it
recomputes free global slots, promotes the oldest ``queued`` rows to
``ready`` (respecting the per-user cap), and publishes a
``session:{id}:events`` -> ``session_promoted`` event so any SSE
subscriber wakes up immediately. With ``backend.replicas=1`` (the chart
default) there is exactly one drainer; horizontal scaling would need
leader election (out of scope for v1 — documented in the module docstring).

A queued session rejects action submits with 409 until it is promoted,
so a Too-eager agent can't race ahead of its slot.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arena.db import async_session as _async_session_factory
from arena.models.session import SessionModel
from arena.platform_settings import get_platform_setting

_log = logging.getLogger("arena.concurrency.queue")

# How often the drainer looks for promotable queued sessions. Short
# enough that a freshly-freed slot is filled within a poll, long enough
# that a single-replica backend isn't burning CPU.
_DRAIN_INTERVAL_SECONDS = 2.0

# Statuses that count toward the "active" set against the global and
# per-user caps. ``queued`` is the waiting state; ``ready``/``running``
# are active; ``completed``/``failed`` are terminal and free a slot.
_ACTIVE_STATUSES = ("ready", "running")


@dataclass(frozen=True)
class AdmissionDecision:
    queued: bool
    position: int  # 1-based; only meaningful when queued=True
    max_concurrent_sessions: int
    max_concurrent_sessions_per_user: int
    active_global: int
    active_user: int


async def evaluate_admission(
    db: AsyncSession,
    user_id: str,
) -> AdmissionDecision:
    """Decide whether the next session for *user_id* may start immediately.

    Reads the two concurrency knobs from ``platform_settings`` (env-fallback
    via :class:`arena.settings.Settings`) and counts active rows. Does not
    mutate the DB — the caller persists the new row with the chosen status.

    The queue is a soft limit, not a security boundary, so a failure in the
    count or settings lookup is logged and the request is admitted (fail-open)
    rather than blocking all game creation.
    """
    try:
        return await _evaluate_admission_inner(db, user_id)
    except Exception as exc:  # noqa: BLE001
        _log.debug("admission check failed; admitting (fail-open): %s", exc)
        # Use env-var defaults so the returned limits are still sensible.
        from arena.settings import get_settings

        s = get_settings()
        return AdmissionDecision(
            queued=False,
            position=0,
            max_concurrent_sessions=s.max_concurrent_sessions,
            max_concurrent_sessions_per_user=s.max_concurrent_sessions_per_user,
            active_global=0,
            active_user=0,
        )


async def _evaluate_admission_inner(
    db: AsyncSession,
    user_id: str,
) -> AdmissionDecision:
    max_global = await get_platform_setting(
        "max_concurrent_sessions", db, cast=int
    )
    max_per_user = await get_platform_setting(
        "max_concurrent_sessions_per_user", db, cast=int
    )

    # Coerce to a UUID object so the bind renders cleanly against the
    # PGUUID column (a plain str fails literal_binds in tests; asyncpg
    # coerces at runtime either way).
    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        user_uuid = user_id

    active_global = (
        await db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.status.in_(_ACTIVE_STATUSES))
        )
    ).scalar_one()

    active_user = (
        await db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(
                SessionModel.user_id == user_uuid,
                SessionModel.status.in_(_ACTIVE_STATUSES),
            )
        )
    ).scalar_one()

    should_queue = active_global >= max_global or active_user >= max_per_user
    if not should_queue:
        return AdmissionDecision(
            queued=False,
            position=0,
            max_concurrent_sessions=max_global,
            max_concurrent_sessions_per_user=max_per_user,
            active_global=active_global,
            active_user=active_user,
        )

    queued_count = (
        await db.execute(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.status == "queued")
        )
    ).scalar_one()
    return AdmissionDecision(
        queued=True,
        position=int(queued_count) + 1,
        max_concurrent_sessions=max_global,
        max_concurrent_sessions_per_user=max_per_user,
        active_global=active_global,
        active_user=active_user,
    )


async def promote_queued_sessions(db: AsyncSession, broker) -> int:
    """One drain cycle: promote queued sessions to ``ready`` as slots free.

    Returns the number of sessions promoted. Pure logic — caller supplies
    the DB session and broker so this is unit-testable without a real DB.
    Recomputes free global slots, walks the oldest queued rows, honours
    the per-user cap, and publishes a ``session_promoted`` event per row.
    """
    max_global = await get_platform_setting("max_concurrent_sessions", db, cast=int)
    max_per_user = await get_platform_setting(
        "max_concurrent_sessions_per_user", db, cast=int
    )

    active_global = int(
        (
            await db.execute(
                select(func.count())
                .select_from(SessionModel)
                .where(SessionModel.status.in_(_ACTIVE_STATUSES))
            )
        ).scalar_one()
    )
    free_slots = max_global - active_global
    if free_slots <= 0:
        return 0

    queued_rows = await db.execute(
        select(SessionModel)
        .where(SessionModel.status == "queued")
        .order_by(SessionModel.created_at.asc())
        .limit(free_slots)
    )
    promoted = 0
    for row in queued_rows.scalars():
        if row.user_id is not None:
            user_active = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(SessionModel)
                        .where(
                            SessionModel.user_id == row.user_id,
                            SessionModel.status.in_(_ACTIVE_STATUSES),
                        )
                    )
                ).scalar_one()
            )
            if user_active >= max_per_user:
                continue
        row.status = "ready"
        promoted += 1
        if broker is not None:
            await broker.publish(
                f"session:{row.id}:events",
                {
                    "event": "session_promoted",
                    "session_id": row.id,
                    "status": "ready",
                },
            )
        _log.info("Promoted queued session %s -> ready", row.id)
    if promoted:
        await db.commit()
    return promoted


async def _queue_drainer_loop(broker) -> None:
    """Background loop: promote ``queued`` sessions as slots free up.

    Delegates each cycle to :func:`promote_queued_sessions` with a fresh
    session from the global factory. Single-replica by default; horizontal
    scaling needs leader election (out of scope for v1).
    """
    while True:
        try:
            async with _async_session_factory() as db:
                await promote_queued_sessions(db, broker)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.warning("Queue drainer loop error", exc_info=True)
        await asyncio.sleep(_DRAIN_INTERVAL_SECONDS)


__all__ = [
    "AdmissionDecision",
    "evaluate_admission",
    "promote_queued_sessions",
    "_queue_drainer_loop",
]