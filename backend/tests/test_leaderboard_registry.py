"""Tests for the new AgentRegistry fields and methods added for the leaderboard.

Covers:
- matches_played counter
- match_timestamps
- elo_snapshots
- agg_metrics / aggregated_metrics
- get_rating_history
- record_match idempotency
- to_dict / from_dict roundtrip for the new fields
"""
from datetime import datetime

import pytest

from arena.metrics.contracts import Match
from arena.metrics.registry import AgentRegistry, _AGGREGATED_METRICS


def _make_match(agent_ids, match_id="m1", game_type="ultimatum"):
    return Match(match_id=match_id, game_type=game_type, agent_ids=agent_ids, moves=[])


def _make_metrics(**kwargs):
    base = {
        "avg_payoff": 0.5,
        "nash_gap": 0.1,
        "cumulative_regret": 0.2,
        "strategy_entropy": 1.5,
        "behavioral_consistency": 0.8,
        "cooperation_rate": 0.6,
    }
    base.update(kwargs)
    return base


# ── matches_played ──────────────────────────────────────────────────────


class TestMatchesPlayed:
    def test_initial_state_is_zero(self):
        r = AgentRegistry()
        assert dict(r.matches_played) == {}

    def test_increments_per_match(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        assert r.matches_played["A"] == 1
        assert r.matches_played["B"] == 1

        r.record_match(_make_match(["A", "B"], "m2"), {"A": 1.0, "B": 0.0})
        assert r.matches_played["A"] == 2
        assert r.matches_played["B"] == 2

    def test_increments_for_all_agents_in_multiplayer(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B", "C"], "m1"), {"A": 1.0, "B": 0.5, "C": 0.0})
        assert r.matches_played == {"A": 1, "B": 1, "C": 1}

    def test_idempotent_does_not_increment(self):
        r = AgentRegistry()
        m = _make_match(["A", "B"], "m1")
        r.record_match(m, {"A": 1.0, "B": 0.0})
        r.record_match(m, {"A": 99.0, "B": 99.0})
        assert r.matches_played == {"A": 1, "B": 1}


# ── match_timestamps ────────────────────────────────────────────────────


class TestMatchTimestamps:
    def test_initial_state_empty(self):
        r = AgentRegistry()
        assert r.match_timestamps == {}

    def test_default_timestamp_is_iso_utc(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        ts = r.match_timestamps["m1"]
        assert isinstance(ts, str)
        # ISO 8601 with timezone offset.
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_explicit_timestamp_is_used(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            timestamp="2025-06-15T12:00:00+00:00",
        )
        assert r.match_timestamps["m1"] == "2025-06-15T12:00:00+00:00"


# ── elo_snapshots ───────────────────────────────────────────────────────


class TestEloSnapshots:
    def test_initial_state_empty(self):
        r = AgentRegistry()
        assert dict(r.elo_snapshots) == {}

    def test_snapshot_appended_per_match(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        r.record_match(_make_match(["A", "B"], "m2"), {"A": 0.0, "B": 1.0})
        assert len(r.elo_snapshots["A"]) == 2
        assert len(r.elo_snapshots["B"]) == 2
        # All snapshots have timestamps and a float elo.
        for ts, elo in r.elo_snapshots["A"]:
            assert isinstance(ts, str)
            assert isinstance(elo, float)

    def test_elo_changes_visible_across_snapshots(self):
        r = AgentRegistry()
        m1 = _make_match(["A", "B"], "m1")
        r.record_match(m1, {"A": 10.0, "B": 0.0})
        elo_after_m1 = r.elo_snapshots["A"][-1][1]

        r.record_match(_make_match(["A", "B"], "m2"), {"A": 0.0, "B": 10.0})
        elo_after_m2 = r.elo_snapshots["A"][-1][1]

        assert elo_after_m1 != elo_after_m2

    def test_idempotent_does_not_add_snapshot(self):
        r = AgentRegistry()
        m = _make_match(["A", "B"], "m1")
        r.record_match(m, {"A": 1.0, "B": 0.0})
        r.record_match(m, {"A": 99.0, "B": 99.0})
        assert len(r.elo_snapshots["A"]) == 1


# ── aggregated metrics ──────────────────────────────────────────────────


class TestAggregatedMetrics:
    def test_initial_state_empty(self):
        r = AgentRegistry()
        assert r.aggregated_metrics(["A", "B"]) == {}

    def test_averages_tracked_metrics(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            agent_metrics={"A": _make_metrics(nash_gap=0.4), "B": _make_metrics(nash_gap=0.2)},
        )
        r.record_match(
            _make_match(["A", "B"], "m2"),
            {"A": 1.0, "B": 0.0},
            agent_metrics={"A": _make_metrics(nash_gap=0.6), "B": _make_metrics(nash_gap=0.4)},
        )
        agg = r.aggregated_metrics(["A", "B"])
        assert agg["A"]["nash_gap"] == pytest.approx(0.5)
        assert agg["B"]["nash_gap"] == pytest.approx(0.3)

    def test_ignores_non_tracked_metric_keys(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A"], "m1"),
            {"A": 1.0},
            agent_metrics={"A": {"some_random_metric": 99.0, "nash_gap": 0.1}},
        )
        agg = r.aggregated_metrics(["A"])
        assert "some_random_metric" not in agg["A"]
        assert agg["A"]["nash_gap"] == pytest.approx(0.1)

    def test_ignores_none_values(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A"], "m1"),
            {"A": 1.0},
            agent_metrics={"A": {"nash_gap": None}},
        )
        assert r.aggregated_metrics(["A"]) == {}

    def test_ignores_non_finite_values(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A"], "m1"),
            {"A": 1.0},
            agent_metrics={"A": {"nash_gap": float("inf")}},
        )
        assert r.aggregated_metrics(["A"]) == {}

    def test_ignores_non_numeric_values(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A"], "m1"),
            {"A": 1.0},
            agent_metrics={"A": {"nash_gap": "not a number"}},
        )
        assert r.aggregated_metrics(["A"]) == {}

    def test_handles_missing_agent_in_request(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A"], "m1"),
            {"A": 1.0},
            agent_metrics={"A": _make_metrics()},
        )
        assert r.aggregated_metrics(["A", "B"]) == {"A": pytest.approx(_make_metrics(), abs=1e-9)}

    def test_aggregated_metrics_set_is_complete(self):
        assert _AGGREGATED_METRICS == frozenset({
            "avg_payoff",
            "nash_gap",
            "cumulative_regret",
            "strategy_entropy",
            "behavioral_consistency",
            "cooperation_rate",
            "payoff_volatility",
            "action_concentration",
        })


# ── get_rating_history ──────────────────────────────────────────────────


class TestGetRatingHistory:
    def test_empty_for_unknown_agent(self):
        r = AgentRegistry()
        assert r.get_rating_history("ghost") == []

    def test_returns_copy_of_snapshots(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        history = r.get_rating_history("A")
        assert len(history) == 1
        # Mutating the returned list must not affect the registry.
        history.clear()
        assert len(r.elo_snapshots["A"]) == 1

    def test_returns_tuples(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A"], "m1"), {"A": 1.0})
        history = r.get_rating_history("A")
        assert all(isinstance(p, tuple) and len(p) == 2 for p in history)


# ── record_match idempotency ────────────────────────────────────────────


class TestRecordMatchIdempotency:
    def test_duplicate_match_id_does_not_double_count_elo(self):
        r = AgentRegistry()
        m = _make_match(["A", "B"], "m1")
        r.record_match(m, {"A": 1.0, "B": 0.0})
        elo_a_after_first = r.elo_ratings["A"]
        elo_b_after_first = r.elo_ratings["B"]

        # Calling again with a different outcome must not change ratings.
        r.record_match(m, {"A": 0.0, "B": 1.0})
        assert r.elo_ratings["A"] == elo_a_after_first
        assert r.elo_ratings["B"] == elo_b_after_first

    def test_duplicate_match_id_does_not_double_count_marginal(self):
        r = AgentRegistry()
        m = _make_match(["A", "B"], "m1")
        r.record_match(m, {"A": 1.0, "B": 0.0})
        r.record_match(m, {"A": 5.0, "B": 5.0})
        assert len(r.marginal_payoffs["A"]["B"]) == 1
        assert r.marginal_payoffs["A"]["B"] == [(1.0, 0.0)]

    def test_duplicate_match_id_does_not_double_count_aggregated(self):
        r = AgentRegistry()
        m = _make_match(["A"], "m1")
        r.record_match(m, {"A": 1.0}, agent_metrics={"A": _make_metrics(nash_gap=0.1)})
        r.record_match(m, {"A": 1.0}, agent_metrics={"A": _make_metrics(nash_gap=0.9)})
        # Average should still be 0.1, not 0.5.
        assert r.aggregated_metrics(["A"])["A"]["nash_gap"] == pytest.approx(0.1)

    def test_distinct_match_ids_both_recorded(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 0.0})
        r.record_match(_make_match(["A", "B"], "m2"), {"A": 0.0, "B": 1.0})
        assert r.match_history == ["m1", "m2"]
        assert r.matches_played == {"A": 2, "B": 2}


# ── serialization roundtrip ────────────────────────────────────────────


class TestSerializationWithNewFields:
    def test_to_dict_includes_all_new_fields(self):
        r = AgentRegistry()
        r.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            agent_metrics={"A": _make_metrics(nash_gap=0.5)},
            timestamp="2025-01-01T00:00:00+00:00",
        )
        data = r.to_dict()
        assert "matches_played" in data
        assert "match_timestamps" in data
        assert "agg_metrics" in data
        assert "agg_metric_counts" in data
        assert "elo_snapshots" in data
        assert data["matches_played"] == {"A": 1, "B": 1}
        assert data["match_timestamps"]["m1"] == "2025-01-01T00:00:00+00:00"
        assert data["agg_metrics"]["A"]["nash_gap"] == 0.5
        assert data["agg_metric_counts"]["A"]["nash_gap"] == 1
        assert len(data["elo_snapshots"]["A"]) == 1

    def test_from_dict_roundtrip_preserves_all_fields(self):
        r1 = AgentRegistry(alpha=75.0)
        r1.record_match(
            _make_match(["A", "B"], "m1"),
            {"A": 1.0, "B": 0.0},
            agent_metrics={"A": _make_metrics(nash_gap=0.5)},
            timestamp="2025-01-01T00:00:00+00:00",
        )
        r1.record_match(
            _make_match(["A", "B"], "m2"),
            {"A": 0.0, "B": 1.0},
            agent_metrics={"B": _make_metrics(nash_gap=0.3)},
            timestamp="2025-01-02T00:00:00+00:00",
        )
        data = r1.to_dict()
        r2 = AgentRegistry.from_dict(data)

        assert r2.alpha == 75.0
        assert r2.matches_played == {"A": 2, "B": 2}
        assert r2.match_timestamps == r1.match_timestamps
        assert dict(r2.agg_metrics) == dict(r1.agg_metrics)
        assert dict(r2.agg_metric_counts) == dict(r1.agg_metric_counts)
        assert r2.elo_snapshots["A"] == r1.elo_snapshots["A"]
        assert r2.elo_snapshots["B"] == r1.elo_snapshots["B"]
        assert r2.match_history == r1.match_history
        assert r2.elo_ratings == r1.elo_ratings

    def test_from_dict_legacy_format_without_new_fields(self):
        """Old serialized data (pre-PR) should still load cleanly."""
        legacy = {
            "alpha": 50.0,
            "elo_ratings": {"A": 1500.0, "B": 1300.0},
            "marginal_payoffs": {"A": {"B": [(10.0, 5.0)]}},
            "match_history": ["m1"],
        }
        r = AgentRegistry.from_dict(legacy)
        assert r.elo_ratings == {"A": 1500.0, "B": 1300.0}
        assert r.match_history == ["m1"]
        assert dict(r.matches_played) == {}
        assert r.match_timestamps == {}
        assert dict(r.agg_metrics) == {}
        assert dict(r.agg_metric_counts) == {}
        assert dict(r.elo_snapshots) == {}

    def test_aggregated_metrics_after_roundtrip(self):
        r1 = AgentRegistry()
        r1.record_match(
            _make_match(["A"], "m1"),
            {"A": 1.0},
            agent_metrics={"A": _make_metrics(nash_gap=0.4)},
        )
        r1.record_match(
            _make_match(["A"], "m2"),
            {"A": 1.0},
            agent_metrics={"A": _make_metrics(nash_gap=0.6)},
        )
        r2 = AgentRegistry.from_dict(r1.to_dict())
        assert r2.aggregated_metrics(["A"])["A"]["nash_gap"] == pytest.approx(0.5)
