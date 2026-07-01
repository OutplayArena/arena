"""Tests for leaderboard privacy scoping, session visibility, and attribution helpers.

Covers:
- _leaderboard_agent_entry() — display_name / owner_username / is_own logic
- _build_leaderboard_response() — with and without enough agents for α-Rank
- _public_agent_id() / _namespace_match() — agent ID namespacing
- _build_personal_registry() — per-user on-demand registry construction
- _restore_wandb_logger() — early return paths (no meta / no user_id)
- GET /leaderboard?scope=personal — personal registry path
- GET /leaderboard?scope=all — merged personal+public path
- PATCH /sessions/{id}/visibility — toggle is_public, triggers rebuild
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")

import importlib  # noqa: E402
import pytest  # noqa: E402

import arena.main  # noqa: E402
importlib.reload(arena.main)

from arena.main import (  # noqa: E402
    app,
    _leaderboard_agent_entry,
    _build_leaderboard_response,
    _public_agent_id,
    _namespace_match,
    _build_personal_registry,
    _restore_wandb_logger,
    get_broker,
)
from arena.db import get_db  # noqa: E402
from arena.auth.dependencies import get_local_or_optional_user  # noqa: E402
from arena.models.user import User  # noqa: E402
from arena.metrics.registry import AgentRegistry  # noqa: E402
from arena.metrics import contracts  # noqa: E402
import arena.metrics  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


# ── Shared fixtures ───────────────────────────────────────────────────────────

_UID = uuid.UUID("00000000-0000-0000-0000-000000000077")
_FAKE_USER = User(
    id=_UID,
    email="bob@example.com",
    name="Bob",
    provider="github",
    provider_user_id="gh-77",
)
_FAKE_USER.username = "bobdev"


class FakeResult:
    def __init__(self, data=None):
        self._data = data

    def scalar_one_or_none(self):
        if isinstance(self._data, list):
            return self._data[0] if self._data else None
        return self._data

    def scalars(self):
        return self

    def all(self):
        return self._data if isinstance(self._data, list) else (
            [self._data] if self._data is not None else []
        )


class FakeBroker:
    async def publish(self, channel, message):
        pass

    async def cache_get(self, key):
        return None

    async def cache_set(self, key, value, ttl=None):
        pass

    async def enqueue(self, queue, message):
        pass


class VisibilityFakeDb:
    """DB fake for set_session_visibility tests."""

    def __init__(self, session_row=None):
        self._session = session_row
        self.committed = False

    async def execute(self, stmt):
        return FakeResult(self._session)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


@pytest.fixture(autouse=True)
def _reset_registries():
    saved_global = arena.metrics._global_registry
    saved = dict(arena.metrics._registries)
    arena.metrics._global_registry = None
    arena.metrics._registries = {}
    yield
    arena.metrics._global_registry = saved_global
    arena.metrics._registries = saved


def _make_match(agent_ids, match_id="m1", game_type="ultimatum"):
    return contracts.Match(
        match_id=match_id, game_type=game_type, agent_ids=agent_ids, moves=[]
    )


def _seed(registry: AgentRegistry, agent_ids, payoffs=None, match_id="m1"):
    payoffs = payoffs or {a: 1.0 for a in agent_ids}
    registry.record_match(_make_match(agent_ids, match_id), payoffs)


# ── _public_agent_id ──────────────────────────────────────────────────────────


class TestPublicAgentId:
    def test_with_username(self):
        assert _public_agent_id("gpt-4o", "herbertw") == "gpt-4o@herbertw"

    def test_without_username_returns_bare(self):
        assert _public_agent_id("gpt-4o", None) == "gpt-4o"


# ── _namespace_match ──────────────────────────────────────────────────────────


class TestNamespaceMatch:
    def test_namespaces_agent_ids(self):
        m = _make_match(["gpt-4o", "claude-3"], "m1")
        namespaced = _namespace_match(m, "alice")
        assert namespaced.agent_ids == ["gpt-4o@alice", "claude-3@alice"]

    def test_no_username_keeps_bare_ids(self):
        m = _make_match(["gpt-4o", "claude-3"], "m1")
        namespaced = _namespace_match(m, None)
        assert namespaced.agent_ids == ["gpt-4o", "claude-3"]

    def test_moves_agent_ids_are_rewritten(self):
        from arena.metrics.contracts import Move
        move = Move(agent_id="gpt-4o", round_number=1, action="C", payoff=1.0)
        m = contracts.Match(match_id="m1", game_type="pd", agent_ids=["gpt-4o", "claude-3"], moves=[move])
        namespaced = _namespace_match(m, "alice")
        assert namespaced.moves[0].agent_id == "gpt-4o@alice"


# ── _leaderboard_agent_entry ──────────────────────────────────────────────────


class TestLeaderboardAgentEntry:
    def _empty_registry(self):
        r = AgentRegistry()
        _seed(r, ["A", "B"])
        return r

    def test_bare_agent_id_personal(self):
        r = self._empty_registry()
        pop = {"elo_ratings": r.elo_ratings, "alpha_rank_scores": {}}
        agg = r.aggregated_metrics(["A"])
        entry = _leaderboard_agent_entry("gpt-4o", r, pop, agg, "bobdev", is_personal=True)
        assert entry["display_name"] == "gpt-4o"
        assert entry["owner_username"] == "bobdev"
        assert entry["is_own"] is True

    def test_namespaced_agent_id_splits_on_at(self):
        r = self._empty_registry()
        pop = {"elo_ratings": r.elo_ratings, "alpha_rank_scores": {}}
        agg = r.aggregated_metrics(["A"])
        entry = _leaderboard_agent_entry("gpt-4o@alice", r, pop, agg, "bobdev", is_personal=False)
        assert entry["display_name"] == "gpt-4o"
        assert entry["owner_username"] == "alice"
        assert entry["is_own"] is False  # alice ≠ bobdev

    def test_namespaced_own_agent_is_own(self):
        r = self._empty_registry()
        pop = {"elo_ratings": r.elo_ratings, "alpha_rank_scores": {}}
        agg = r.aggregated_metrics(["A"])
        entry = _leaderboard_agent_entry("gpt-4o@bobdev", r, pop, agg, "bobdev", is_personal=False)
        assert entry["is_own"] is True

    def test_anonymous_public_entry(self):
        r = self._empty_registry()
        pop = {"elo_ratings": r.elo_ratings, "alpha_rank_scores": {}}
        agg = r.aggregated_metrics(["A"])
        entry = _leaderboard_agent_entry("gpt-4o@alice", r, pop, agg, None, is_personal=False)
        assert entry["display_name"] == "gpt-4o"
        assert entry["is_own"] is False


# ── _build_leaderboard_response ───────────────────────────────────────────────


class TestBuildLeaderboardResponse:
    def test_fewer_than_two_agents_returns_note(self):
        r = AgentRegistry()
        _seed(r, ["A", "B"])
        result = _build_leaderboard_response(r, ["A"], "elo", "desc", 1, 50)
        assert "note" in result
        assert result["total"] == 1

    def test_two_agents_no_note(self):
        r = AgentRegistry()
        _seed(r, ["A", "B"])
        result = _build_leaderboard_response(r, ["A", "B"], "elo", "desc", 1, 50)
        assert "note" not in result
        assert len(result["agents"]) == 2

    def test_sort_asc(self):
        r = AgentRegistry()
        for i in range(3):
            _seed(r, ["A", "B"], {"A": 10.0, "B": 0.0}, match_id=f"m{i}")
        result = _build_leaderboard_response(r, ["A", "B"], "elo", "asc", 1, 50)
        # Ascending: lower elo first → B first
        assert result["agents"][0]["agent_id"] == "B"

    def test_attribution_in_response(self):
        r = AgentRegistry()
        _seed(r, ["gpt-4o@alice", "claude@bob"])
        result = _build_leaderboard_response(
            r, ["gpt-4o@alice", "claude@bob"], "elo", "desc", 1, 50,
            current_username="alice", is_personal=False
        )
        names = {e["agent_id"]: e for e in result["agents"]}
        assert names["gpt-4o@alice"]["is_own"] is True
        assert names["claude@bob"]["is_own"] is False
        assert names["claude@bob"]["owner_username"] == "bob"


# ── _build_personal_registry ──────────────────────────────────────────────────

# Re-use the same _FakeSession / _FakeSessionFactory / _FakeResult pattern
# from test_registry_backfill.py so we can patch _async_session_factory.

class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDbResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)

    def all(self):
        return [(r, None) if not isinstance(r, tuple) else r for r in self._rows]


class _FakeDbSession:
    def __init__(self, results):
        self._results = list(results)
        self.committed = False

    async def execute(self, stmt):
        return self._results.pop(0)

    async def commit(self):
        self.committed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class _FakeDbSessionFactory:
    def __init__(self, sessions):
        self._sessions = iter(sessions)

    def __call__(self):
        return next(self._sessions)


def _stub_session_row(session_id, user_id=None):
    row = MagicMock()
    row.id = session_id
    row.status = "complete"
    row.is_public = True
    row.user_id = user_id
    row.created_at = None
    return row


class _StubMatch:
    def __init__(self, match_id, game_type="prisonersdilemma", agent_ids=("A", "B")):
        self.match_id = match_id
        self.game_type = game_type
        self.agent_ids = list(agent_ids)
        self.moves = []
        self.config = {}

    def payoffs(self, agent_id):
        return [1.0]


class _StubGameSession:
    def __init__(self, match):
        self._match = match

    def to_match(self):
        return self._match


class TestBuildPersonalRegistry:
    @pytest.mark.asyncio
    async def test_returns_registry_with_user_sessions(self, monkeypatch):
        sess_row = _stub_session_row("s1", user_id=_UID)
        db_session = _FakeDbSession([_FakeDbResult([sess_row])])
        monkeypatch.setattr(arena.main, "_async_session_factory", _FakeDbSessionFactory([db_session]))
        monkeypatch.setattr(
            arena.main.GameSession, "from_db_row",
            staticmethod(lambda row: _StubGameSession(_StubMatch("m1"))),
        )

        reg = await _build_personal_registry(_UID)

        assert "m1" in reg.match_history

    @pytest.mark.asyncio
    async def test_db_error_returns_empty_registry(self, monkeypatch):
        class _BadSession:
            async def execute(self, stmt):
                raise RuntimeError("boom")

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        monkeypatch.setattr(arena.main, "_async_session_factory", lambda: _BadSession())

        reg = await _build_personal_registry(_UID)

        assert reg.elo_ratings == {}

    @pytest.mark.asyncio
    async def test_bad_session_row_skipped(self, monkeypatch):
        sess_row = _stub_session_row("bad")
        db_session = _FakeDbSession([_FakeDbResult([sess_row])])
        monkeypatch.setattr(arena.main, "_async_session_factory", _FakeDbSessionFactory([db_session]))

        class _BoomSession:
            def to_match(self):
                raise RuntimeError("bad row")

        monkeypatch.setattr(
            arena.main.GameSession, "from_db_row",
            staticmethod(lambda row: _BoomSession()),
        )

        reg = await _build_personal_registry(_UID)
        assert reg.match_history == []

    @pytest.mark.asyncio
    async def test_unknown_game_type_skipped(self, monkeypatch):
        """Matches with game_type 'unknown' are skipped (line 410 continue)."""
        sess_row = _stub_session_row("s-unk")
        db_session = _FakeDbSession([_FakeDbResult([sess_row])])
        monkeypatch.setattr(arena.main, "_async_session_factory", _FakeDbSessionFactory([db_session]))
        monkeypatch.setattr(
            arena.main.GameSession, "from_db_row",
            staticmethod(lambda row: _StubGameSession(_StubMatch("m-unk", game_type="unknown"))),
        )

        reg = await _build_personal_registry(_UID)
        assert "m-unk" not in reg.match_history

    @pytest.mark.asyncio
    async def test_duplicate_match_not_double_counted(self, monkeypatch):
        """Matches already in the registry are skipped (line 412 continue)."""
        sess_rows = [_stub_session_row("s1"), _stub_session_row("s2")]
        db_session = _FakeDbSession([_FakeDbResult(sess_rows)])
        monkeypatch.setattr(arena.main, "_async_session_factory", _FakeDbSessionFactory([db_session]))
        # Both rows map to the same match_id → second should be skipped
        monkeypatch.setattr(
            arena.main.GameSession, "from_db_row",
            staticmethod(lambda row: _StubGameSession(_StubMatch("m-dup"))),
        )

        reg = await _build_personal_registry(_UID)
        assert reg.match_history.count("m-dup") == 1


# ── _restore_wandb_logger early return paths ──────────────────────────────────


class TestRestoreWandbLoggerEarlyReturns:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_meta_and_no_db_meta(self):
        broker = FakeBroker()  # cache_get always returns None
        session = MagicMock()
        session.session_id = "sess-1"
        session.wandb_run_meta = None  # no DB meta either
        db = MagicMock()

        result = await _restore_wandb_logger(session, db, broker)

        assert result is None

    @pytest.mark.asyncio
    async def test_uses_wandb_run_meta_when_cache_empty(self):
        broker = FakeBroker()  # cache_get returns None
        session = MagicMock()
        session.session_id = "sess-1"
        session.wandb_run_meta = {"run_id": "abc", "project": "test"}
        session.user_id = None  # no user → early return after meta check

        db = MagicMock()

        result = await _restore_wandb_logger(session, db, broker)

        assert result is None  # user_id is None → returns None

    @pytest.mark.asyncio
    async def test_returns_none_when_cache_has_meta_but_no_user_id(self):
        class _CacheBroker(FakeBroker):
            async def cache_get(self, key):
                return {"run_id": "xyz", "project": "outplayarena"}

        session = MagicMock()
        session.session_id = "sess-2"
        session.wandb_run_meta = None
        session.user_id = None

        result = await _restore_wandb_logger(session, MagicMock(), _CacheBroker())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_cred_found(self):
        class _CacheBroker(FakeBroker):
            async def cache_get(self, key):
                return {"run_id": "xyz", "project": "outplayarena"}

        session = MagicMock()
        session.session_id = "sess-3"
        session.wandb_run_meta = None
        session.user_id = uuid.uuid4()

        async def _fake_execute(stmt):
            return FakeResult(None)  # no credential found

        db = MagicMock()
        db.execute = AsyncMock(side_effect=_fake_execute)

        result = await _restore_wandb_logger(session, db, _CacheBroker())

        assert result is None


# ── Leaderboard scope endpoint tests ─────────────────────────────────────────


@pytest.fixture()
def _base_client():
    """Client with no user (anonymous)."""
    async def _db():
        yield MagicMock()

    async def _broker():
        yield FakeBroker()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_broker] = _broker
    app.dependency_overrides[get_local_or_optional_user] = lambda: None
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_broker, None)
    app.dependency_overrides.pop(get_local_or_optional_user, None)


@pytest.fixture()
def _authed_client():
    """Client with a logged-in user, fake DB, and no-op broker."""
    async def _db():
        yield MagicMock()

    async def _broker():
        yield FakeBroker()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_broker] = _broker
    app.dependency_overrides[get_local_or_optional_user] = lambda: _FAKE_USER
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_broker, None)
    app.dependency_overrides.pop(get_local_or_optional_user, None)


class TestLeaderboardScope:
    def test_anonymous_always_gets_public_scope(self, _base_client, monkeypatch):
        """Anonymous request returns scope=public even if scope param provided."""
        r = arena.metrics.get_global_registry()
        _seed(r, ["A", "B"])
        res = _base_client.get("/leaderboard?scope=personal")
        assert res.status_code == 200
        data = res.json()
        assert data["scope"] == "public"

    def test_logged_in_personal_scope(self, _authed_client, monkeypatch):
        """scope=personal calls _build_personal_registry and returns scope=personal."""
        personal_reg = AgentRegistry()
        _seed(personal_reg, ["my-model", "opponent"])

        async def _fake_personal(user_id):
            return personal_reg

        monkeypatch.setattr(arena.main, "_build_personal_registry", _fake_personal)

        res = _authed_client.get("/leaderboard?scope=personal")
        assert res.status_code == 200
        data = res.json()
        assert data["scope"] == "personal"

    def test_logged_in_all_scope(self, _authed_client, monkeypatch):
        """scope=all merges personal + public results."""
        personal_reg = AgentRegistry()
        _seed(personal_reg, ["my-model", "opponent"])

        pub_reg = arena.metrics.get_global_registry()
        _seed(pub_reg, ["gpt-4o@alice", "claude@carol"])

        async def _fake_personal(user_id):
            return personal_reg

        monkeypatch.setattr(arena.main, "_build_personal_registry", _fake_personal)

        res = _authed_client.get("/leaderboard?scope=all")
        assert res.status_code == 200
        data = res.json()
        assert data["scope"] == "all"

    def test_invalid_scope_defaults_to_personal(self, _authed_client, monkeypatch):
        """Unknown scope value falls back to personal for logged-in users."""
        personal_reg = AgentRegistry()
        _seed(personal_reg, ["A", "B"])

        async def _fake_personal(user_id):
            return personal_reg

        monkeypatch.setattr(arena.main, "_build_personal_registry", _fake_personal)

        res = _authed_client.get("/leaderboard?scope=bogus")
        assert res.status_code == 200
        data = res.json()
        assert data["scope"] == "personal"

    def test_all_scope_with_single_agent_personal_uses_else_branch(self, _authed_client, monkeypatch):
        """scope=all with <2 personal agents takes the else (no α-Rank) path."""
        # Personal registry with only 1 agent → len(personal_target) < 2 branch
        personal_reg = AgentRegistry()
        _seed(personal_reg, ["solo-model", "dummy"])  # needs 2 to record but we filter one out
        # Build a minimal reg that has only 1 known elo entry
        solo_reg = AgentRegistry()
        solo_reg.record_match(_make_match(["solo-model", "dummy"], "m-solo"), {"solo-model": 1.0, "dummy": 0.0})
        # Manually keep only solo-model by clearing dummy's elo
        del solo_reg.elo_ratings["dummy"]

        async def _fake_personal(user_id):
            return solo_reg

        # Empty public registry
        monkeypatch.setattr(arena.main, "_build_personal_registry", _fake_personal)

        res = _authed_client.get("/leaderboard?scope=all")
        assert res.status_code == 200
        assert res.json()["scope"] == "all"

    def test_all_scope_single_public_agent_uses_else_branch(self, _authed_client, monkeypatch):
        """scope=all with <2 public agents takes the else path for pop_pub."""
        # Empty personal registry (0 agents)
        async def _fake_personal(user_id):
            return AgentRegistry()

        monkeypatch.setattr(arena.main, "_build_personal_registry", _fake_personal)

        # Global registry with exactly 1 public agent
        pub_reg = arena.metrics.get_global_registry()
        pub_reg.record_match(_make_match(["gpt-4o@alice", "claude@alice"], "m-pub"), {"gpt-4o@alice": 1.0, "claude@alice": 0.0})
        # Remove one so only 1 remains after current_user filtering (if any)
        del pub_reg.elo_ratings["claude@alice"]

        res = _authed_client.get("/leaderboard?scope=all")
        assert res.status_code == 200
        assert res.json()["scope"] == "all"


# ── set_session_visibility ────────────────────────────────────────────────────


class _SessionRow:
    """Minimal session row for visibility toggle tests."""

    def __init__(self, session_id, user_id=_UID, is_public=False):
        self.id = session_id
        self.user_id = user_id
        self.is_public = is_public


class TestSetSessionVisibility:
    def _make_client(self, session_row):
        db = VisibilityFakeDb(session_row)

        async def _get_db():
            yield db

        async def _broker():
            yield FakeBroker()

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_broker] = _broker
        app.dependency_overrides[get_local_or_optional_user] = lambda: _FAKE_USER
        return TestClient(app, raise_server_exceptions=True), db

    def _teardown(self):
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_broker, None)
        app.dependency_overrides.pop(get_local_or_optional_user, None)

    def test_sets_is_public_true(self, monkeypatch):
        row = _SessionRow("sess-vis-1", user_id=_UID, is_public=False)
        client, db = self._make_client(row)

        async def _noop_rebuild():
            pass

        monkeypatch.setattr(arena.main, "_rebuild_leaderboard_registries", _noop_rebuild)

        try:
            res = client.patch("/sessions/sess-vis-1/visibility", json={"is_public": True})
        finally:
            self._teardown()

        assert res.status_code == 200
        data = res.json()
        assert data["is_public"] is True
        assert data["session_id"] == "sess-vis-1"
        assert db.committed

    def test_sets_is_public_false(self, monkeypatch):
        row = _SessionRow("sess-vis-2", user_id=_UID, is_public=True)
        client, db = self._make_client(row)

        async def _noop_rebuild():
            pass

        monkeypatch.setattr(arena.main, "_rebuild_leaderboard_registries", _noop_rebuild)

        try:
            res = client.patch("/sessions/sess-vis-2/visibility", json={"is_public": False})
        finally:
            self._teardown()

        assert res.status_code == 200
        assert res.json()["is_public"] is False

    def test_returns_404_when_session_not_found(self, monkeypatch):
        client, _ = self._make_client(None)  # DB returns no session row

        async def _noop_rebuild():
            pass

        monkeypatch.setattr(arena.main, "_rebuild_leaderboard_registries", _noop_rebuild)

        try:
            res = client.patch("/sessions/no-such-id/visibility", json={"is_public": True})
        finally:
            self._teardown()

        assert res.status_code == 404

    def test_anonymous_user_targets_null_user_id_clause(self, monkeypatch):
        """Anonymous PATCH uses the user_id IS NULL WHERE clause (line 1326)."""
        row = _SessionRow("sess-anon-1", user_id=None, is_public=False)
        db = VisibilityFakeDb(row)

        async def _get_db():
            yield db

        async def _broker():
            yield FakeBroker()

        async def _noop_rebuild():
            pass

        monkeypatch.setattr(arena.main, "_rebuild_leaderboard_registries", _noop_rebuild)
        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_broker] = _broker
        app.dependency_overrides[get_local_or_optional_user] = lambda: None
        client = TestClient(app, raise_server_exceptions=True)

        try:
            res = client.patch("/sessions/sess-anon-1/visibility", json={"is_public": True})
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_broker, None)
            app.dependency_overrides.pop(get_local_or_optional_user, None)

        assert res.status_code == 200

    def test_rebuild_error_is_swallowed(self, monkeypatch):
        """A failing registry rebuild doesn't propagate as HTTP 500 (lines 1338-1339)."""
        row = _SessionRow("sess-vis-err", user_id=_UID, is_public=False)
        client, _ = self._make_client(row)

        async def _boom():
            raise RuntimeError("redis down")

        monkeypatch.setattr(arena.main, "_rebuild_leaderboard_registries", _boom)

        try:
            res = client.patch("/sessions/sess-vis-err/visibility", json={"is_public": True})
        finally:
            self._teardown()

        # The rebuild error is caught and logged; the endpoint still returns 200.
        assert res.status_code == 200
