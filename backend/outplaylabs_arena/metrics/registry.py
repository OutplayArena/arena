from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

import numpy as np

from outplaylabs_arena.metrics.contracts import Match
from outplaylabs_arena.metrics.ranking import RankingMetrics


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

    def record_match(self, match: Match, avg_payoffs: dict[str, float]) -> None:
        """
        Record a completed match. avg_payoffs maps agent_id → average payoff this match.
        Updates Elo ratings and marginal pairwise payoffs for α-Rank.
        """
        self.match_history.append(match.match_id)
        agents = match.agent_ids

        for a, b in combinations(agents, 2):
            pa, pb = avg_payoffs.get(a, 0.0), avg_payoffs.get(b, 0.0)
            self.marginal_payoffs[a][b].append((pa, pb))
            self.marginal_payoffs[b][a].append((pb, pa))

        elo_snapshot = {a: self.elo_ratings[a] for a in agents}
        updated = RankingMetrics.update_elo_multiplayer(elo_snapshot, avg_payoffs)
        for a, new_rating in updated.items():
            self.elo_ratings[a] = new_rating

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

    # ── serialization for DB persistence ────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "alpha": self.alpha,
            "elo_ratings": dict(self.elo_ratings),
            "marginal_payoffs": {
                a: {b: list(pairs) for b, pairs in inner.items()}
                for a, inner in self.marginal_payoffs.items()
            },
            "match_history": list(self.match_history),
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
        return registry
