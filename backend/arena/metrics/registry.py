from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations

import numpy as np

from arena.metrics.contracts import Match
from arena.metrics.ranking import RankingMetrics

# Metrics aggregated from MatchEvaluator for display on the leaderboard.
# These are stored as running sums and averaged when the report is built.
_AGGREGATED_METRICS = frozenset({
    "avg_payoff",
    "nash_gap",
    "cumulative_regret",
    "strategy_entropy",
    "behavioral_consistency",
    "cooperation_rate",
    "payoff_volatility",
})


class AgentRegistry:
    """
    Stateful accumulator of payoff data across matches for α-Rank and Elo.

    N-player α-Rank uses polymatrix marginalisation:
      For each ordered pair (i, j), the marginal payoff of i vs. j is the
      average of i's payoff in all matches where both i and j participated,
      treating all other agents as background (averaged out).

    This is the standard tractable extension of α-Rank to N > 2.
    """

    def __init__(self, alpha: float = 50.0):
        self.alpha = alpha
        self.elo_ratings: dict[str, float] = defaultdict(lambda: 1200.0)
        # marginal_payoffs[i][j] = list of (payoff_i, payoff_j) from matches containing both
        self.marginal_payoffs: dict[str, dict[str, list[tuple[float, float]]]] = \
            defaultdict(lambda: defaultdict(list))
        self.match_history: list[str] = []
        self.matches_played: dict[str, int] = defaultdict(int)
        # Running sums of per-agent metrics across all matches
        self.agg_metrics: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.agg_metric_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # Match timestamps for time-range filtering (match_id -> isoformat str)
        self.match_timestamps: dict[str, str] = {}
        # Elo history snapshots for rating-over-time charts (agent_id -> [(ts, elo)])
        self.elo_snapshots: dict[str, list[tuple[str, float]]] = defaultdict(list)

    def record_match(
        self,
        match: Match,
        avg_payoffs: dict[str, float],
        agent_metrics: dict[str, dict] | None = None,
        timestamp: str | None = None,
    ) -> None:
        """
        Record a completed match. avg_payoffs maps agent_id → average payoff this match.
        Updates Elo ratings, marginal pairwise payoffs, and aggregated metrics for α-Rank.
        agent_metrics is an optional dict of {agent_id: {metric_name: value}} from the
        MatchEvaluator, used to build leaderboard columns (nash_gap, regret, etc.).
        timestamp is an ISO-8601 string; defaults to now if not provided.
        """
        if match.match_id in self.match_history:
            return
        self.match_history.append(match.match_id)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        self.match_timestamps[match.match_id] = ts

        agents = match.agent_ids
        for a in agents:
            self.matches_played[a] += 1

        for a, b in combinations(agents, 2):
            pa, pb = avg_payoffs.get(a, 0.0), avg_payoffs.get(b, 0.0)
            self.marginal_payoffs[a][b].append((pa, pb))
            self.marginal_payoffs[b][a].append((pb, pa))

        elo_snapshot = {a: self.elo_ratings[a] for a in agents}
        updated = RankingMetrics.update_elo_multiplayer(elo_snapshot, avg_payoffs)
        for a, new_rating in updated.items():
            self.elo_ratings[a] = new_rating
            self.elo_snapshots[a].append((ts, new_rating))

        if agent_metrics:
            for agent_id, metrics in agent_metrics.items():
                for key in _AGGREGATED_METRICS:
                    val = metrics.get(key)
                    if val is not None and isinstance(val, (int, float)) and math.isfinite(val):
                        self.agg_metrics[agent_id][key] += val
                        self.agg_metric_counts[agent_id][key] += 1

    def marginal_mean(self, a: str, b: str) -> tuple[float, float] | None:
        records = self.marginal_payoffs.get(a, {}).get(b, [])
        if not records:
            return None
        return (
            float(np.mean([r[0] for r in records])),
            float(np.mean([r[1] for r in records])),
        )

    def build_response_graph(self, agent_ids: list[str]) -> dict[tuple[str, str], float]:
        """
        Directed response graph edge weights for α-Rank.
        Edge (A→B) = fixation probability of A invading a population of B.
        Uses polymatrix marginalisation for N > 2.
        """
        graph = {}
        for a, b in combinations(agent_ids, 2):
            payoffs = self.marginal_mean(a, b)
            if payoffs is None:
                continue
            pa, pb = payoffs
            graph[(a, b)] = RankingMetrics.alpha_rank_fixation_probability(
                pa, pb, alpha=self.alpha
            )
            graph[(b, a)] = RankingMetrics.alpha_rank_fixation_probability(
                pb, pa, alpha=self.alpha
            )
        return graph

    def compute_alpha_rank_scores(self, agent_ids: list[str]) -> dict[str, float]:
        """
        α-Rank stationary distribution — the definitive multi-agent ranking.
        Higher mass = more evolutionarily dominant strategy.
        """
        n = len(agent_ids)
        if n < 2:
            return {agent_ids[0]: 1.0} if agent_ids else {}

        graph = self.build_response_graph(agent_ids)
        idx   = {a: i for i, a in enumerate(agent_ids)}

        T = np.zeros((n, n))
        for (a, b), fp in graph.items():
            i, j = idx[a], idx[b]
            # graph[(a,b)] = P(a invades b's population) = P(transition: b's state → a's state)
            # So T[j][i] = P(population moves from "everyone plays b" to "everyone plays a")
            T[j][i] += fp / (n - 1)

        for i in range(n):
            T[i][i] = max(0.0, 1.0 - sum(T[i][j] for j in range(n) if j != i))

        dist = np.ones(n) / n
        for _ in range(2000):
            new = dist @ T
            if np.max(np.abs(new - dist)) < 1e-9:
                break
            dist = new

        return {agent_ids[i]: float(dist[i]) for i in range(n)}

    def population_diversity(self, agent_ids: list[str]) -> float:
        """Shannon entropy of the α-Rank distribution — higher = more diverse ecosystem."""
        scores = self.compute_alpha_rank_scores(agent_ids)
        total  = sum(scores.values())
        if total == 0:
            return 0.0
        probs = [v / total for v in scores.values()]
        return float(-sum(p * math.log2(p) for p in probs if p > 0))

    def aggregated_metrics(self, agent_ids: list[str]) -> dict[str, dict[str, float]]:
        """Return per-agent averages of all tracked metrics for the leaderboard."""
        result = {}
        for agent_id in agent_ids:
            row = {}
            counts = self.agg_metric_counts.get(agent_id, {})
            sums = self.agg_metrics.get(agent_id, {})
            for key in _AGGREGATED_METRICS:
                c = counts.get(key, 0)
                if c > 0:
                    row[key] = sums[key] / c
            if row:
                result[agent_id] = row
        return result

    def get_rating_history(self, agent_id: str) -> list[tuple[str, float]]:
        """Return the (timestamp, elo) snapshot series for a given agent."""
        return list(self.elo_snapshots.get(agent_id, []))

    # ── serialization for DB persistence ────────────────────────────────────

    def clear(self) -> None:
        """Reset all state to empty — used before a full leaderboard rebuild."""
        self.elo_ratings = defaultdict(lambda: 1200.0)
        self.marginal_payoffs = defaultdict(lambda: defaultdict(list))
        self.match_history = []
        self.matches_played = defaultdict(int)
        self.agg_metrics = defaultdict(lambda: defaultdict(float))
        self.agg_metric_counts = defaultdict(lambda: defaultdict(int))
        self.match_timestamps = {}
        self.elo_snapshots = defaultdict(list)

    def to_dict(self) -> dict:
        return {
            "alpha": self.alpha,
            "elo_ratings": dict(self.elo_ratings),
            "marginal_payoffs": {
                a: {b: list(pairs) for b, pairs in inner.items()}
                for a, inner in self.marginal_payoffs.items()
            },
            "match_history": list(self.match_history),
            "matches_played": dict(self.matches_played),
            "match_timestamps": dict(self.match_timestamps),
            "agg_metrics": {a: dict(d) for a, d in self.agg_metrics.items()},
            "agg_metric_counts": {a: dict(d) for a, d in self.agg_metric_counts.items()},
            "elo_snapshots": {a: list(pairs) for a, pairs in self.elo_snapshots.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentRegistry":
        registry = cls(alpha=data.get("alpha", 50.0))
        for agent, rating in data.get("elo_ratings", {}).items():
            registry.elo_ratings[agent] = rating
        for a, inner in data.get("marginal_payoffs", {}).items():
            for b, pairs in inner.items():
                registry.marginal_payoffs[a][b] = [tuple(p) for p in pairs]
        registry.match_history = data.get("match_history", [])
        for agent, count in data.get("matches_played", {}).items():
            registry.matches_played[agent] = count
        registry.match_timestamps = dict(data.get("match_timestamps", {}))
        for agent, metrics in data.get("agg_metrics", {}).items():
            for key, val in metrics.items():
                registry.agg_metrics[agent][key] = val
        for agent, counts in data.get("agg_metric_counts", {}).items():
            for key, val in counts.items():
                registry.agg_metric_counts[agent][key] = val
        for agent, pairs in data.get("elo_snapshots", {}).items():
            registry.elo_snapshots[agent] = [tuple(p) for p in pairs]
        return registry
