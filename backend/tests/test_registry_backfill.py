"""Tests for arena.main._load_registries_from_db.

This is the self-healing mechanism every backend boot relies on: it
reloads persisted leaderboard/Elo state from agent_registry_states, then
replays any completed session whose outcome isn't reflected in the
in-memory registries yet (e.g. because the previous process was killed
— by a Swarm rolling deploy or otherwise — between recording a match and
flushing the registry to the DB). If this logic is wrong, a registry
update lost mid-deploy stays lost forever instead of self-healing on the
next restart.
"""
import os

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")

from unittest.mock import MagicMock

import pytest

import arena.main as main
import arena.metrics as metrics
from arena.metrics.registry import AgentRegistry


# ── Fakes ────────────────────────────────────────────────────────────────


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeSession:
    """One `async with _async_session_factory() as db:` block's worth of
    canned `db.execute(...)` results, returned in call order."""

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


class _FakeSessionFactory:
    """Hands out one _FakeSession per call, in order — mirrors one call
    per `async with _async_session_factory() as db:` block in the function
    under test."""

    def __init__(self, sessions):
        self._sessions = iter(sessions)

    def __call__(self):
        return next(self._sessions)


def _registry_row(key, state):
    row = MagicMock()
    row.key = key
    row.state_json = state
    return row


def _session_row(session_id, status="complete"):
    row = MagicMock()
    row.id = session_id
    row.status = status
    row.created_at = None
    return row


class _StubMatch:
    def __init__(self, match_id, game_type="prisonersdilemma", agent_ids=("A", "B"), payoffs=None):
        self.match_id = match_id
        self.game_type = game_type
        self.agent_ids = list(agent_ids)
        self._payoffs = payoffs or {a: [1.0] for a in agent_ids}

    def payoffs(self, agent_id):
        return self._payoffs.get(agent_id, [])


class _StubGameSession:
    def __init__(self, match, *, raise_on_results=False):
        self._match = match
        self._raise_on_results = raise_on_results

    def results(self, evaluator=None):
        if self._raise_on_results:
            raise RuntimeError("boom")
        return {}

    def to_match(self):
        return self._match


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_registry_globals():
    """The registries live in module-level globals — snapshot/restore
    around every test so backfill tests can't bleed into each other or
    into unrelated test files sharing the same pytest session."""
    saved_global = metrics._global_registry
    saved_registries = dict(metrics._registries)
    metrics._global_registry = None
    metrics._registries = {}
    yield
    metrics._global_registry = saved_global
    metrics._registries = saved_registries


def _patch_session_factory(monkeypatch, sessions):
    monkeypatch.setattr(main, "_async_session_factory", _FakeSessionFactory(sessions))


def _patch_game_session(monkeypatch, by_id: dict[str, _StubGameSession]):
    def _from_db_row(row):
        return by_id[row.id]
    monkeypatch.setattr(main.GameSession, "from_db_row", staticmethod(_from_db_row))


# ── Loading agent_registry_states ───────────────────────────────────────


class TestLoadRegistryRows:
    @pytest.mark.asyncio
    async def test_loads_global_and_named_rows(self, monkeypatch):
        global_state = AgentRegistry().to_dict()
        global_state["elo_ratings"] = {"agent-x": 1600.0}
        named_state = AgentRegistry().to_dict()
        named_state["elo_ratings"] = {"agent-y": 1400.0}

        load_session = _FakeSession([
            _FakeResult([
                _registry_row("global", global_state),
                _registry_row("game:prisonersdilemma", named_state),
            ]),
        ])
        backfill_session = _FakeSession([_FakeResult([])])
        _patch_session_factory(monkeypatch, [load_session, backfill_session])

        await main._load_registries_from_db()

        assert metrics.get_global_registry().elo_ratings["agent-x"] == 1600.0
        assert metrics.get_registry("game:prisonersdilemma").elo_ratings["agent-y"] == 1400.0

    @pytest.mark.asyncio
    async def test_malformed_row_is_skipped_not_fatal(self, monkeypatch):
        good_state = AgentRegistry().to_dict()
        good_state["elo_ratings"] = {"agent-x": 1500.0}

        load_session = _FakeSession([
            _FakeResult([
                _registry_row("game:bad", "not a valid state dict"),
                _registry_row("global", good_state),
            ]),
        ])
        backfill_session = _FakeSession([_FakeResult([])])
        _patch_session_factory(monkeypatch, [load_session, backfill_session])

        await main._load_registries_from_db()

        # The malformed row didn't crash startup, and the good row after
        # it still loaded.
        assert metrics.get_global_registry().elo_ratings["agent-x"] == 1500.0
        assert "game:bad" not in metrics._registries

    @pytest.mark.asyncio
    async def test_no_global_row_defaults_to_empty_registry(self, monkeypatch):
        load_session = _FakeSession([_FakeResult([])])
        backfill_session = _FakeSession([_FakeResult([])])
        _patch_session_factory(monkeypatch, [load_session, backfill_session])

        await main._load_registries_from_db()

        assert metrics.get_global_registry().elo_ratings == {}

    @pytest.mark.asyncio
    async def test_db_error_during_load_does_not_raise(self, monkeypatch):
        class _ExplodingSession(_FakeSession):
            async def execute(self, stmt):
                raise RuntimeError("connection reset")

        backfill_session = _FakeSession([_FakeResult([])])
        _patch_session_factory(monkeypatch, [_ExplodingSession([]), backfill_session])

        # Must not raise — a DB hiccup on startup shouldn't crash the boot.
        await main._load_registries_from_db()


