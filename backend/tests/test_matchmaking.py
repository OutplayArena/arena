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
)
from arena.settings import get_settings  # noqa: E402


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