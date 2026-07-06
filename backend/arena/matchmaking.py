"""Cross-user matchmaking / lobby logic (#96).

A ``Match`` is the waiting-phase lobby container. The host creates one
with their chosen game config and marks one or more opponent slots as
open; each open slot is a ``MatchParticipant`` to be claimed. The join
endpoint is race-safe via a DB unique constraint on ``(match_id, slot)``.
When all slots are filled, a real ``SessionModel`` is created
(pre-allocated session_id → deterministic nks_ token derivation) and the
match transitions to ``running``.

A background sweeper loop (modeled on ``_gdpr_purge_loop``) expires
matches past their TTL, notifies waiters via Redis pub/sub, and cleans
up participant rows.

Local mode (no OAuth providers) disables all endpoints with 403 —
matchmaking is intrinsically multi-user.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from arena.auth.session_key import derive_session_key
from arena.db import async_session as _async_session_factory
from arena.models.match import Match, MatchParticipant
from arena.platform_settings import get_platform_setting
from arena.session import GameSession
from arena.settings import get_settings

_log = logging.getLogger("arena.matchmaking")


def _generate_invite_code() -> str:
    return secrets.token_urlsafe(16)


def _lobby_match_summary(m: Match, host_name: str | None = None) -> dict:
    return {
        "id": m.id,
        "host_user_id": str(m.host_user_id),
        "host_name": host_name,
        "game_type": m.game_type,
        "status": m.status,
        "total_slots": m.total_slots,
        "filled_slots": m.filled_slots,
        "open_slots": m.total_slots - m.filled_slots,
        "invite_code": m.invite_code,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "started_at": m.started_at.isoformat() if m.started_at else None,
        "expires_at": m.expires_at.isoformat() if m.expires_at else None,
    }


def _match_detail(m: Match, participants: list[MatchParticipant], host_name: str | None = None) -> dict:
    detail = _lobby_match_summary(m, host_name)
    detail["participants"] = [
        {
            "slot": p.slot,
            "user_id": str(p.user_id),
            "joined_at": p.joined_at.isoformat() if p.joined_at else None,
        }
        for p in participants
    ]
    if m.session_id:
        detail["session_id"] = m.session_id
    return detail


async def create_lobby_match(
    db: AsyncSession,
    *,
    host_user_id: UUID,
    game_type: str,
    config: any,
    config_hash: str,
    agents: dict[str, str] | None = None,
    ttl_hours: int | None = None,
) -> tuple[Match, str]:
    """Create a new waiting match and the host's participant row.

    Returns (match, host_token). The host's ``nks_`` token is derived from
    the pre-allocated session_id so it's valid the moment the match fills
    and the session is created. The host claims the first slot (``A``).
    """
    if ttl_hours is None:
        ttl_hours = await get_platform_setting(
            "matchmaking_ttl_hours", db, cast=int
        )
    if ttl_hours == 0:  # env fallback returned None cast to int
        from arena.settings import get_settings

        ttl_hours = get_settings().matchmaking_ttl_hours

    now = datetime.now(timezone.utc)
    match_id = str(__import__("uuid").uuid4())
    pre_session_id = str(__import__("uuid").uuid4())
    player_ids = config.player_ids()
    total_slots = len(player_ids)
    host_slot = player_ids[0] if player_ids else "A"
    host_token = derive_session_key(pre_session_id, host_slot)

    match = Match(
        id=match_id,
        host_user_id=host_user_id,
        game_type=game_type,
        config_json=config.to_dict() if hasattr(config, "to_dict") else config,
        config_hash=config_hash,
        agents_json=agents,
        status="waiting",
        invite_code=_generate_invite_code(),
        total_slots=total_slots,
        filled_slots=1,
        session_id=None,
        created_at=now,
        expires_at=now + timedelta(hours=ttl_hours),
    )
    db.add(match)

    host_participant = MatchParticipant(
        match_id=match_id,
        user_id=host_user_id,
        slot=host_slot,
        player_token=host_token,
    )
    db.add(host_participant)
    await db.commit()
    _log.info("Match %s created (host=%s, game=%s, slots=%d)", match_id, host_user_id, game_type, total_slots)
    return match, host_token


async def list_open_matches(db: AsyncSession) -> list[dict]:
    """Return all matches currently waiting for opponents."""
    result = await db.execute(
        select(Match)
        .where(Match.status == "waiting")
        .order_by(Match.created_at.asc())
    )
    matches = result.scalars().all()
    summaries = []
    for m in matches:
        host_name = None
        try:
            from arena.models.user import User

            host_r = await db.execute(select(User).where(User.id == m.host_user_id))
            host = host_r.scalar_one_or_none()
            if host:
                host_name = host.username or host.name
        except Exception:
            pass
        summaries.append(_lobby_match_summary(m, host_name))
    return summaries


async def get_match_detail(db: AsyncSession, match_id: str) -> dict | None:
    m = (
        await db.execute(select(Match).where(Match.id == match_id))
    ).scalar_one_or_none()
    if m is None:
        return None
    parts_r = await db.execute(
        select(MatchParticipant)
        .where(MatchParticipant.match_id == match_id)
        .order_by(MatchParticipant.joined_at.asc())
    )
    participants = parts_r.scalars().all()
    host_name = None
    try:
        from arena.models.user import User

        host_r = await db.execute(select(User).where(User.id == m.host_user_id))
        host = host_r.scalar_one_or_none()
        if host:
            host_name = host.username or host.name
    except Exception:
        pass
    return _match_detail(m, list(participants), host_name)


async def join_match(
    db: AsyncSession,
    *,
    match_id: str,
    user_id: UUID,
    slot: str | None = None,
) -> tuple[str, str, bool, Match]:
    """Claim an open slot in a match. Race-safe.

    Returns (player_token, slot_claimed, match_filled, match). Raises
    ``ValueError`` with a message suitable for an HTTPException detail.
    The DB unique constraints on (match_id, slot) and (match_id, user_id)
    are the race-safety boundary: concurrent INSERTs → one succeeds, the
    other gets IntegrityError → 409.
    """
    m = (
        await db.execute(select(Match).where(Match.id == match_id))
    ).scalar_one_or_none()
    if m is None:
        raise ValueError("match not found")
    if m.status != "waiting":
        raise ValueError(f"match is not open for joining (status={m.status})")
    if datetime.now(timezone.utc) > m.expires_at:
        raise ValueError("match has expired")


    existing = (
        await db.execute(
            select(MatchParticipant).where(
                MatchParticipant.match_id == match_id,
                MatchParticipant.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("user already joined this match")

    taken_slots = {
        p.slot
        for p in (
            await db.execute(
                select(MatchParticipant).where(
                    MatchParticipant.match_id == match_id
                )
            )
        ).scalars().all()
    }

    config_dict = m.config_json
    from arena.game_registry import GameRegistry

    config = GameRegistry().config_from_request(config_dict)
    all_slots = config.player_ids()
    open_slots = [s for s in all_slots if s not in taken_slots]
    if not open_slots:
        raise ValueError("match is full")

    if slot is None:
        slot = open_slots[0]
    elif slot not in open_slots:
        raise ValueError(
            f"slot '{slot}' is taken or invalid; open slots: {open_slots}"
        )

    if not m.session_id:
        m.session_id = str(__import__("uuid").uuid4())

    token = derive_session_key(m.session_id, slot)
    participant = MatchParticipant(
        match_id=match_id,
        user_id=user_id,
        slot=slot,
        player_token=token,
    )
    db.add(participant)
    m.filled_slots = m.filled_slots + 1
    match_filled = m.filled_slots >= m.total_slots

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("slot was claimed by another user") from exc

    if match_filled:
        await _start_match_session(db, m, config)

    return token, slot, match_filled, m


async def _start_match_session(db: AsyncSession, m: Match, config: any) -> None:
    """Create the SessionModel for a filled match and transition to running."""
    from arena.game_registry import GameRegistry

    game = GameRegistry().game_from_config(config)
    session = GameSession.create(
        config,
        game=game,
        locked=False,
        agents=m.agents_json,
        session_id=m.session_id,
    )
    await session.save_new(
        db,
        user_id=str(m.host_user_id),
        agents=m.agents_json,
        match_id=m.id,
    )
    m.status = "running"
    m.started_at = datetime.now(timezone.utc)
    await db.commit()
    _log.info("Match %s started → session %s", m.id, m.session_id)


async def cancel_match(db: AsyncSession, *, match_id: str, user_id: UUID) -> bool:
    """Cancel a waiting match. Only the host can cancel."""
    m = (
        await db.execute(select(Match).where(Match.id == match_id))
    ).scalar_one_or_none()
    if m is None:
        return False
    if m.host_user_id != user_id:
        raise ValueError("only the host can cancel a match")
    if m.status != "waiting":
        raise ValueError(f"match is not waiting (status={m.status})")
    m.status = "cancelled"
    await db.commit()
    _log.info("Match %s cancelled by host %s", match_id, user_id)
    return True


async def expire_stale_matches(db: AsyncSession, broker) -> int:
    """Expire matches past their TTL. Returns the count expired.

    Notifies waiters via Redis pub/sub so ``wait_for_opponent`` SSE
    subscribers get a ``match_expired`` event and can bail out.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Match).where(
            Match.status == "waiting",
            Match.expires_at < now,
        )
    )
    stale = result.scalars().all()
    expired = 0
    for m in stale:
        m.status = "expired"
        expired += 1
        if broker is not None:
            try:
                await broker.publish(
                    f"match:{m.id}:events",
                    {
                        "event": "match_expired",
                        "match_id": m.id,
                    },
                )
            except Exception:
                _log.debug("broker.publish failed for match %s expiry", m.id, exc_info=True)
        _log.info("Match %s expired (TTL)", m.id)
    if expired:
        await db.commit()
    return expired


