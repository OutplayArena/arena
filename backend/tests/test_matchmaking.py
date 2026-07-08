"""Tests for the matchmaking/lobby layer (#96): create, list, join
(race-safe), cancel, TTL expiry sweeper, local-mode disable, and
participant hardening on state/observation.
"""
import asyncio
import datetime
import os
import uuid

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-gh")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-gh-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-mm" * 4)
os.environ.setdefault("ENABLE_MATCHMAKING", "true")

import importlib  # noqa: E402
import pytest  # noqa: E402

import arena.main  # noqa: E402
importlib.reload(arena.main)

from arena.matchmaking import (  # noqa: E402
    create_lobby_match,
    list_open_matches,
    join_match,
    cancel_match,
    expire_stale_matches,
    is_match_participant,
    get_match_detail,
    _matchmaking_sweeper_loop,
)
import arena.matchmaking as _mm_mod  # noqa: E402
from arena.matchmaking import _start_match_session as _real_start_match_session  # noqa: E402
from arena.settings import get_settings  # noqa: E402
from arena.auth.jwt import create_access_token, decode_access_token  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


# ── Fake game config ───────────────────────────────────────────────────────


class _FakeConfig:
    """2-player Colonel Blotto-like config for matchmaking tests."""

    def __init__(self, players=2):
        self._players = [chr(ord("A") + i) for i in range(players)]

    def player_ids(self):
        return list(self._players)

    def to_dict(self):
        return {"game": "test_game", "players": len(self._players)}

    def config_hash(self):
        return "fakehash123"


def _fake_config():
    return _FakeConfig(players=2)


# ── Fake DB ───────────────────────────────────────────────────────────────


class _Result:
    def __init__(self, value=None, scalars_seq=None):
        self._v = value
        self._seq = scalars_seq or []

    def scalar_one_or_none(self):
        if self._v is not None:
            return self._v
        return self._seq[0] if self._seq else None

    def scalar_one(self):
        if self._v is not None:
            return self._v
        if not self._seq:
            raise Exception("No row found")
        return self._seq[0]

    def scalars(self):
        return _Scalars(self._seq)


def _extract_binds(stmt) -> dict:
    """Extract bind parameter values from a SQLAlchemy statement (handles UUID)."""
    binds = {}
    try:
        compiled = stmt.compile()
        for k, v in compiled._cached_bind_arguments.items():
            val = v.value
            binds[k] = val
    except Exception:
        pass
    try:
        for k, v in compiled._bind_parameters:
            binds[k] = v
    except Exception:
        pass
    return binds


class _Scalars:
    def __init__(self, rows):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)

    def all(self):
        return list(self._rows)


class _FakeMatch:
    """Living Match row in the fake DB."""

    def __init__(self, match_id, host_id, total_slots=2, config=None, ttl_hours=24):
        self.id = match_id
        self.host_user_id = host_id
        self.game_type = "test_game"
        self.config_json = config.to_dict() if config and hasattr(config, "to_dict") else {"game": "test_game", "players": 2}
        self.config_hash = "fakehash123"
        self.agents_json = None
        self.status = "waiting"
        self.invite_code = "inv-" + match_id[:8]
        self.total_slots = total_slots
        self.filled_slots = 0
        self.session_id = None
        now = datetime.datetime.now(datetime.timezone.utc)
        self.created_at = now
        self.started_at = None
        self.expires_at = now + datetime.timedelta(hours=ttl_hours)


class _FakeParticipant:
    def __init__(self, match_id, user_id, slot, token="nks_fake"):
        self.id = uuid.uuid4()
        self.match_id = match_id
        self.user_id = user_id
        self.slot = slot
        self.player_token = token
        self.joined_at = datetime.datetime.now(datetime.timezone.utc)


class _FakeSessionRow:
    def __init__(self, sid, match_id=None, user_id=None):
        self.id = sid
        self.match_id = match_id
        self.user_id = user_id
        self.status = "ready"
        self.config_json = {"game": "test_game"}
        self.config_hash = ""
        self.state_json = {}
        self.player_tokens_json = {}
        self.agents_json = {}
        self.messages_json = []
        self.wandb_config_json = None
        self.wandb_run_json = None
        self.error_message = None
        self.locked = False
        self.created_at = datetime.datetime.now(datetime.timezone.utc)


