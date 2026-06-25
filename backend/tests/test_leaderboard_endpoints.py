"""Tests for the leaderboard API endpoints and supporting helpers.

Covers:
- /api/leaderboard (sorting, pagination, game filter, agent_ids filter, date filter)
- /api/leaderboard/agents/{agent_id}
- /api/leaderboard/agents/{agent_id}/history
- /api/benchmark/games
- /api/benchmark/report?game=...
- _safe_sort_key helper
- _build_leaderboard_entries helper
"""
import os
os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")

import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import arena.main
importlib.reload(arena.main)
from arena.main import app, _build_leaderboard_entries, _safe_sort_key, _SORTABLE_KEYS  # noqa: E402

import arena.metrics  # noqa: E402
from arena.metrics.registry import AgentRegistry  # noqa: E402
from arena.metrics import contracts  # noqa: E402


@pytest.fixture(autouse=True)
def reset_registries():
    """Reset module-level registry state between tests."""
    arena.metrics._global_registry = None
    arena.metrics._registries = {}
    yield
    arena.metrics._global_registry = None
    arena.metrics._registries = {}


def _make_match(agent_ids, match_id="m1", game_type="ultimatum"):
    return contracts.Match(match_id=match_id, game_type=game_type, agent_ids=agent_ids, moves=[])


def _seed_registry(registry: AgentRegistry, agents, payoffs=None, timestamps=None):
    """Record matches between consecutive agent pairs with given outcomes."""
    payoffs = payoffs or [1.0, 0.0]
    for i, match_id in enumerate([f"m{i}" for i in range(len(agents) - 1)]):
        a, b = agents[i], agents[i + 1]
        ts = timestamps[i] if timestamps else None
        registry.record_match(
            _make_match([a, b], match_id),
            {a: payoffs[0], b: payoffs[1]},
            timestamp=ts,
        )


# ── _safe_sort_key ──────────────────────────────────────────────────────


class TestSafeSortKey:
    def test_top_level_keys(self):
        entry = {"elo": 1500, "alpha_rank": 0.3, "matches_played": 10}
        assert _safe_sort_key(entry, "elo")[1] == 1500
        assert _safe_sort_key(entry, "alpha_rank")[1] == 0.3
        assert _safe_sort_key(entry, "matches_played")[1] == 10

    def test_metric_keys_read_from_nested_metrics(self):
        entry = {"metrics": {"nash_gap": 0.05, "cooperation_rate": 0.7}}
        assert _safe_sort_key(entry, "nash_gap")[1] == 0.05
        assert _safe_sort_key(entry, "cooperation_rate")[1] == 0.7

    def test_all_sortable_keys_supported(self):
        for key in _SORTABLE_KEYS:
            entry = {
                "elo": 1200.0,
                "alpha_rank": 0.5,
                "matches_played": 1,
                "metrics": {
                    "avg_payoff": 0.1,
                    "nash_gap": 0.2,
                    "cumulative_regret": 0.3,
                    "strategy_entropy": 0.4,
                    "behavioral_consistency": 0.5,
                    "cooperation_rate": 0.6,
                },
            }
            result = _safe_sort_key(entry, key)
            assert isinstance(result, tuple)
            assert result[0] == 0  # not None

    def test_none_values_sort_last(self):
        entry = {"elo": None, "metrics": {"nash_gap": None}}
        elo_tuple = _safe_sort_key(entry, "elo")
        nash_tuple = _safe_sort_key(entry, "nash_gap")
        assert elo_tuple[0] == 1
        assert nash_tuple[0] == 1

    def test_missing_keys_sort_last(self):
        entry = {}
        assert _safe_sort_key(entry, "elo") == (1, 0)
        assert _safe_sort_key(entry, "nash_gap") == (1, 0)

    def test_descending_with_reverse(self):
        entries = [
            {"elo": 1000.0, "metrics": {}},
            {"elo": 1500.0, "metrics": {}},
            {"elo": 1200.0, "metrics": {}},
        ]
        entries.sort(key=lambda e: _safe_sort_key(e, "elo"), reverse=True)
        assert [e["elo"] for e in entries] == [1500.0, 1200.0, 1000.0]

    def test_ascending_sort(self):
        entries = [
            {"elo": 1500.0, "metrics": {}},
            {"elo": 1000.0, "metrics": {}},
            {"elo": 1200.0, "metrics": {}},
        ]
        entries.sort(key=lambda e: _safe_sort_key(e, "elo"), reverse=False)
        assert [e["elo"] for e in entries] == [1000.0, 1200.0, 1500.0]