async def _matchmaking_sweeper_loop(broker) -> None:
    """Background loop: expire stale matches every interval.

    Mirrors ``_gdpr_purge_loop``. Single-replica by chart default.
    """
    while True:
        try:
            async with _async_session_factory() as db:
                await expire_stale_matches(db, broker)
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.warning("Matchmaking sweeper loop error", exc_info=True)
        try:
            interval = get_settings().matchmaking_sweeper_interval_seconds
        except Exception:
            interval = 3600
        await asyncio.sleep(max(60, interval))


async def is_match_participant(
    db: AsyncSession, *, session_id: str, user_id: UUID | None
) -> bool:
    """Check whether *user_id* is a participant in the match that spawned *session_id*.

    Used by the state/observation endpoints' participant-hardening check.
    Returns True if the session has a ``match_id`` and the user is a
    participant in that match (including the host). Returns True (open) when
    the session has no ``match_id`` (preserves the legacy non-matchmaking
    behaviour — the nks_ token remains the access capability).
    """
    if user_id is None:
        return False
    from arena.models.session import SessionModel

    row = (
        await db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
    ).scalar_one_or_none()
    if row is None or not row.match_id:
        return True
    p = (
        await db.execute(
            select(MatchParticipant).where(
                MatchParticipant.match_id == row.match_id,
                MatchParticipant.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    return p is not None


__all__ = [
    "create_lobby_match",
    "list_open_matches",
    "get_match_detail",
    "join_match",
    "cancel_match",
    "expire_stale_matches",
    "_matchmaking_sweeper_loop",
    "is_match_participant",
]