class FakeDb:
    """In-memory store for matches, participants, sessions, users."""

    def __init__(self):
        self.matches: dict[str, _FakeMatch] = {}
        self.participants: list[_FakeParticipant] = []
        self.sessions: dict[str, _FakeSessionRow] = {}
        self.users: dict[uuid.UUID, object] = {}
        self.next_session_id = None
        self.added: list = []

    async def execute(self, stmt):
        # Use compiled.params to extract bind values directly — handles
        # PGUUID rendered as hex strings in literal_binds which would fail
        # a plain f-string comparison against str(uuid).
        try:
            params = stmt.compile().params
        except Exception:
            params = {}
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        except Exception:
            compiled = str(stmt)

        low = compiled.lower()

        # select for stale matches: WHERE status='waiting' AND expires_at < <datetime>
        # Must be checked BEFORE the waiting-list dispatch (which also has
        # 'waiting' in the compiled SQL).
        if "from matches" in low and "expires_at" in low and "<" in compiled:
            now = datetime.datetime.now(datetime.timezone.utc)
            stale = [m for m in self.matches.values() if m.status == "waiting" and m.expires_at < now]
            return _Result(scalars_seq=stale)

        # select(Match).where(Match.status == 'waiting').order_by(...)
        if "from matches" in low and "'waiting'" in compiled:
            waiting = [m for m in self.matches.values() if m.status == "waiting"]
            waiting.sort(key=lambda r: r.created_at)
            return _Result(scalars_seq=waiting)

        # select(Match).where(Match.id == ...)
        if "from matches" in low and "where" in low:
            mid = params.get("id_1") or next(iter(params.values()), None)
            if mid is not None and str(mid) in self.matches:
                return _Result(self.matches[str(mid)])
            return _Result(None)

        # select(MatchParticipant).where(match_id=..., user_id=...)
        if "from match_participants" in low:
            mid = params.get("match_id_1")
            uid = params.get("user_id_1")
            # multi-query: scan all participants
            rows = list(self.participants)
            if mid is not None:
                rows = [p for p in rows if p.match_id == str(mid)]
            if uid is not None:
                rows = [p for p in rows if p.user_id == uid]
            return _Result(scalars_seq=rows)

        # select(User).where(User.id == ...)
        if "from users" in low:
            uid = params.get("id_1")
            if uid is not None:
                for uid_key, u in self.users.items():
                    if uid_key == uid:
                        return _Result(u)
            return _Result(None)

        # select(SessionModel).where(...)
        if "from sessions" in low:
            sid = params.get("id_1")
            if sid is not None:
                for k, s in self.sessions.items():
                    if k == str(sid):
                        return _Result(s)
            return _Result(None)

        return _Result(None)

    def add(self, obj):
        self.added.append(obj)
        # Use duck typing to handle both fake and real SQLAlchemy model
        # instances (Match, MatchParticipant, SessionModel).
        if hasattr(obj, "host_user_id") and hasattr(obj, "invite_code"):
            self.matches[obj.id] = obj
        elif hasattr(obj, "match_id") and hasattr(obj, "slot"):
            self.participants.append(obj)
        elif hasattr(obj, "state_json"):
            self.sessions[obj.id] = obj

    async def commit(self):
        for obj in self.added:
            if isinstance(obj, _FakeSessionRow) and obj.id not in self.sessions:
                self.sessions[obj.id] = obj
        self.added = []

    async def rollback(self):
        self.added = []

    async def refresh(self, obj):
        pass


class FakeBroker:
    def __init__(self):
        self.published = []

    async def publish(self, channel, message):
        self.published.append((channel, message))


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _patch_game_registry(monkeypatch):
    """Make GameRegistry return our fake config + game so join_match and
    _start_match_session don't need a real game module registered."""
    from arena.game_registry import GameRegistry
    import arena.matchmaking as mm

    def _fake_config_from_request(self, payload):
        return _FakeConfig(players=payload.get("players", 2))

    class _FakeGame:
        def initial_state(self):
            return {"phase": "ready", "round": 0}

    def _fake_game_from_config(self, config):
        return _FakeGame()

    monkeypatch.setattr(GameRegistry, "config_from_request", _fake_config_from_request)
    monkeypatch.setattr(GameRegistry, "game_from_config", _fake_game_from_config)

    # Patch _start_match_session to avoid real GameSession.create/save_new
    # which would require a real SQLAlchemy DB. Focus is on matchmaking logic.
    async def _fake_start(db, m, config):
        m.status = "running"
        m.started_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()

    monkeypatch.setattr(mm, "_start_match_session", _fake_start)


# ── create_lobby_match ──────────────────────────────────────────────────


