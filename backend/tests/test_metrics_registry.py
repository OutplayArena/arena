"""Tests for the AgentRegistry (Elo, α-Rank, serialization)."""

from arena.metrics.contracts import Match
from arena.metrics.registry import AgentRegistry


def _make_match(agent_ids, match_id="m1"):
    return Match(match_id=match_id, game_type="ultimatum", agent_ids=agent_ids, moves=[])


class TestConstruction:
    def test_default_alpha(self):
        r = AgentRegistry()
        assert r.alpha == 50.0

    def test_custom_alpha(self):
        r = AgentRegistry(alpha=100.0)
        assert r.alpha == 100.0

    def test_default_elo_for_new_agent(self):
        r = AgentRegistry()
        assert r.elo_ratings["new-agent"] == 1200.0


class TestRecordMatch:
    def test_records_marginal_payoffs(self):
        r = AgentRegistry()
        match = _make_match(["A", "B"])
        r.record_match(match, {"A": 10.0, "B": 5.0})

        # Both (A,B) and (B,A) marginal records should be stored.
        assert r.marginal_payoffs["A"]["B"] == [(10.0, 5.0)]
        assert r.marginal_payoffs["B"]["A"] == [(5.0, 10.0)]

    def test_updates_elo_ratings(self):
        r = AgentRegistry()
        match = _make_match(["A", "B"])
        r.record_match(match, {"A": 10.0, "B": 0.0})
        assert r.elo_ratings["A"] > 1200.0
        assert r.elo_ratings["B"] < 1200.0

    def test_appends_to_match_history(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 1.0, "B": 1.0})
        r.record_match(_make_match(["A", "B"], "m2"), {"A": 2.0, "B": 2.0})
        assert r.match_history == ["m1", "m2"]


class TestMarginalMean:
    def test_empty_returns_none(self):
        r = AgentRegistry()
        assert r.marginal_mean("A", "B") is None

    def test_single_record(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"]), {"A": 10.0, "B": 5.0})
        ma, mb = r.marginal_mean("A", "B")
        assert ma == 10.0
        assert mb == 5.0

    def test_multiple_records_averaged(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"], "m1"), {"A": 10.0, "B": 5.0})
        r.record_match(_make_match(["A", "B"], "m2"), {"A": 20.0, "B": 15.0})
        ma, mb = r.marginal_mean("A", "B")
        assert ma == 15.0  # (10+20)/2
        assert mb == 10.0  # (5+15)/2


class TestBuildResponseGraph:
    def test_empty_when_no_matches(self):
        r = AgentRegistry()
        graph = r.build_response_graph(["A", "B"])
        assert graph == {}

    def test_returns_bidirectional_edges(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"]), {"A": 10.0, "B": 5.0})
        graph = r.build_response_graph(["A", "B"])
        assert ("A", "B") in graph
        assert ("B", "A") in graph


class TestComputeAlphaRankScores:
    def test_single_agent_returns_one(self):
        r = AgentRegistry()
        assert r.compute_alpha_rank_scores(["A"]) == {"A": 1.0}

    def test_empty_returns_empty(self):
        r = AgentRegistry()
        assert r.compute_alpha_rank_scores([]) == {}

    def test_two_agents_with_matches(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"]), {"A": 10.0, "B": 0.0})
        scores = r.compute_alpha_rank_scores(["A", "B"])
        assert "A" in scores
        assert "B" in scores
        # Probabilities sum to ~1.
        total = sum(scores.values())
        assert abs(total - 1.0) < 1e-6


class TestPopulationDiversity:
    def test_single_agent_diversity_is_zero(self):
        r = AgentRegistry()
        assert r.population_diversity(["A"]) == 0.0

    def test_empty_returns_zero(self):
        r = AgentRegistry()
        assert r.population_diversity([]) == 0.0

    def test_two_agents_diversity_positive(self):
        r = AgentRegistry()
        r.record_match(_make_match(["A", "B"]), {"A": 5.0, "B": 5.0})
        d = r.population_diversity(["A", "B"])
        assert d >= 0.0


class TestSerialization:
    def test_to_dict_round_trip(self):
        r1 = AgentRegistry(alpha=75.0)
        r1.record_match(_make_match(["A", "B"], "m1"), {"A": 10.0, "B": 5.0})
        r1.record_match(_make_match(["A", "B"], "m2"), {"A": 20.0, "B": 15.0})
        data = r1.to_dict()

        assert data["alpha"] == 75.0
        assert data["match_history"] == ["m1", "m2"]
        assert "A" in data["elo_ratings"]
        assert "B" in data["elo_ratings"]

        r2 = AgentRegistry.from_dict(data)
        assert r2.alpha == 75.0
        assert r2.match_history == ["m1", "m2"]
        assert r2.elo_ratings["A"] == r1.elo_ratings["A"]
        assert r2.marginal_payoffs["A"]["B"] == [(10.0, 5.0), (20.0, 15.0)]

    def test_from_dict_uses_default_alpha(self):
        r = AgentRegistry.from_dict({})
        assert r.alpha == 50.0
        assert r.match_history == []

    def test_from_dict_with_empty_elo_and_marginal(self):
        r = AgentRegistry.from_dict({"alpha": 30.0})
        assert r.alpha == 30.0
