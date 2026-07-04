"""Tests for arena.metrics.risk (RiskMetrics)."""

import pytest

from arena.metrics.risk import RiskMetrics, hhi


# ── payoff_volatility ──────────────────────────────────────────────────


class TestPayoffVolatility:
    def test_empty_payoffs(self):
        assert RiskMetrics.payoff_volatility([]) == 0.0

    def test_single_payoff(self):
        assert RiskMetrics.payoff_volatility([5.0]) == 0.0

    def test_constant_payoffs_zero_volatility(self):
        assert RiskMetrics.payoff_volatility([3.0, 3.0, 3.0]) == pytest.approx(0.0)

    def test_known_std(self):
        # population std of [1, 2, 3, 4] is sqrt(1.25) ≈ 1.1180339887
        result = RiskMetrics.payoff_volatility([1.0, 2.0, 3.0, 4.0])
        assert result == pytest.approx(1.1180339887, rel=1e-6)


# ── action_concentration ───────────────────────────────────────────────


class TestActionConcentration:
    def test_vector_actions_returns_float(self):
        result = RiskMetrics.action_concentration([[10, 0, 0], [0, 10, 0]])
        assert result is not None
        assert result == pytest.approx(1.0)

    def test_spread_allocation_low_concentration(self):
        result = RiskMetrics.action_concentration([[5, 5, 5, 5]])
        assert result is not None
        assert result == pytest.approx(0.25)

    def test_scalar_actions_return_none(self):
        assert RiskMetrics.action_concentration(["cooperate", "defect"]) is None

    def test_numeric_scalar_actions_return_none(self):
        assert RiskMetrics.action_concentration([0, 1, 0]) is None

    def test_empty_actions_return_none(self):
        assert RiskMetrics.action_concentration([]) is None

    def test_mixed_actions_filters_to_vectors_only(self):
        result = RiskMetrics.action_concentration(["fold", [10, 0], "raise"])
        assert result is not None
        assert result == pytest.approx(1.0)


# ── shared hhi helper (used by Colonel Blotto's metrics.py too) ────────


class TestHHI:
    def test_all_in_one_battlefield(self):
        assert hhi([10, 0, 0]) == pytest.approx(1.0)

    def test_evenly_spread(self):
        assert hhi([5, 5, 5, 5]) == pytest.approx(0.25)

    def test_zero_total(self):
        assert hhi([0, 0, 0]) == 0.0