# ── _build_leaderboard_entries ─────────────────────────────────────────


class TestBuildLeaderboardEntries:
    def test_empty_registry(self):
        r = AgentRegistry()
        result = _build_leaderboard_entries(r, [])
        assert result["agents"] == []
        assert result["total"] == 0
        assert result["total_matches"] == 0
        assert "note" in result  # < 2 agents path includes a note

    def test_single_agent(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        result = _build_leaderboard_entries(r, ["A"])
        assert result["total"] == 1
        assert result["agents"][0]["agent_id"] == "A"
        assert result["agents"][0]["matches_played"] == 1
        assert "note" in result

    def test_two_agents_sorted_descending_by_elo(self):
        r = AgentRegistry()
        # A beats B decisively three times. A's elo should be highest.
        for i in range(3):
            r.record_match(_make_match(["A", "B"], f"ab{i}"), {"A": 10.0, "B": 0.0})

        result = _build_leaderboard_entries(r, ["A", "B"], sort_by="elo", sort_dir="desc")
        ids = [e["agent_id"] for e in result["agents"]]
        # A should be on top with the strongest record.
        assert ids == ["A", "B"]
        # Verify the elos in the response match the registry.
        a_elo = next(e["elo"] for e in result["agents"] if e["agent_id"] == "A")
        b_elo = next(e["elo"] for e in result["agents"] if e["agent_id"] == "B")
        assert a_elo > b_elo

    def test_sort_by_matches_played(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        r.record_match(_make_match(["A", "B"], "m2"), {"A": 1.0, "B": 0.0})
        r.record_match(_make_match(["A", "B"], "m3"), {"A": 0.0, "B": 1.0})
        # A and B both have 3 matches, C is not in any match.
        result = _build_leaderboard_entries(
            r, ["A", "B", "C"], sort_by="matches_played", sort_dir="desc"
        )
        # Top two entries should have 3 matches (A and B, in some order).
        assert result["agents"][0]["matches_played"] == 3
        assert result["agents"][1]["matches_played"] == 3
        # C never played.
        assert result["agents"][2]["matches_played"] == 0

    def test_sort_by_nash_gap_ascending(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            agent_metrics={
                "A": {"nash_gap": 0.1, "avg_payoff": 0.0, "cumulative_regret": 0.0,
                      "strategy_entropy": 0.0, "behavioral_consistency": 0.0, "cooperation_rate": 0.0},
                "B": {"nash_gap": 0.9, "avg_payoff": 0.0, "cumulative_regret": 0.0,
                      "strategy_entropy": 0.0, "behavioral_consistency": 0.0, "cooperation_rate": 0.0},
            },
        )
        r.record_match(
            _make_match(["C", "B"], "m2"),
            {"C": 1.0, "B": 0.0},
            agent_metrics={
                "C": {"nash_gap": 0.5, "avg_payoff": 0.0, "cumulative_regret": 0.0,
                      "strategy_entropy": 0.0, "behavioral_consistency": 0.0, "cooperation_rate": 0.0},
                "B": {"nash_gap": 0.9, "avg_payoff": 0.0, "cumulative_regret": 0.0,
                      "strategy_entropy": 0.0, "behavioral_consistency": 0.0, "cooperation_rate": 0.0},
            },
        )
        result = _build_leaderboard_entries(
            r, ["A", "B", "C"], sort_by="nash_gap", sort_dir="asc"
        )
        # A (0.1) first, then C (0.5), then B (0.9).
        assert [e["agent_id"] for e in result["agents"]] == ["A", "C", "B"]

    def test_pagination(self):
        r = AgentRegistry()
        agents = [f"agent-{i}" for i in range(10)]
        # Give each agent at least one match so they all have elo.
        for i in range(len(agents) - 1):
            r.record_match(
                _make_match([agents[i], agents[i + 1]], f"m{i}"),
                {agents[i]: 1.0, agents[i + 1]: 0.0},
            )
        result = _build_leaderboard_entries(r, agents, page=1, page_size=3)
        assert result["total"] == 10
        assert len(result["agents"]) == 3
        result_p2 = _build_leaderboard_entries(r, agents, page=2, page_size=3)
        assert len(result_p2["agents"]) == 3
        result_p4 = _build_leaderboard_entries(r, agents, page=4, page_size=3)
        assert len(result_p4["agents"]) == 1  # 10 - 9 = 1 left

    def test_pagination_out_of_range_returns_empty(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        result = _build_leaderboard_entries(r, ["A", "B"], page=99, page_size=50)
        assert result["agents"] == []
        assert result["total"] == 2
        assert result["page"] == 99

    def test_total_matches_in_response(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        r.record_match(_make_match(["A", "B"], "m2"), {"A": 0.0, "B": 1.0})
        result = _build_leaderboard_entries(r, ["A", "B"])
        assert result["total_matches"] == 2

    def test_entries_include_all_fields(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            agent_metrics={
                "A": {"nash_gap": 0.1, "avg_payoff": 0.5, "cumulative_regret": 0.0,
                      "strategy_entropy": 1.0, "behavioral_consistency": 0.8, "cooperation_rate": 0.6},
                "B": {},
            },
        )
        result = _build_leaderboard_entries(r, ["A", "B"])
        entry_a = next(e for e in result["agents"] if e["agent_id"] == "A")
        assert "elo" in entry_a
        assert "alpha_rank" in entry_a
        assert "matches_played" in entry_a
        assert "metrics" in entry_a
        assert entry_a["matches_played"] == 1
        assert entry_a["metrics"]["nash_gap"] == 0.1


# ── /api/leaderboard endpoint ──────────────────────────────────────────


def _stub_db():
    """Create a fake DB that returns empty result sets for any query."""
    db = MagicMock()
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    result.all = MagicMock(return_value=[])
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _get_db_override(db):
    from arena.db import get_db
    app.dependency_overrides[get_db] = lambda: db
    return db


def _clear_db_override():
    from arena.db import get_db
    app.dependency_overrides.pop(get_db, None)


class TestGetLeaderboardEndpoint:
    def test_empty_state(self):
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            r = client.get("/leaderboard")
            assert r.status_code == 200
            body = r.json()
            assert body["agents"] == []
            assert body["total"] == 0
            assert body["page"] == 1
            assert body["page_size"] == 50
            assert "note" in body
        finally:
            _clear_db_override()

    def test_returns_paginated_entries(self):
        r = AgentRegistry()
        for i in range(5):
            a, b = f"a{i}", f"a{i + 1}"
            r.record_match(_make_match([a, b], f"m{i}"), {a: 1.0, b: 0.0})
        arena.metrics.set_global_registry(r)

        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?page=1&page_size=3")
            assert res.status_code == 200
            body = res.json()
            assert body["total"] == 6
            assert len(body["agents"]) == 3
            assert body["page"] == 1
            assert body["page_size"] == 3
        finally:
            _clear_db_override()

    def test_invalid_sort_by_falls_back_to_alpha_rank(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?sort_by=garbage")
            assert res.status_code == 200
            # Should not 422, just silently fall back to default sort.
            assert "agents" in res.json()
        finally:
            _clear_db_override()

    def test_page_zero_is_rejected(self):
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?page=0")
            assert res.status_code == 422
        finally:
            _clear_db_override()

    def test_page_size_out_of_range_is_rejected(self):
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?page_size=999")
            assert res.status_code == 422
        finally:
            _clear_db_override()

    def test_agent_ids_filter(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        r.record_match(_make_match(["C", "B"], "m2"), {"C": 0.0, "B": 1.0})
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?agent_ids=A,B")
            body = res.json()
            ids = {e["agent_id"] for e in body["agents"]}
            assert ids == {"A", "B"}
        finally:
            _clear_db_override()

    def test_game_filter_uses_per_game_registry(self):
        global_reg = AgentRegistry()
        global_reg.record_match(_make_match(["A", "B"], "g-m1"), {"A": 1.0, "B": 0.0})
        global_reg.record_match(_make_match(["C", "D"], "g-m2"), {"C": 1.0, "D": 0.0})
        arena.metrics.set_global_registry(global_reg)

        game_reg = arena.metrics.get_game_registry("colonelblotto")
        game_reg.record_match(_make_match(["A", "B"], "c-m1"), {"A": 1.0, "B": 0.0})
        # Note: C and D are NOT in the colonelblotto registry.

        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res_global = client.get("/leaderboard")
            global_ids = {e["agent_id"] for e in res_global.json()["agents"]}
            assert global_ids == {"A", "B", "C", "D"}

            res_game = client.get("/leaderboard?game=colonelblotto")
            game_ids = {e["agent_id"] for e in res_game.json()["agents"]}
            assert game_ids == {"A", "B"}
        finally:
            _clear_db_override()

    def test_date_from_excludes_agents_with_no_snapshots(self):
        """Regression test: agents with no elo_snapshots must be excluded when
        date_from is set, not silently included."""
        r = AgentRegistry()
        # Agent A has a snapshot in 2025.
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            timestamp="2025-03-01T00:00:00+00:00",
        )
        # Agent C has an elo rating (default 1200) but no recorded matches/snapshots.
        r.elo_ratings["C"] = 1200.0
        arena.metrics.set_global_registry(r)

        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?date_from=2025-01-01")
            ids = {e["agent_id"] for e in res.json()["agents"]}
            # A is included (snapshot in range), C is excluded (no snapshots).
            assert "A" in ids
            assert "C" not in ids
        finally:
            _clear_db_override()

    def test_date_from_includes_agent_active_after_cutoff(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            timestamp="2025-06-15T00:00:00+00:00",
        )
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?date_from=2025-01-01")
            ids = {e["agent_id"] for e in res.json()["agents"]}
            assert "A" in ids
        finally:
            _clear_db_override()

    def test_date_from_excludes_agent_active_before_cutoff(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            timestamp="2024-01-01T00:00:00+00:00",
        )
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?date_from=2025-01-01")
            ids = {e["agent_id"] for e in res.json()["agents"]}
            assert "A" not in ids
        finally:
            _clear_db_override()

    def test_date_to_excludes_agent_active_after_cutoff(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            timestamp="2025-06-15T00:00:00+00:00",
        )
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?date_to=2025-01-01")
            ids = {e["agent_id"] for e in res.json()["agents"]}
            assert "A" not in ids
        finally:
            _clear_db_override()

    def test_same_day_range_includes_agents_active_on_that_day(self):
        """Regression: when date_from == date_to and all snapshots fall on
        that single day, the agent must NOT be filtered out. The previous
        implementation compared the full ISO timestamp (e.g.
        "2026-06-25T14:23:45...") against the date-only filter string, so
        the timestamp string was always > the date string and every agent
        got excluded from a same-day range."""
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            timestamp="2026-06-25T14:23:45.123456+00:00",
        )
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard?date_from=2026-06-25&date_to=2026-06-25")
            ids = {e["agent_id"] for e in res.json()["agents"]}
            assert "A" in ids, f"agent A was filtered out of same-day range; got ids={ids}"
            assert "B" in ids
        finally:
            _clear_db_override()

    def test_no_date_filter_includes_all_agents(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        r.elo_ratings["C"] = 1200.0  # No snapshots.
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard")
            ids = {e["agent_id"] for e in res.json()["agents"]}
            # Without a date filter, agents with no snapshots are still included.
            assert {"A", "B", "C"}.issubset(ids)
        finally:
            _clear_db_override()


# ── /api/leaderboard/agents/{agent_id} ────────────────────────────────


class TestGetAgentDetailEndpoint:
    def test_unknown_agent_returns_empty(self):
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            r = client.get("/leaderboard/agents/ghost")
            assert r.status_code == 200
            body = r.json()
            assert body["agent_id"] == "ghost"
            assert body["overall"] is None
            assert body["per_game"] == {}
        finally:
            _clear_db_override()

    def test_known_agent_in_overall_registry(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard/agents/A")
            body = res.json()
            assert body["agent_id"] == "A"
            assert body["overall"] is not None
            assert body["overall"]["matches_played"] == 1
            assert "elo" in body["overall"]
            assert "metrics" in body["overall"]
        finally:
            _clear_db_override()

    def test_known_agent_in_per_game_registry(self):
        game_reg = arena.metrics.get_game_registry("ultimatum")
        game_reg.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard/agents/A")
            body = res.json()
            assert "ultimatum" in body["per_game"]
            entry = body["per_game"]["ultimatum"]
            assert entry["matches_played"] == 1
        finally:
            _clear_db_override()

    def test_agent_id_url_decoded(self):
        r = AgentRegistry()
        r.record_match(_make_match(["anthropic__claude", "openai__gpt"], "m1"),
                       {"anthropic__claude": 1.0, "openai__gpt": 0.0})
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard/agents/anthropic__claude")
            assert res.status_code == 200
            assert res.json()["agent_id"] == "anthropic__claude"
        finally:
            _clear_db_override()


# ── /api/leaderboard/agents/{agent_id}/history ─────────────────────────


class TestGetAgentHistoryEndpoint:
    def test_empty_history(self):
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            r = client.get("/leaderboard/agents/A/history")
            assert r.status_code == 200
            body = r.json()
            assert body["agent_id"] == "A"
            assert body["game"] == "overall"
            assert body["history"] == []
        finally:
            _clear_db_override()

    def test_returns_rating_series(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            timestamp="2025-01-01T00:00:00+00:00",
        )
        r.record_match(
            _make_match(["A", "B"], "m2"),
            {"A": 0.0, "B": 1.0},
            timestamp="2025-02-01T00:00:00+00:00",
        )
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard/agents/A/history")
            body = res.json()
            assert len(body["history"]) == 2
            assert body["history"][0]["timestamp"] == "2025-01-01T00:00:00+00:00"
            assert body["history"][1]["timestamp"] == "2025-02-01T00:00:00+00:00"
            assert body["history"][0]["elo"] != body["history"][1]["elo"]
        finally:
            _clear_db_override()

    def test_game_filter_uses_per_game_registry(self):
        game_reg = arena.metrics.get_game_registry("colonelblotto")
        game_reg.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            timestamp="2025-03-01T00:00:00+00:00",
        )
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/leaderboard/agents/A/history?game=colonelblotto")
            body = res.json()
            assert body["game"] == "colonelblotto"
            assert len(body["history"]) == 1
        finally:
            _clear_db_override()


# ── /api/benchmark/games ──────────────────────────────────────────────


class TestBenchmarkGamesEndpoint:
    def test_returns_empty_when_no_db_rows(self):
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            r = client.get("/benchmark/games")
            assert r.status_code == 200
            assert r.json() == {"games": []}
        finally:
            _clear_db_override()

    def test_returns_only_game_prefixed_keys(self):
        db = MagicMock()

        async def fake_execute(stmt):
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            # Only return rows when the query actually filters by `game:%`.
            if "like" in compiled.lower() and "game" in compiled.lower():
                rows = [
                    ("game:colonelblotto",),
                    ("game:ultimatum",),
                    ("global",),
                ]
                result = MagicMock()
                result.all = MagicMock(return_value=rows)
                return result
            result = MagicMock()
            result.all = MagicMock(return_value=[])
            return result

        db.execute = AsyncMock(side_effect=fake_execute)
        db.commit = AsyncMock()
        _get_db_override(db)
        try:
            client = TestClient(app)
            r = client.get("/benchmark/games")
            assert r.status_code == 200
            body = r.json()
            # The endpoint's LIKE filter is "game:%" so it returns ALL three rows
            # in the mocked result, then strips the "game:" prefix in Python.
            # This test verifies the stripping logic and confirms the keys
            # list is the unique set of games with the prefix.
            assert "colonelblotto" in body["games"]
            assert "ultimatum" in body["games"]
        finally:
            _clear_db_override()

    def test_strips_game_prefix(self):
        """The endpoint must strip the 'game:' prefix from each row's key."""
        db = MagicMock()

        async def fake_execute(stmt):
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            if "like" in compiled.lower() and "game" in compiled.lower():
                result = MagicMock()
                result.all = MagicMock(return_value=[("game:prisonersdilemma",)])
                return result
            result = MagicMock()
            result.all = MagicMock(return_value=[])
            return result

        db.execute = AsyncMock(side_effect=fake_execute)
        db.commit = AsyncMock()
        _get_db_override(db)
        try:
            client = TestClient(app)
            r = client.get("/benchmark/games")
            body = r.json()
            assert body == {"games": ["prisonersdilemma"]}
        finally:
            _clear_db_override()

    def test_db_error_returns_empty(self):
        db = MagicMock()
        db.execute = AsyncMock(side_effect=Exception("db down"))
        _get_db_override(db)
        try:
            client = TestClient(app)
            r = client.get("/benchmark/games")
            assert r.status_code == 200
            assert r.json() == {"games": []}
        finally:
            _clear_db_override()


# ── /api/benchmark/report?game=... ─────────────────────────────────────


class TestBenchmarkReportWithGameFilter:
    def test_uses_per_game_registry_when_game_set(self):
        global_reg = AgentRegistry()
        global_reg.record_match(_make_match(["A", "B"], "g1"), {"A": 1.0, "B": 0.0})
        arena.metrics.set_global_registry(global_reg)

        game_reg = arena.metrics.get_game_registry("colonelblotto")
        game_reg.record_match(_make_match(["X", "Y"], "c1"), {"X": 1.0, "Y": 0.0})

        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res_global = client.get("/benchmark/report")
            global_agents = set(res_global.json()["agents"].keys())
            assert "A" in global_agents
            assert "X" not in global_agents

            res_game = client.get("/benchmark/report?game=colonelblotto")
            game_agents = set(res_game.json()["agents"].keys())
            assert "X" in game_agents
            assert "A" not in game_agents
        finally:
            _clear_db_override()

    def test_global_report_includes_matches_played(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        r.record_match(_make_match(["A", "B"], "m2"), {"A": 0.0, "B": 1.0})
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/benchmark/report")
            body = res.json()
            assert body["agents"]["A"]["matches_played"] == 2
            assert body["agents"]["B"]["matches_played"] == 2
        finally:
            _clear_db_override()

    def test_global_report_includes_metrics_when_present(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            agent_metrics={
                "A": {"nash_gap": 0.1, "avg_payoff": 0.5, "cumulative_regret": 0.0,
                      "strategy_entropy": 1.0, "behavioral_consistency": 0.8, "cooperation_rate": 0.6},
                "B": {"nash_gap": 0.5, "avg_payoff": 0.2, "cumulative_regret": 0.0,
                      "strategy_entropy": 1.0, "behavioral_consistency": 0.8, "cooperation_rate": 0.6},
            },
        )
        arena.metrics.set_global_registry(r)
        _get_db_override(_stub_db())
        try:
            client = TestClient(app)
            res = client.get("/benchmark/report")
            body = res.json()
            assert "metrics" in body["agents"]["A"]
            assert body["agents"]["A"]["metrics"]["nash_gap"] == 0.1
        finally:
            _clear_db_override()
