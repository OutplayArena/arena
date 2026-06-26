"""Coverage tests for arena.metrics helpers and arena.messaging broker ABC.

Targets the uncovered lines in:
- backend/arena/metrics/cooperative.py (CooperativeMetrics)
- backend/arena/metrics/behavioral.py (BehavioralMetrics)
- backend/arena/manifest.py (build_agent_manifest edge cases)
- backend/arena/messaging/broker.py (MessageBroker abstract methods)
- backend/arena/messaging/redis_broker.py (init error path, default URL)
"""

import pytest

from arena.manifest import build_agent_manifest
from arena.messaging.broker import MessageBroker
from arena.messaging.redis_broker import RedisBroker
from arena.metrics.behavioral import BehavioralMetrics
from arena.metrics.cooperative import CooperativeMetrics


# ── CooperativeMetrics ─────────────────────────────────────────────────


class TestCooperationRate:
    def test_empty_actions(self):
        assert CooperativeMetrics.cooperation_rate([]) == 0.0

    def test_all_cooperate(self):
        assert CooperativeMetrics.cooperation_rate([1, 1, 1, 1]) == 1.0

    def test_all_defect(self):
        assert CooperativeMetrics.cooperation_rate([0, 0, 0]) == 0.0

    def test_mixed(self):
        assert CooperativeMetrics.cooperation_rate([1, 0, 1, 0]) == 0.5


class TestConditionalCooperationRates:
    def test_short_history_returns_zeros(self):
        result = CooperativeMetrics.conditional_cooperation_rates(
            [1], {"opp": [1]}
        )
        assert result == {"opp": {"after_cooperate": 0.0, "after_defect": 0.0}}

    def test_with_enough_data(self):
        own = [1, 1, 0, 1]
        opp = {"alice": [1, 0, 1, 0]}
        result = CooperativeMetrics.conditional_cooperation_rates(own, opp)
        assert "alice" in result
        assert "after_cooperate" in result["alice"]
        assert "after_defect" in result["alice"]


class TestTitForTatAdherence:
    def test_empty_own_actions(self):
        result = CooperativeMetrics.tit_for_tat_adherence([], {"opp": [1, 0]})
        assert result == {"opp": 0.0}

    def test_perfect_tft(self):
        own = [1, 0, 1, 0, 1]
        opp = {"bob": [0, 1, 0, 1, 0]}
        result = CooperativeMetrics.tit_for_tat_adherence(own, opp)
        assert result["bob"] == 1.0

    def test_tft_always_cooperate(self):
        own = [1, 1, 1, 1]
        opp = {"bob": [0, 0, 0, 0]}
        result = CooperativeMetrics.tit_for_tat_adherence(own, opp)
        assert result["bob"] == 0.25


class TestForgivenessIndex:
    def test_no_defections_returns_zero(self):
        own = [1, 1, 1, 1]
        opp = {"x": [1, 1, 1, 1]}
        result = CooperativeMetrics.forgiveness_index(own, opp)
        assert result["x"] == 0.0

    def test_defection_with_forgiveness(self):
        own = [1, 0, 0, 1]
        opp = {"x": [1, 0, 0, 0]}
        result = CooperativeMetrics.forgiveness_index(own, opp)
        assert "x" in result
        assert result["x"] > 0.0


class TestMultilateralCooperationIndex:
    def test_empty(self):
        assert CooperativeMetrics.multilateral_cooperation_index({}) == []

    def test_with_data(self):
        all_actions = {
            "A": [1, 0, 1],
            "B": [0, 0, 1],
            "C": [1, 1, 1],
        }
        result = CooperativeMetrics.multilateral_cooperation_index(all_actions)
        assert len(result) == 3
        assert result[0] == pytest.approx(2 / 3)
        assert result[2] == 1.0


class TestPairwiseReciprocityMatrix:
    def test_short_history(self):
        result = CooperativeMetrics.pairwise_reciprocity_matrix(
            {"a": [1], "b": [0]}, ["a", "b"]
        )
        assert result[("a", "b")] == 0.0
        assert result[("b", "a")] == 0.0

    def test_with_correlated_data(self):
        all_actions = {
            "a": [1, 1, 1, 0, 0],
            "b": [0, 1, 1, 1, 0],
        }
        result = CooperativeMetrics.pairwise_reciprocity_matrix(all_actions, ["a", "b"])
        assert ("a", "b") in result
        assert ("b", "a") in result

    def test_constant_actions_yield_zero(self):
        all_actions = {"a": [1, 1, 1, 1], "b": [0, 0, 0, 0]}
        result = CooperativeMetrics.pairwise_reciprocity_matrix(all_actions, ["a", "b"])
        assert result[("a", "b")] == 0.0
        assert result[("b", "a")] == 0.0