# ── Backfill replay ──────────────────────────────────────────────────────


class TestBackfill:
    @pytest.mark.asyncio
    async def test_replays_completed_session_not_yet_recorded(self, monkeypatch):
        load_session = _FakeSession([_FakeResult([])])
        sess_row = _session_row("s1")
        backfill_query_session = _FakeSession([_FakeResult([sess_row])])
        save_session = _FakeSession([None, None])  # one execute per save_registry() call
        _patch_session_factory(
            monkeypatch, [load_session, backfill_query_session, save_session]
        )
        _patch_game_session(monkeypatch, {
            "s1": _StubGameSession(_StubMatch("m1")),
        })

        await main._load_registries_from_db()

        game_registry = metrics.get_game_registry("prisonersdilemma")
        assert "m1" in game_registry.match_history
        # The replayed match got persisted back to the DB (the self-healing
        # write), not just held in memory again.
        assert save_session.committed

    @pytest.mark.asyncio
    async def test_already_recorded_match_is_not_double_counted(self, monkeypatch):
        # Simulates the normal case: this runs on every restart, and most
        # completed sessions are already reflected in the registry.
        game_registry = metrics.get_game_registry("prisonersdilemma")
        game_registry.match_history.append("m1")

        load_session = _FakeSession([_FakeResult([])])
        sess_row = _session_row("s1")
        backfill_query_session = _FakeSession([_FakeResult([sess_row])])
        _patch_session_factory(monkeypatch, [load_session, backfill_query_session])
        _patch_game_session(monkeypatch, {
            "s1": _StubGameSession(_StubMatch("m1")),
        })

        await main._load_registries_from_db()

        # record_match was never re-invoked for an already-known match, so
        # no third (save) session should have been requested at all.
        assert game_registry.match_history.count("m1") == 1

    @pytest.mark.asyncio
    async def test_one_bad_session_does_not_abort_the_rest(self, monkeypatch):
        load_session = _FakeSession([_FakeResult([])])
        rows = [_session_row("bad"), _session_row("good")]
        backfill_query_session = _FakeSession([_FakeResult(rows)])
        save_session = _FakeSession([None])
        _patch_session_factory(
            monkeypatch, [load_session, backfill_query_session, save_session]
        )
        _patch_game_session(monkeypatch, {
            "bad": _StubGameSession(_StubMatch("m-bad"), raise_on_results=True),
            "good": _StubGameSession(_StubMatch("m-good")),
        })

        await main._load_registries_from_db()

        game_registry = metrics.get_game_registry("prisonersdilemma")
        assert "m-good" in game_registry.match_history
        assert "m-bad" not in game_registry.match_history

    @pytest.mark.asyncio
    async def test_backfill_section_error_does_not_raise(self, monkeypatch):
        load_session = _FakeSession([_FakeResult([])])

        class _ExplodingSession(_FakeSession):
            async def execute(self, stmt):
                raise RuntimeError("connection reset")

        _patch_session_factory(monkeypatch, [load_session, _ExplodingSession([])])

        # Must not raise — a DB hiccup during backfill shouldn't crash boot.
        await main._load_registries_from_db()