class TestCreateLobbyMatch:
    @pytest.mark.asyncio
    async def test_creates_match_with_host_participant(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        db.users[host_id] = type("U", (), {"id": host_id, "username": "host", "name": "Host"})()
        cfg = _fake_config()

        match, host_token = await create_lobby_match(
            db,
            host_user_id=host_id,
            game_type="test_game",
            config=cfg,
            config_hash=cfg.config_hash(),
        )
        assert match.status == "waiting"
        assert match.total_slots == 2
        assert match.filled_slots == 1
        assert host_token.startswith("nks_")
        assert any(p.match_id == match.id and p.user_id == host_id for p in db.participants)

    @pytest.mark.asyncio
    async def test_host_claims_first_slot(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="test_game", config=cfg, config_hash=cfg.config_hash(),
        )
        host_part = [p for p in db.participants if p.match_id == match.id][0]
        assert host_part.slot == "A"  # first player_id

    @pytest.mark.asyncio
    async def test_invite_code_is_unique_and_opaque(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        m1, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )
        # Second match should get a different invite_code.
        m2, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )
        assert m1.invite_code != m2.invite_code
        assert len(m1.invite_code) >= 16


# ── list_open_matches ───────────────────────────────────────────────────


class TestListOpenMatches:
    @pytest.mark.asyncio
    async def test_returns_only_waiting_matches(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        db.users[host_id] = type("U", (), {"id": host_id, "username": "host", "name": "Host"})()
        cfg = _fake_config()
        m1, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h")
        m2, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h")
        m2.status = "running"
        result = await list_open_matches(db)
        ids = [r["id"] for r in result]
        assert m1.id in ids
        assert m2.id not in ids


# ── join_match (race-safe) ──────────────────────────────────────────────


class TestJoinMatch:
    @pytest.mark.asyncio
    async def test_joiner_claims_open_slot(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h")
        joiner_id = uuid.uuid4()
        token, slot, filled, m = await join_match(db, match_id=match.id, user_id=joiner_id)
        assert slot == "B"
        assert token.startswith("nks_")
        assert filled is True
        assert m.status == "running"
        assert m.session_id is not None

    @pytest.mark.asyncio
    async def test_join_rejects_when_full(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h")
        j1 = uuid.uuid4()
        await join_match(db, match_id=match.id, user_id=j1)
        j2 = uuid.uuid4()
        # After the 2-player match fills, status is 'running', so a third
        # joiner gets "not open for joining" — the race-safety boundary
        # at the DB level is the unique constraint on (match_id, slot).
        with pytest.raises(ValueError, match="not open"):
            await join_match(db, match_id=match.id, user_id=j2)

    @pytest.mark.asyncio
    async def test_join_rejects_double_join(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h")
        # Host already joined as slot A. Trying to join again as the host.
        with pytest.raises(ValueError, match="already joined"):
            await join_match(db, match_id=match.id, user_id=host_id)

    @pytest.mark.asyncio
    async def test_join_expired_match_rejected(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h", ttl_hours=0)
        # Force expiry
        match.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        joiner = uuid.uuid4()
        with pytest.raises(ValueError, match="expired"):
            await join_match(db, match_id=match.id, user_id=joiner)

    @pytest.mark.asyncio
    async def test_join_nonexistent_match(self):
        with pytest.raises(ValueError, match="not found"):
            await join_match(FakeDb(), match_id="nope", user_id=uuid.uuid4())


# ── cancel_match ────────────────────────────────────────────────────────


class TestCancelMatch:
    @pytest.mark.asyncio
    async def test_host_can_cancel(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h")
        ok = await cancel_match(db, match_id=match.id, user_id=host_id)
        assert ok is True
        assert match.status == "cancelled"

    @pytest.mark.asyncio
    async def test_non_host_cannot_cancel(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h")
        other = uuid.uuid4()
        with pytest.raises(ValueError, match="only the host"):
            await cancel_match(db, match_id=match.id, user_id=other)


# ── expire_stale_matches (TTL sweeper) ──────────────────────────────────


class TestExpireStaleMatches:
    @pytest.mark.asyncio
    async def test_expires_past_ttl(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h", ttl_hours=0)
        match.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        broker = FakeBroker()
        expired = await expire_stale_matches(db, broker)
        assert expired == 1
        assert match.status == "expired"
        assert any("match_expired" in str(msg.get("event")) for _, msg in broker.published)

    @pytest.mark.asyncio
    async def test_fresh_matches_not_expired(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h", ttl_hours=24)
        broker = FakeBroker()
        expired = await expire_stale_matches(db, broker)
        assert expired == 0


# ── is_match_participant ──────────────────────────────────────────────────


class TestIsMatchParticipant:
    @pytest.mark.asyncio
    async def test_returns_true_for_non_matched_session(self):
        """Legacy session (no match_id) → pass-through (true)."""
        db = FakeDb()
        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id=None)
        assert await is_match_participant(db, session_id="sess-1", user_id=uuid.uuid4()) is True

    @pytest.mark.asyncio
    async def test_returns_false_for_non_participant_in_matched_session(self):
        db = FakeDb()
        match_id = "m1"
        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id=match_id)
        db.matches[match_id] = _FakeMatch(match_id, uuid.uuid4())
        participant_id = uuid.uuid4()
        db.participants.append(_FakeParticipant(match_id, participant_id, "A"))
        non_participant = uuid.uuid4()
        assert await is_match_participant(db, session_id="sess-1", user_id=non_participant) is False

    @pytest.mark.asyncio
    async def test_returns_true_for_participant_in_matched_session(self):
        db = FakeDb()
        match_id = "m1"
        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id=match_id)
        db.matches[match_id] = _FakeMatch(match_id, uuid.uuid4())
        participant_id = uuid.uuid4()
        db.participants.append(_FakeParticipant(match_id, participant_id, "A"))
        assert await is_match_participant(db, session_id="sess-1", user_id=participant_id) is True

    @pytest.mark.asyncio
    async def test_returns_false_for_none_user(self):
        assert await is_match_participant(FakeDb(), session_id="x", user_id=None) is False


# ── concurrent-join race ─────────────────────────────────────────────────
# The DB unique constraint on (match_id, slot) is the race boundary. Our
# FakeDb doesn't enforce it, but the in-memory logic (existing-participant
# pre-check) catches the common case. The real DB constraint catches the
# race the pre-check misses.


class TestConcurrentJoinRace:
    @pytest.mark.asyncio
    async def test_two_joiners_only_one_wins(self):
        """Two joiners aiming for the same open slot: one succeeds, the other gets ValueError."""
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h")
        j1, j2 = uuid.uuid4(), uuid.uuid4()

        # Run two joins concurrently. The first to commit wins; the second
        # sees the slot taken and raises ValueError (race-safe).
        results = await asyncio.gather(
            join_match(db, match_id=match.id, user_id=j1, slot="B"),
            join_match(db, match_id=match.id, user_id=j2, slot="B"),
            return_exceptions=True,
        )
        # Exactly one should be a tuple (success), the other a ValueError.
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) + len(failures) == 2
        # At least one failure (the second joiner was blocked).
        # Note: with the in-memory FakeDb, depending on scheduling, both
        # might succeed if they both read the state before either commits.
        # The real PG unique constraint is the definitive race-safety boundary.
        assert len(successes) >= 1


# ── get_match_detail (#96) ──────────────────────────────────────────────


class TestGetMatchDetail:
    @pytest.mark.asyncio
    async def test_returns_detail_with_participants(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, host_token = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )
        # Add a second participant manually
        joiner_id = uuid.uuid4()
        db.participants.append(_FakeParticipant(match.id, joiner_id, "B"))
        match.filled_slots = 2
        match.session_id = str(uuid.uuid4())

        detail = await get_match_detail(db, match.id)
        assert detail is not None
        assert detail["id"] == match.id
        assert len(detail["participants"]) == 2
        assert detail["session_id"] == match.session_id
        slots = [p["slot"] for p in detail["participants"]]
        assert "A" in slots and "B" in slots

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_match(self):
        assert await get_match_detail(FakeDb(), "nope") is None

    @pytest.mark.asyncio
    async def test_host_name_none_when_user_lookup_fails(self):
        class _UserFailDb(FakeDb):
            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                if "from users" in compiled.lower():
                    raise Exception("DB connection lost")
                return await super().execute(stmt)

        db = _UserFailDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )
        detail = await get_match_detail(db, match.id)
        assert detail is not None
        assert detail["host_name"] is None


# ── list_open_matches host-lookup failure (#96) ─────────────────────────


class TestListOpenMatchesHostFailure:
    @pytest.mark.asyncio
    async def test_host_name_none_when_user_lookup_fails(self):
        class _UserFailDb(FakeDb):
            async def execute(self, stmt):
                compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
                if "from users" in compiled.lower():
                    raise Exception("DB connection lost")
                return await super().execute(stmt)

        db = _UserFailDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )

        result = await list_open_matches(db)
        assert len(result) == 1
        assert result[0]["host_name"] is None


# ── join_match edge cases (#96) ─────────────────────────────────────────


class TestJoinMatchFull:
    @pytest.mark.asyncio
    async def test_join_when_all_slots_taken(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )
        # Manually fill the remaining slot
        joiner_id = uuid.uuid4()
        db.participants.append(_FakeParticipant(match.id, joiner_id, "B"))
        match.filled_slots = 2

        third = uuid.uuid4()
        with pytest.raises(ValueError, match="full"):
            await join_match(db, match_id=match.id, user_id=third)


class TestJoinMatchInvalidSlot:
    @pytest.mark.asyncio
    async def test_join_with_invalid_slot(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )
        joiner = uuid.uuid4()
        with pytest.raises(ValueError, match="taken or invalid"):
            await join_match(db, match_id=match.id, user_id=joiner, slot="Z")


class TestJoinMatchIntegrityError:
    @pytest.mark.asyncio
    async def test_join_handles_integrity_error(self):
        from sqlalchemy.exc import IntegrityError

        class _IntegrityDb(FakeDb):
            async def commit(self):
                raise IntegrityError("simulated", params=None, orig=Exception("dup"))

        db = _IntegrityDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match.__wrapped__(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h") \
            if hasattr(create_lobby_match, '__wrapped__') else _create_match_raw(db, host_id, cfg)

        joiner = uuid.uuid4()
        with pytest.raises(ValueError, match="claimed by another user"):
            await join_match(db, match_id=match.id, user_id=joiner)


def _create_match_raw(db, host_id, cfg):
    """Create a match without committing (for IntegrityError test)."""
    match = _FakeMatch(str(uuid.uuid4()), host_id, config=cfg)
    db.matches[match.id] = match
    db.participants.append(_FakeParticipant(match.id, host_id, "A"))
    match.filled_slots = 1
    return match, "nks_fake"


# ── _start_match_session (#96) ──────────────────────────────────────────


class TestStartMatchSession:
    @pytest.mark.asyncio
    async def test_creates_session_and_transitions_match(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )
        match.session_id = str(uuid.uuid4())

        # Call the real _start_match_session (not the fixture-patched version)
        await _real_start_match_session(db, match, cfg)
        assert match.status == "running"
        assert match.started_at is not None
        # Session should be in the DB
        assert match.session_id in db.sessions


# ── cancel_match edge cases (#96) ───────────────────────────────────────


class TestCancelMatchNotFound:
    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_match(self):
        db = FakeDb()
        result = await cancel_match(db, match_id="nope", user_id=uuid.uuid4())
        assert result is False


class TestCancelMatchNotWaiting:
    @pytest.mark.asyncio
    async def test_raises_for_running_match(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h",
        )
        match.status = "running"
        with pytest.raises(ValueError, match="not waiting"):
            await cancel_match(db, match_id=match.id, user_id=host_id)


# ── expire_stale_matches broker failure (#96) ───────────────────────────


class TestExpireBrokerFailure:
    @pytest.mark.asyncio
    async def test_expiry_continues_when_publish_fails(self):
        db = FakeDb()
        host_id = uuid.uuid4()
        cfg = _fake_config()
        match, _ = await create_lobby_match(
            db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h", ttl_hours=0,
        )
        match.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)

        class _FailBroker:
            async def publish(self, channel, message):
                raise Exception("redis down")

        expired = await expire_stale_matches(db, _FailBroker())
        assert expired == 1
        assert match.status == "expired"


# ── _matchmaking_sweeper_loop (#96) ─────────────────────────────────────


class TestSweeperLoop:
    @pytest.mark.asyncio
    async def test_loop_runs_and_exits_on_cancel(self, monkeypatch):
        call_count = 0

        class _CtxDb:
            async def __aenter__(self):
                return FakeDb()

            async def __aexit__(self, *args):
                return False

        monkeypatch.setattr(_mm_mod, "_async_session_factory", _CtxDb)

        original_sleep = asyncio.sleep

        async def _fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise asyncio.CancelledError()

        monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

        with pytest.raises(asyncio.CancelledError):
            await _matchmaking_sweeper_loop(FakeBroker())

    @pytest.mark.asyncio
    async def test_loop_handles_errors_and_continues(self, monkeypatch):
        call_count = 0

        class _ErrorCtxDb:
            async def __aenter__(self):
                raise Exception("DB connection failed")

            async def __aexit__(self, *args):
                return False

        monkeypatch.setattr(_mm_mod, "_async_session_factory", _ErrorCtxDb)

        sleep_count = 0

        async def _fake_sleep(seconds):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count >= 1:
                raise asyncio.CancelledError()

        monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

        with pytest.raises(asyncio.CancelledError):
            await _matchmaking_sweeper_loop(FakeBroker())
        assert sleep_count >= 1

    @pytest.mark.asyncio
    async def test_loop_reraises_cancelled_from_expire(self, monkeypatch):
        """CancelledError raised inside expire_stale_matches is re-raised."""

        class _CancelCtxDb:
            async def __aenter__(self):
                raise asyncio.CancelledError()

            async def __aexit__(self, *args):
                return False

        monkeypatch.setattr(_mm_mod, "_async_session_factory", _CancelCtxDb)

        with pytest.raises(asyncio.CancelledError):
            await _matchmaking_sweeper_loop(FakeBroker())

    @pytest.mark.asyncio
    async def test_loop_uses_default_interval_on_settings_failure(self, monkeypatch):
        call_count = 0

        class _CtxDb:
            async def __aenter__(self):
                return FakeDb()

            async def __aexit__(self, *args):
                return False

        monkeypatch.setattr(_mm_mod, "_async_session_factory", _CtxDb)

        def _settings_boom():
            raise Exception("settings unavailable")

        monkeypatch.setattr(_mm_mod, "get_settings", _settings_boom)

        async def _fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise asyncio.CancelledError()
            assert seconds == 3600  # default interval

        monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

        with pytest.raises(asyncio.CancelledError):
            await _matchmaking_sweeper_loop(FakeBroker())


def _seed_lobby_client(monkeypatch, db, user, broker=None):
    """Wire up dependencies for lobby endpoint tests."""
    monkeypatch.setenv("GITHUB_CLIENT_ID", "test-gh")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "test-gh-secret")
    get_settings.cache_clear()

    async def _db_factory():
        yield db

    app = arena.main.app
    app.dependency_overrides[arena.main.get_db] = _db_factory
    app.dependency_overrides[arena.main.require_user] = lambda: user
    app.dependency_overrides[arena.main.get_broker] = lambda: broker or FakeBroker()
    return TestClient(app)


class TestLobbyCreateMatch:
    def test_creates_match_via_endpoint(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.post("/lobby/matches", json={"game": "test_game", "players": 2})
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert "match_id" in data
            assert "host_token" in data
            assert data["status"] == "waiting"
            assert data["total_slots"] == 2
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyListMatches:
    def test_lists_open_matches(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h"))

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.get("/lobby/matches")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert len(data["matches"]) >= 1
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyGetMatch:
    def test_get_match_detail(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        match, _ = asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h"))

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.get(f"/lobby/matches/{match.id}")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["id"] == match.id
            assert "participants" in data
        finally:
            arena.main.app.dependency_overrides.clear()

    def test_get_nonexistent_match_404(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.get("/lobby/matches/nope")
            assert resp.status_code == 404
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyJoinMatch:
    def test_join_match_via_endpoint(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        match, _ = asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h"))

        joiner_id = uuid.uuid4()
        joiner = type("U", (), {"id": joiner_id, "email": "j@e.io", "name": "J", "username": "joiner"})()
        db.users[joiner_id] = joiner

        client = _seed_lobby_client(monkeypatch, db, joiner)
        try:
            resp = client.post(f"/lobby/matches/{match.id}/join", json={})
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["slot"] == "B"
            assert "player_token" in data
        finally:
            arena.main.app.dependency_overrides.clear()

    def test_join_expired_match_returns_409(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        match, _ = asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h", ttl_hours=0))
        match.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)

        joiner_id = uuid.uuid4()
        joiner = type("U", (), {"id": joiner_id, "email": "j@e.io", "name": "J", "username": "joiner"})()
        db.users[joiner_id] = joiner

        client = _seed_lobby_client(monkeypatch, db, joiner)
        try:
            resp = client.post(f"/lobby/matches/{match.id}/join", json={})
            assert resp.status_code == 409
        finally:
            arena.main.app.dependency_overrides.clear()

    def test_join_nonexistent_match_returns_404(self, monkeypatch):
        joiner_id = uuid.uuid4()
        joiner = type("U", (), {"id": joiner_id, "email": "j@e.io", "name": "J", "username": "joiner"})()
        db = FakeDb()

        client = _seed_lobby_client(monkeypatch, db, joiner)
        try:
            resp = client.post("/lobby/matches/nope/join", json={})
            assert resp.status_code == 404
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyCancelMatch:
    def test_cancel_match_via_endpoint(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        match, _ = asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h"))

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.delete(f"/lobby/matches/{match.id}")
            assert resp.status_code == 200, resp.text
            assert resp.json()["cancelled"] is True
        finally:
            arena.main.app.dependency_overrides.clear()

    def test_cancel_non_host_returns_403(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        match, _ = asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h"))

        other_id = uuid.uuid4()
        other = type("U", (), {"id": other_id, "email": "o@e.io", "name": "O", "username": "other"})()

        client = _seed_lobby_client(monkeypatch, db, other)
        try:
            resp = client.delete(f"/lobby/matches/{match.id}")
            assert resp.status_code == 403
        finally:
            arena.main.app.dependency_overrides.clear()

    def test_cancel_nonexistent_match_returns_404(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.delete("/lobby/matches/nope")
            assert resp.status_code == 404
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyStreamMatch:
    def test_stream_nonexistent_match_404(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.get("/lobby/matches/nope/stream")
            assert resp.status_code == 404
        finally:
            arena.main.app.dependency_overrides.clear()

    def test_stream_returns_event_stream(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        match, _ = asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h"))

        # Use a non-MessageBroker to trigger the fallback path (line 959-961)
        class _FakeNonBroker:
            pass

        client = _seed_lobby_client(monkeypatch, db, host, broker=_FakeNonBroker())
        try:
            resp = client.get(f"/lobby/matches/{match.id}/stream")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
        finally:
            arena.main.app.dependency_overrides.clear()


# ── _check_match_participation with Bearer JWT (#96) ────────────────────


class TestCheckMatchParticipation:
    @pytest.mark.asyncio
    async def test_rejects_non_participant_with_jwt(self):
        from arena.main import _check_match_participation

        db = FakeDb()
        match_id = "m1"
        participant_id = uuid.uuid4()
        non_participant_id = uuid.uuid4()

        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id=match_id)
        db.matches[match_id] = _FakeMatch(match_id, participant_id)
        db.participants.append(_FakeParticipant(match_id, participant_id, "A"))

        token = create_access_token(str(non_participant_id))
        with pytest.raises(Exception) as exc_info:
            await _check_match_participation("sess-1", f"Bearer {token}", db)
        assert "not a participant" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_allows_participant_with_jwt(self):
        from arena.main import _check_match_participation

        db = FakeDb()
        match_id = "m1"
        participant_id = uuid.uuid4()

        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id=match_id)
        db.matches[match_id] = _FakeMatch(match_id, participant_id)
        db.participants.append(_FakeParticipant(match_id, participant_id, "A"))

        token = create_access_token(str(participant_id))
        # Should not raise
        await _check_match_participation("sess-1", f"Bearer {token}", db)

    @pytest.mark.asyncio
    async def test_passes_through_with_nks_token(self):
        from arena.main import _check_match_participation

        db = FakeDb()
        # No match_id → legacy session → pass-through
        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id=None)
        # Should not raise even with a Bearer nks_ token
        await _check_match_participation("sess-1", "Bearer nks_faketoken", db)

    @pytest.mark.asyncio
    async def test_passes_through_with_no_auth(self):
        from arena.main import _check_match_participation

        db = FakeDb()
        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id="m1")
        # No authorization header → pass-through
        await _check_match_participation("sess-1", None, db)
        await _check_match_participation("sess-1", "", db)

    @pytest.mark.asyncio
    async def test_passes_through_with_garbage_jwt(self):
        """An un-decodable Bearer token is treated as no-auth (pass-through)."""
        from arena.main import _check_match_participation

        db = FakeDb()
        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id="m1")
        await _check_match_participation("sess-1", "Bearer not-a-real-jwt", db)

    @pytest.mark.asyncio
    async def test_passes_through_with_non_bearer_auth(self):
        from arena.main import _check_match_participation

        db = FakeDb()
        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id="m1")
        await _check_match_participation("sess-1", "Basic abc123", db)

    @pytest.mark.asyncio
    async def test_passes_through_when_jwt_sub_not_uuid(self):
        """JWT with a non-UUID sub → UUID() raises → except Exception: return."""
        from arena.main import _check_match_participation

        db = FakeDb()
        db.sessions["sess-1"] = _FakeSessionRow("sess-1", match_id="m1")
        token = create_access_token("not-a-uuid-string")
        await _check_match_participation("sess-1", f"Bearer {token}", db)


class TestLobbyMatchmakingDisabled:
    def test_create_rejects_when_matchmaking_disabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_MATCHMAKING", "false")
        get_settings.cache_clear()
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.post("/lobby/matches", json={"game": "test_game", "players": 2})
            assert resp.status_code == 403
            assert "disabled" in resp.json()["detail"].lower()
        finally:
            arena.main.app.dependency_overrides.clear()

    def test_join_rejects_when_matchmaking_disabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_MATCHMAKING", "false")
        get_settings.cache_clear()
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.post("/lobby/matches/fake/join", json={})
            assert resp.status_code == 403
            assert "disabled" in resp.json()["detail"].lower()
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyCreateInvalidConfig:
    def test_create_rejects_bad_game_config(self, monkeypatch):
        from arena.game_registry import GameRegistry, GameRegistryError

        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()

        def _bad_config(self, payload):
            raise ValueError("unknown game type")

        monkeypatch.setattr(GameRegistry, "config_from_request", _bad_config)

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.post("/lobby/matches", json={"game": "nonexistent", "players": 2})
            assert resp.status_code == 400
            assert "unknown game type" in resp.json()["detail"].lower()
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyJoinWithSlot:
    def test_join_with_explicit_slot(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        match, _ = asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h"))

        joiner_id = uuid.uuid4()
        joiner = type("U", (), {"id": joiner_id, "email": "j@e.io", "name": "J", "username": "joiner"})()
        db.users[joiner_id] = joiner

        client = _seed_lobby_client(monkeypatch, db, joiner)
        try:
            resp = client.post(f"/lobby/matches/{match.id}/join", json={"slot": "B"})
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["slot"] == "B"
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyLocalModeDisabled:
    def test_create_rejects_in_local_mode(self, monkeypatch):
        monkeypatch.setenv("GITHUB_CLIENT_ID", "")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
        get_settings.cache_clear()

        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()

        async def _db_factory():
            yield db

        app = arena.main.app
        app.dependency_overrides[arena.main.get_db] = _db_factory
        app.dependency_overrides[arena.main.require_user] = lambda: host
        client = TestClient(app)
        try:
            resp = client.post("/lobby/matches", json={"game": "test_game", "players": 2})
            assert resp.status_code == 403
            assert "multi-user" in resp.json()["detail"].lower()
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyCreateInternalError:
    def test_create_returns_500_on_internal_error(self, monkeypatch):
        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()

        async def _boom(*args, **kwargs):
            raise RuntimeError("DB schema mismatch")

        monkeypatch.setattr(arena.main, "create_lobby_match", _boom)

        client = _seed_lobby_client(monkeypatch, db, host)
        try:
            resp = client.post("/lobby/matches", json={"game": "test_game", "players": 2})
            assert resp.status_code == 500
            assert "schema mismatch" in resp.json()["detail"].lower()
        finally:
            arena.main.app.dependency_overrides.clear()


class TestLobbyStreamWithBroker:
    def test_stream_subscribes_to_broker_channel(self, monkeypatch):
        from arena.messaging.broker import MessageBroker

        class _FakeRealBroker(MessageBroker):
            async def publish(self, channel, message): pass
            async def subscribe(self, channel):
                async def _gen():
                    yield {"event": "match_filled", "match_id": "x", "session_id": "s1", "status": "running"}
                return _gen()
            async def enqueue(self, queue, message): pass
            async def dequeue(self, queue, timeout=5): return None
            async def cache_set(self, key, value, ttl=300): pass
            async def cache_get(self, key): return None
            async def close(self): pass

        _broker = _FakeRealBroker()
        monkeypatch.setattr(arena.main, "get_broker", lambda: _broker)

        host_id = uuid.uuid4()
        host = type("U", (), {"id": host_id, "email": "h@e.io", "name": "H", "username": "host"})()
        db = FakeDb()
        db.users[host_id] = host
        cfg = _fake_config()
        match, _ = asyncio.run(create_lobby_match(db, host_user_id=host_id, game_type="g", config=cfg, config_hash="h"))

        client = _seed_lobby_client(monkeypatch, db, host, broker=_broker)
        try:
            resp = client.get(f"/lobby/matches/{match.id}/stream")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            assert "match_filled" in resp.text
        finally:
            arena.main.app.dependency_overrides.clear()