class TestGiniCoefficient:
    def test_empty(self):
        assert CooperativeMetrics.gini_coefficient([]) == 0.0

    def test_all_zero(self):
        assert CooperativeMetrics.gini_coefficient([0, 0, 0]) == 0.0

    def test_equal_payoffs_near_zero(self):
        result = CooperativeMetrics.gini_coefficient([10, 10, 10, 10])
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_unequal_payoffs_positive(self):
        result = CooperativeMetrics.gini_coefficient([1, 1, 1, 100])
        assert 0 < result < 1


class TestPriceOfAnarchy:
    def test_zero_nash_returns_inf(self):
        result = CooperativeMetrics.price_of_anarchy(10.0, 0.0)
        assert result == float("inf")

    def test_normal_case(self):
        result = CooperativeMetrics.price_of_anarchy(10.0, 5.0)
        assert result == 2.0


class TestCoalitionPayoffImprovement:
    def test_improvement_for_each_agent(self):
        result = CooperativeMetrics.coalition_payoff_improvement(
            {"a": 1.0, "b": 1.0},
            {"a": 2.0, "b": 3.0},
        )
        assert result["a"] == pytest.approx(1.0)
        assert result["b"] == pytest.approx(2.0)

    def test_zero_solo_returns_inf(self):
        result = CooperativeMetrics.coalition_payoff_improvement(
            {"a": 0.0, "b": 1.0},
            {"a": 5.0, "b": 1.0},
        )
        assert result["a"] == float("inf")
        assert result["b"] == 0.0


class TestShapleyValueDeviation:
    def test_deviation_positive_and_negative(self):
        result = CooperativeMetrics.shapley_value_deviation(
            actual_payoffs={"a": 10.0, "b": 5.0},
            shapley_values={"a": 8.0, "b": 7.0},
        )
        assert result["a"] == pytest.approx(2.0)
        assert result["b"] == pytest.approx(-2.0)

    def test_only_actual_payoffs(self):
        result = CooperativeMetrics.shapley_value_deviation(
            actual_payoffs={"a": 10.0}, shapley_values={}
        )
        assert result["a"] == 10.0

    def test_only_shapley_values(self):
        result = CooperativeMetrics.shapley_value_deviation(
            actual_payoffs={}, shapley_values={"a": 5.0}
        )
        assert result["a"] == -5.0


# ── BehavioralMetrics ──────────────────────────────────────────────────


class TestStrategyEntropy:
    def test_empty_actions(self):
        assert BehavioralMetrics.strategy_entropy([]) == 0.0

    def test_single_action(self):
        assert BehavioralMetrics.strategy_entropy([1]) == 0.0

    def test_two_equal_actions(self):
        result = BehavioralMetrics.strategy_entropy([1, 0])
        assert result == pytest.approx(1.0)

    def test_uniform_distribution(self):
        result = BehavioralMetrics.strategy_entropy([0, 1, 2, 3])
        assert result == pytest.approx(2.0)

    def test_list_actions_are_tupleized(self):
        result = BehavioralMetrics.strategy_entropy([[1, 0], [1, 0], [0, 1]])
        assert result > 0


class TestBehavioralConsistency:
    def test_zero_actions(self):
        assert BehavioralMetrics.behavioral_consistency([]) == 1.0

    def test_one_unique(self):
        assert BehavioralMetrics.behavioral_consistency([1, 1, 1]) == 1.0

    def test_two_uniques(self):
        result = BehavioralMetrics.behavioral_consistency([0, 1, 0, 1])
        assert 0 <= result <= 1

    def test_max_diversity(self):
        result = BehavioralMetrics.behavioral_consistency([0, 1, 2, 3, 4, 5, 6, 7])
        assert result == pytest.approx(0.0)


class TestRegret:
    def test_zero_regret(self):
        result = BehavioralMetrics.regret([5.0, 5.0, 5.0], 5.0)
        assert result == 0.0

    def test_positive_regret(self):
        result = BehavioralMetrics.regret([3.0, 3.0], 5.0)
        assert result == pytest.approx(4.0)

    def test_realized_exceeds_best_returns_zero(self):
        result = BehavioralMetrics.regret([10.0, 10.0], 5.0)
        assert result == 0.0


class TestAdaptiveRegret:
    def test_empty(self):
        assert BehavioralMetrics.adaptive_regret([]) == []

    def test_windowed(self):
        realized = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = BehavioralMetrics.adaptive_regret(realized, window=2)
        assert len(result) == 3
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(1.0)

    def test_default_window(self):
        realized = list(range(20))
        result = BehavioralMetrics.adaptive_regret(realized)
        assert len(result) == 2


class TestOpponentPredictionAccuracy:
    def test_empty_lists(self):
        assert BehavioralMetrics.opponent_prediction_accuracy([], []) == 0.0

    def test_mismatched_lengths(self):
        assert BehavioralMetrics.opponent_prediction_accuracy([1], [1, 0]) == 0.0

    def test_perfect_prediction(self):
        result = BehavioralMetrics.opponent_prediction_accuracy(
            [1, 0, 1], [1, 0, 1]
        )
        assert result == 1.0

    def test_zero_prediction(self):
        result = BehavioralMetrics.opponent_prediction_accuracy(
            [1, 1, 1], [0, 0, 0]
        )
        assert result == 0.0

    def test_list_predictions(self):
        result = BehavioralMetrics.opponent_prediction_accuracy(
            [[1, 0], [0, 1]], [[1, 0], [0, 1]]
        )
        assert result == 1.0


class TestPerOpponentPredictionAccuracy:
    def test_per_opponent_breakdown(self):
        predicted = {"alice": [1, 0, 1], "bob": [0, 1, 0]}
        actual = {"alice": [1, 0, 1], "bob": [0, 0, 0]}
        result = BehavioralMetrics.per_opponent_prediction_accuracy(predicted, actual)
        assert result["alice"] == 1.0
        assert 0 <= result["bob"] <= 1

    def test_missing_opponent(self):
        predicted = {"alice": [1]}
        actual = {"alice": [1], "bob": [0]}
        result = BehavioralMetrics.per_opponent_prediction_accuracy(predicted, actual)
        assert result["alice"] == 1.0
        assert result["bob"] == 0.0


# ── MessageBroker ABC ───────────────────────────────────────────────────


class TestMessageBrokerAbstract:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            MessageBroker()

    def test_subclass_must_implement_all_methods(self):
        class IncompleteBroker(MessageBroker):
            async def publish(self, channel, message):
                pass

        with pytest.raises(TypeError):
            IncompleteBroker()

    def test_subclass_with_all_methods_is_instantiable(self):
        class CompleteBroker(MessageBroker):
            async def publish(self, channel, message):
                pass
            async def subscribe(self, channel):
                return
                yield None
            async def enqueue(self, queue, message):
                pass
            async def dequeue(self, queue, timeout=5):
                return None
            async def cache_set(self, key, value, ttl=300):
                pass
            async def cache_get(self, key):
                return None
            async def close(self):
                pass

        broker = CompleteBroker()
        assert broker is not None


# ── Manifest edge cases ─────────────────────────────────────────────────


class TestBuildAgentManifestEdgeCases:
    def test_manifest_with_no_skill_file(self, tmp_path, monkeypatch):
        from arena.game_registry import GameRegistry
        (tmp_path / "core").mkdir()
        game_dir = tmp_path / "core" / "no_skill_game"
        game_dir.mkdir()
        (game_dir / "game.yaml").write_text(
            'name: no-skill\nversion: "1.0"\nstatus: stable\nplayers: {min: 2, max: 2}\nontology: {timing: single_round}\n',
            encoding="utf-8",
        )
        (game_dir / "prompts.yaml").write_text(
            "action_format:\n  type: json_array\n",
            encoding="utf-8",
        )
        (game_dir / "metrics.yaml").write_text("metrics:\n  - total_payoff\n", encoding="utf-8")
        monkeypatch.setenv("API_PREFIX", "")
        manifest = build_agent_manifest(
            "no_skill_game", registry=GameRegistry(tmp_path), mcp_url=None
        )
        assert manifest["game"] == "no_skill_game"
        assert manifest["skill"]["title"] == ""
        assert manifest["mcp_endpoint"] == ""

    def test_manifest_with_mcp_url(self):
        manifest = build_agent_manifest("colonelblotto", mcp_url="https://example.com/mcp")
        assert manifest["mcp_endpoint"] == "https://example.com/mcp"

    def test_manifest_default_registry(self):
        manifest = build_agent_manifest("colonelblotto")
        assert manifest["platform"] == "outplaylabs-arena"
        assert manifest["manifest_version"] == "1.0"

    def test_manifest_includes_metrics(self):
        manifest = build_agent_manifest("colonelblotto")
        assert "metric_names" in manifest
        assert "total_payoff" in manifest["metric_names"]


# ── RedisBroker init error path ─────────────────────────────────────────


class TestRedisBrokerInit:
    def test_init_raises_when_redis_not_installed(self, monkeypatch):
        import arena.messaging.redis_broker as rb

        monkeypatch.setattr(rb, "aioredis", None)
        with pytest.raises(RuntimeError, match="redis is not installed"):
            RedisBroker(redis_url="redis://x")

    def test_default_redis_url_from_env(self, monkeypatch):
        from arena.messaging import redis_broker

        monkeypatch.setenv("REDIS_URL", "redis://custom:1234/5")
        result = redis_broker._default_redis_url()
        assert result == "redis://custom:1234/5"

    def test_default_redis_url_fallback(self, monkeypatch):
        from arena.messaging import redis_broker

        monkeypatch.delenv("REDIS_URL", raising=False)
        result = redis_broker._default_redis_url()
        assert result == "redis://localhost:6379/0"
