"""
Agent Evaluation Metrics Engine  v2 — Multi-Agent Ready
=========================================================
Fully supports 2..N agents per match.

Key changes from v1:
  - Elo replaced with multi-player Elo (virtual pairwise decomposition)
  - Cooperative metrics computed against ALL opponents, not just opponents[0]
  - Nash gap generalised: per-agent deviation gain, works for any N
  - AgentRegistry stores full N-player joint payoff vectors
  - α-Rank uses polymatrix marginalisation for N>2
  - Blotto fronts-won uses plurality (most resources wins each front)
  - New: coalition detection helpers for N-player games
"""

from __future__ import annotations
import math
import numpy as np
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any


# ---------------------------------------------------------------------------
# Data Contracts
# ---------------------------------------------------------------------------

@dataclass
class Move:
    """A single decision submitted by one agent in one round."""
    agent_id: str
    round_number: int
    action: Any           # list[int] for Blotto, int for binary games, etc.
    payoff: float
    metadata: dict = field(default_factory=dict)


@dataclass
class Match:
    """One completed match between 2..N agents."""
    match_id: str
    game_type: str
    agent_ids: list[str]
    moves: list[Move]
    config: dict = field(default_factory=dict)

    def moves_by_agent(self, agent_id: str) -> list[Move]:
        return sorted(
            [m for m in self.moves if m.agent_id == agent_id],
            key=lambda m: m.round_number,
        )

    def moves_by_round(self, r: int) -> list[Move]:
        return [m for m in self.moves if m.round_number == r]

    def num_rounds(self) -> int:
        return max((m.round_number for m in self.moves), default=0) + 1

    def payoffs(self, agent_id: str) -> list[float]:
        return [m.payoff for m in self.moves_by_agent(agent_id)]

    def total_payoff(self, agent_id: str) -> float:
        return sum(self.payoffs(agent_id))

    def actions(self, agent_id: str) -> list[Any]:
        return [m.action for m in self.moves_by_agent(agent_id)]

    # joint payoff tuples: one per round, in agent_ids order
    def joint_payoffs(self) -> list[tuple[float, ...]]:
        result = []
        for r in range(self.num_rounds()):
            round_moves = {m.agent_id: m for m in self.moves_by_round(r)}
            if all(a in round_moves for a in self.agent_ids):
                result.append(tuple(round_moves[a].payoff for a in self.agent_ids))
        return result


# ---------------------------------------------------------------------------
# TIER 1 — Ranking
# ---------------------------------------------------------------------------

class RankingMetrics:
    """
    Multi-player Elo and α-Rank support.

    Multi-player Elo strategy: decompose an N-player match into C(N,2) virtual
    pairwise contests, each weighted by 1/(N-1). This is the standard approach
    used in multiplayer gaming and endorsed by Glicko authors.
    """

    @staticmethod
    def expected_score(rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

    @staticmethod
    def update_elo_multiplayer(
        ratings: dict[str, float],
        results: dict[str, float],   # agent_id → avg_payoff this match
        k: float = 32,
    ) -> dict[str, float]:
        """
        N-player Elo update via virtual pairwise decomposition.

        For each ordered pair (i, j):
          score_i = 1 if payoff_i > payoff_j, 0.5 if tied, 0 otherwise
          Weight each update by 1/(N-1) so total update magnitude is K.

        Returns updated ratings dict (does not mutate input).
        """
        new_ratings = dict(ratings)
        agents = list(results)
        n = len(agents)
        if n < 2:
            return new_ratings

        weight = 1.0 / (n - 1)

        for a, b in combinations(agents, 2):
            pa, pb = results[a], results[b]
            score_a = 1.0 if pa > pb else (0.5 if pa == pb else 0.0)
            score_b = 1.0 - score_a

            ea = RankingMetrics.expected_score(new_ratings.get(a, 1200.0), new_ratings.get(b, 1200.0))
            eb = 1.0 - ea

            new_ratings[a] = new_ratings.get(a, 1200.0) + k * weight * (score_a - ea)
            new_ratings[b] = new_ratings.get(b, 1200.0) + k * weight * (score_b - eb)

        return new_ratings

    @staticmethod
    def alpha_rank_fixation_probability(
        payoff_a_vs_b: float,
        payoff_b_vs_a: float,
        alpha: float = 50.0,
        population_size: int = 100,
    ) -> float:
        """Fermi fixation probability of A invading B's population."""
        delta = payoff_a_vs_b - payoff_b_vs_a
        if abs(delta) < 1e-10:
            return 1.0 / population_size

        exp_num = -alpha * delta
        exp_den = -alpha * population_size * delta

        num_val = 0.0 if exp_num < -700 else (float("inf") if exp_num > 700 else math.exp(exp_num))
        den_val = 0.0 if exp_den < -700 else (float("inf") if exp_den > 700 else math.exp(exp_den))

        if math.isinf(num_val) or math.isinf(den_val):
            return 1.0 / population_size

        numerator   = 1.0 - num_val
        denominator = 1.0 - den_val
        if abs(denominator) < 1e-10:
            return 1.0 / population_size

        return numerator / denominator


# ---------------------------------------------------------------------------
# TIER 1 — Equilibrium
# ---------------------------------------------------------------------------

class EquilibriumMetrics:

    @staticmethod
    def nash_gap_nplayer(
        payoffs_per_agent: dict[str, list[float]],
        best_responses: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """
        Per-agent Nash deviation gain for N players.

        Nash Gap_i = max(0, BR_i - avg_payoff_i)

        If best_responses not supplied, uses observed maximum as a
        conservative proxy (always an overestimate — gap may be 0 in reality).

        Returns {agent_id: gap}.
        """
        gaps = {}
        for agent_id, payoffs in payoffs_per_agent.items():
            avg = float(np.mean(payoffs)) if payoffs else 0.0
            br  = (best_responses or {}).get(agent_id, max(payoffs) if payoffs else 0.0)
            gaps[agent_id] = max(0.0, br - avg)
        return gaps

    @staticmethod
    def total_nash_gap(gaps: dict[str, float]) -> float:
        """Sum of all per-agent gaps — single scalar for the whole match."""
        return sum(gaps.values())

    @staticmethod
    def pareto_efficiency(
        joint_payoffs: list[tuple[float, ...]],
        pareto_optimal_value: float | None = None,
    ) -> float:
        if not joint_payoffs:
            return 0.0
        joint_sums = [sum(p) for p in joint_payoffs]
        reference  = pareto_optimal_value or max(joint_sums)
        if reference == 0:
            return 0.0
        return float(np.mean(joint_sums) / reference)

    @staticmethod
    def social_welfare(payoffs_per_agent: dict[str, list[float]]) -> float:
        return sum(float(np.mean(v)) for v in payoffs_per_agent.values() if v)

    @staticmethod
    def social_efficiency_ratio(achieved: float, pareto_optimal: float) -> float:
        return 0.0 if pareto_optimal == 0 else min(1.0, achieved / pareto_optimal)


# ---------------------------------------------------------------------------
# TIER 2 — Cooperative Metrics  (N-player generalised)
# ---------------------------------------------------------------------------

class CooperativeMetrics:
    """
    All pairwise cooperation signals are now computed against EVERY opponent
    and returned as {opponent_id: value} dicts.

    A summary scalar (mean across opponents) is also provided for convenience.
    """

    # ── binary action helpers ────────────────────────────────────────────────

    @staticmethod
    def _to_binary(actions: list[Any]) -> list[int]:
        return [int(a) if isinstance(a, (int, float, bool)) else 0 for a in actions]

    # ── unconditional ────────────────────────────────────────────────────────

    @staticmethod
    def cooperation_rate(actions: list[int]) -> float:
        return float(np.mean(actions)) if actions else 0.0

    # ── pairwise signals (returned per-opponent) ─────────────────────────────

    @staticmethod
    def conditional_cooperation_rates(
        own_actions: list[int],
        opponents_actions: dict[str, list[int]],
    ) -> dict[str, dict[str, float]]:
        """
        Conditional cooperation rate against each opponent.
        Returns {opp_id: {"after_cooperate": float, "after_defect": float}}
        """
        results = {}
        for opp_id, opp_acts in opponents_actions.items():
            if len(own_actions) < 2 or len(opp_acts) < 2:
                results[opp_id] = {"after_cooperate": 0.0, "after_defect": 0.0}
                continue
            after_c = [own_actions[i] for i in range(1, len(own_actions)) if opp_acts[i-1] == 1]
            after_d = [own_actions[i] for i in range(1, len(own_actions)) if opp_acts[i-1] == 0]
            results[opp_id] = {
                "after_cooperate": float(np.mean(after_c)) if after_c else 0.0,
                "after_defect":    float(np.mean(after_d)) if after_d else 0.0,
            }
        return results

    @staticmethod
    def tit_for_tat_adherence(
        own_actions: list[int],
        opponents_actions: dict[str, list[int]],
    ) -> dict[str, float]:
        """
        TfT adherence vs. each opponent.
        In N-player games, TfT is defined against each opponent independently.
        Returns {opp_id: adherence_fraction}.
        """
        results = {}
        for opp_id, opp_acts in opponents_actions.items():
            if not own_actions:
                results[opp_id] = 0.0
                continue
            consistent = int(own_actions[0] == 1)  # TfT opens with cooperation
            for i in range(1, len(own_actions)):
                if i < len(opp_acts) and own_actions[i] == opp_acts[i-1]:
                    consistent += 1
            results[opp_id] = consistent / len(own_actions)
        return results

    @staticmethod
    def forgiveness_index(
        own_actions: list[int],
        opponents_actions: dict[str, list[int]],
    ) -> dict[str, float]:
        """Rounds until resuming cooperation after each opponent defection. Per-opponent."""
        results = {}
        for opp_id, opp_acts in opponents_actions.items():
            waits = []
            i = 1
            while i < len(own_actions):
                if i <= len(opp_acts) and opp_acts[i-1] == 0 and own_actions[i] == 0:
                    j = i + 1
                    while j < len(own_actions) and own_actions[j] == 0:
                        j += 1
                    if j < len(own_actions):
                        waits.append(j - i)
                    i = j
                else:
                    i += 1
            results[opp_id] = float(np.mean(waits)) if waits else 0.0
        return results

    # ── N-player specific ────────────────────────────────────────────────────

    @staticmethod
    def multilateral_cooperation_index(
        all_actions: dict[str, list[int]],
    ) -> list[float]:
        """
        Per-round fraction of agents that cooperated.
        Returns a time-series: [coop_fraction_round_0, coop_fraction_round_1, ...]
        Useful for tracking cooperation dynamics over time.
        """
        if not all_actions:
            return []
        num_rounds = max(len(v) for v in all_actions.values())
        index = []
        for r in range(num_rounds):
            acts = [v[r] for v in all_actions.values() if r < len(v)]
            index.append(float(np.mean(acts)) if acts else 0.0)
        return index

    @staticmethod
    def pairwise_reciprocity_matrix(
        all_actions: dict[str, list[int]],
        agent_ids: list[str],
    ) -> dict[tuple[str, str], float]:
        """
        Compute pairwise reciprocity scores for all (i,j) pairs.
        Reciprocity(i→j) = correlation between i's action at t and j's action at t-1.
        Returns {(agent_i, agent_j): reciprocity_score}
        """
        matrix = {}
        for i, j in combinations(agent_ids, 2):
            acts_i = all_actions.get(i, [])
            acts_j = all_actions.get(j, [])
            min_len = min(len(acts_i), len(acts_j))
            if min_len < 2:
                matrix[(i, j)] = 0.0
                matrix[(j, i)] = 0.0
                continue
            # i's response to j's previous action
            i_responds = acts_i[1:min_len]
            j_prev     = acts_j[:min_len-1]
            j_responds = acts_j[1:min_len]
            i_prev     = acts_i[:min_len-1]
            if np.std(i_responds) > 1e-8 and np.std(j_prev) > 1e-8:
                matrix[(i, j)] = float(np.corrcoef(i_responds, j_prev)[0, 1])
            else:
                matrix[(i, j)] = 0.0
            if np.std(j_responds) > 1e-8 and np.std(i_prev) > 1e-8:
                matrix[(j, i)] = float(np.corrcoef(j_responds, i_prev)[0, 1])
            else:
                matrix[(j, i)] = 0.0
        return matrix

    # ── social metrics ───────────────────────────────────────────────────────

    @staticmethod
    def gini_coefficient(payoffs: list[float]) -> float:
        if not payoffs or sum(payoffs) == 0:
            return 0.0
        arr = sorted(payoffs)
        n   = len(arr)
        idx = np.arange(1, n + 1)
        return float((2 * np.dot(idx, arr) / (n * sum(arr))) - (n + 1) / n)

    @staticmethod
    def price_of_anarchy(pareto_welfare: float, worst_nash_welfare: float) -> float:
        return float("inf") if worst_nash_welfare == 0 else pareto_welfare / worst_nash_welfare

    # ── coalition helpers ────────────────────────────────────────────────────

    @staticmethod
    def coalition_payoff_improvement(
        solo_payoffs: dict[str, float],
        coalition_payoffs: dict[str, float],
    ) -> dict[str, float]:
        """
        How much each agent improved by being in a coalition vs. playing solo.
        Returns {agent_id: improvement_fraction}
        """
        result = {}
        for agent_id in coalition_payoffs:
            solo = solo_payoffs.get(agent_id, 0.0)
            coal = coalition_payoffs[agent_id]
            result[agent_id] = (coal - solo) / abs(solo) if solo != 0 else float("inf")
        return result

    @staticmethod
    def shapley_value_deviation(
        actual_payoffs: dict[str, float],
        shapley_values: dict[str, float],
    ) -> dict[str, float]:
        """
        Deviation of actual payoff from Shapley fair-share value.
        Shapley values must be computed externally (game-specific).
        Returns {agent_id: deviation}
        """
        return {
            a: actual_payoffs.get(a, 0.0) - shapley_values.get(a, 0.0)
            for a in set(actual_payoffs) | set(shapley_values)
        }


# ---------------------------------------------------------------------------
# TIER 2 — Behavioral
# ---------------------------------------------------------------------------

class BehavioralMetrics:

    @staticmethod
    def strategy_entropy(actions: list[Any]) -> float:
        if not actions:
            return 0.0
        counts: dict = defaultdict(int)
        for a in actions:
            counts[tuple(a) if isinstance(a, list) else a] += 1
        n     = len(actions)
        probs = [c / n for c in counts.values()]
        return float(-sum(p * math.log2(p) for p in probs if p > 0))

    @staticmethod
    def behavioral_consistency(actions: list[Any]) -> float:
        unique = len({tuple(a) if isinstance(a, list) else a for a in actions})
        if unique <= 1:
            return 1.0
        max_e = math.log2(unique)
        return 0.0 if max_e == 0 else 1.0 - (BehavioralMetrics.strategy_entropy(actions) / max_e)

    @staticmethod
    def regret(realized_payoffs: list[float], best_fixed_payoff: float) -> float:
        return max(0.0, best_fixed_payoff * len(realized_payoffs) - sum(realized_payoffs))

    @staticmethod
    def adaptive_regret(realized_payoffs: list[float], window: int = 10) -> list[float]:
        regrets = []
        for i in range(0, len(realized_payoffs), window):
            w = realized_payoffs[i:i+window]
            if w:
                regrets.append(max(w) * len(w) - sum(w))
        return regrets

    @staticmethod
    def opponent_prediction_accuracy(
        predicted: list[Any],
        actual: list[Any],
    ) -> float:
        if not predicted or len(predicted) != len(actual):
            return 0.0
        def norm(x):
            return tuple(x) if isinstance(x, list) else x
        return sum(1 for p, a in zip(predicted, actual) if norm(p) == norm(a)) / len(predicted)

    @staticmethod
    def per_opponent_prediction_accuracy(
        predicted_per_opp: dict[str, list[Any]],
        actual_per_opp: dict[str, list[Any]],
    ) -> dict[str, float]:
        """Theory-of-Mind score against each opponent."""
        return {
            opp: BehavioralMetrics.opponent_prediction_accuracy(
                predicted_per_opp.get(opp, []),
                actual_per_opp.get(opp, []),
            )
            for opp in actual_per_opp
        }


# ---------------------------------------------------------------------------
# TIER 3 — Colonel Blotto  (N-player)
# ---------------------------------------------------------------------------

class BlottoMetrics:
    """
    N-player Blotto: each agent submits an allocation list[int].
    Win condition per battlefield: PLURALITY (most resources wins).
    Ties on a front are split or treated as no-win depending on config.
    """

    @staticmethod
    def fronts_won_nplayer(
        allocations: dict[str, list[int]],
        tie_policy: str = "split",   # "split" | "no_win"
    ) -> dict[str, float]:
        """
        Compute fronts won for each agent given all allocations.

        tie_policy:
          "split"  — tied agents each get 0.5 / num_tied (fractional wins)
          "no_win" — ties award no one

        Returns {agent_id: fronts_won (possibly fractional)}
        """
        agents = list(allocations)
        if not agents:
            return {}

        num_fronts = len(next(iter(allocations.values())))
        wins: dict[str, float] = {a: 0.0 for a in agents}

        for f in range(num_fronts):
            front_allocs = {a: allocations[a][f] for a in agents}
            max_val = max(front_allocs.values())
            winners = [a for a, v in front_allocs.items() if v == max_val]

            if len(winners) == 1:
                wins[winners[0]] += 1.0
            elif tie_policy == "split":
                share = 1.0 / len(winners)
                for w in winners:
                    wins[w] += share
            # "no_win": no one gets credit

        return wins

    @staticmethod
    def herfindahl_hirschman_index(allocation: list[int]) -> float:
        total = sum(allocation)
        if total == 0:
            return 0.0
        return float(sum((x / total) ** 2 for x in allocation))

    @staticmethod
    def strategy_diversity_over_match(allocations: list[list[int]]) -> float:
        return BehavioralMetrics.strategy_entropy(allocations)

    @staticmethod
    def mixed_ne_distance(
        observed_allocations: list[list[int]],
        ne_distribution: dict[tuple, float],
    ) -> float:
        if not observed_allocations or not ne_distribution:
            return float("inf")
        counts: dict = defaultdict(int)
        for a in observed_allocations:
            counts[tuple(a)] += 1
        n    = len(observed_allocations)
        obs  = {k: v / n for k, v in counts.items()}
        eps  = 1e-10
        keys = set(ne_distribution) | set(obs)
        return max(0.0, sum(
            obs.get(k, eps) * math.log(obs.get(k, eps) / ne_distribution.get(k, eps))
            for k in keys
        ))

    @staticmethod
    def pattern_exploitability_score(allocations: list[list[int]]) -> float:
        if len(allocations) < 3:
            return 0.0
        arr = np.array(allocations, dtype=float)
        acs = []
        for bf in range(arr.shape[1]):
            s = arr[:, bf]
            if np.std(s) < 1e-8:
                acs.append(1.0)
                continue
            n = (s - np.mean(s)) / np.std(s)
            acs.append(abs(np.corrcoef(n[:-1], n[1:])[0, 1]))
        return float(np.mean(acs))

    @staticmethod
    def underdog_performance(
        agent_resources: int,
        total_resources: int,
        fronts_won_fraction: float,
    ) -> float:
        """
        Generalised underdog metric: performance relative to resource share.
        > 1.0 means agent outperforms their resource proportion.
        """
        share = agent_resources / total_resources if total_resources > 0 else 0.0
        return fronts_won_fraction / share if share > 0 else 0.0

    @staticmethod
    def resource_targeting_overlap(
        allocations: dict[str, list[int]],
    ) -> dict[tuple[str, str], float]:
        """
        Cosine similarity of allocation vectors between each pair of agents.
        High overlap = agents are contesting the same fronts (head-to-head).
        Low overlap = agents are spreading differently (complementary, or avoiding).
        Useful in 3+ player games to detect implicit coordination or avoidance.
        """
        agents = list(allocations)
        overlaps = {}
        for a, b in combinations(agents, 2):
            va = np.array(allocations[a], dtype=float)
            vb = np.array(allocations[b], dtype=float)
            na, nb = np.linalg.norm(va), np.linalg.norm(vb)
            if na == 0 or nb == 0:
                overlaps[(a, b)] = 0.0
            else:
                overlaps[(a, b)] = float(np.dot(va, vb) / (na * nb))
        return overlaps


# ---------------------------------------------------------------------------
# Registry — N-player aware
# ---------------------------------------------------------------------------

class AgentRegistry:
    """
    Stateful store accumulating payoff data across matches for α-Rank and Elo.

    N-player α-Rank uses polymatrix marginalisation:
      For each ordered pair (i, j), the marginal payoff of i vs. j is the
      average of i's payoff in all matches where both i and j participated,
      treating all other agents as background (averaged out).
    This is the standard tractable extension of α-Rank to N>2.
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
        avg_payoffs: {agent_id: average_payoff_this_match}
        Records marginal pairwise entries for every pair in the match.
        """
        self.match_history.append(match.match_id)
        agents = match.agent_ids

        # Record marginal pairwise payoffs for α-Rank
        for a, b in combinations(agents, 2):
            pa, pb = avg_payoffs.get(a, 0.0), avg_payoffs.get(b, 0.0)
            self.marginal_payoffs[a][b].append((pa, pb))
            self.marginal_payoffs[b][a].append((pb, pa))

        # Multi-player Elo update
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
        Uses polymatrix marginalisation for N>2.
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
        Higher mass = more evolutionarily dominant.
        """
        n = len(agent_ids)
        if n < 2:
            return {agent_ids[0]: 1.0} if agent_ids else {}

        graph = self.build_response_graph(agent_ids)
        idx   = {a: i for i, a in enumerate(agent_ids)}

        T = np.zeros((n, n))
        for (a, b), fp in graph.items():
            i, j = idx[a], idx[b]
            T[i][j] += fp / (n - 1)

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
        scores = self.compute_alpha_rank_scores(agent_ids)
        total  = sum(scores.values())
        if total == 0:
            return 0.0
        probs = [v / total for v in scores.values()]
        return float(-sum(p * math.log2(p) for p in probs if p > 0))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class MatchEvaluator:
    """
    Main entry point. Supports 2..N agents per match.
    Call evaluate() after every match; population_report() after a batch.
    """

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def evaluate(self, match: Match, game_config: dict | None = None) -> dict:
        config  = game_config or match.config
        agents  = match.agent_ids
        n       = len(agents)
        payoffs_per_agent = {a: match.payoffs(a) for a in agents}

        report: dict = {
            "match_id":  match.match_id,
            "game_type": match.game_type,
            "num_agents": n,
            "agents": {},
            "joint":  {},
            "pairwise": {},   # NEW: pairwise signals for every (i,j) pair
        }

        # ── Joint metrics ────────────────────────────────────────────────────
        joint_payoffs = match.joint_payoffs()
        pareto_opt    = config.get("pareto_optimal_welfare")
        sw            = EquilibriumMetrics.social_welfare(payoffs_per_agent)

        report["joint"] = {
            "social_welfare":        sw,
            "pareto_efficiency":     EquilibriumMetrics.pareto_efficiency(joint_payoffs, pareto_opt),
            "social_efficiency_ratio": EquilibriumMetrics.social_efficiency_ratio(sw, pareto_opt or sw),
            "gini_coefficient":      CooperativeMetrics.gini_coefficient(
                                         [float(np.mean(v)) for v in payoffs_per_agent.values() if v]
                                     ),
        }

        # Nash gap — now per-agent, works for any N
        best_responses = config.get("best_responses")  # optional {agent_id: float}
        nash_gaps = EquilibriumMetrics.nash_gap_nplayer(payoffs_per_agent, best_responses)
        report["joint"]["nash_gap_per_agent"] = nash_gaps
        report["joint"]["total_nash_gap"]     = EquilibriumMetrics.total_nash_gap(nash_gaps)

        # N-player Blotto: fronts won across ALL opponents simultaneously
        if match.game_type == "colonel_blotto":
            all_allocs_by_round: list[dict[str, list[int]]] = []
            for r in range(match.num_rounds()):
                round_moves = {m.agent_id: m.action for m in match.moves_by_round(r)
                               if isinstance(m.action, list)}
                if len(round_moves) == n:
                    all_allocs_by_round.append(round_moves)

            if all_allocs_by_round:
                total_fronts_won: dict[str, float] = defaultdict(float)
                for allocs in all_allocs_by_round:
                    for agent_id, fw in BlottoMetrics.fronts_won_nplayer(
                        allocs, config.get("tie_policy", "split")
                    ).items():
                        total_fronts_won[agent_id] += fw

                total_possible = len(all_allocs_by_round) * len(
                    next(iter(all_allocs_by_round[0].values()))
                )
                report["joint"]["blotto_fronts_won"] = {
                    a: total_fronts_won[a] / total_possible
                    for a in agents
                }

                # Resource targeting overlap (cosine similarity per pair per round, averaged)
                all_overlaps: dict[tuple, list[float]] = defaultdict(list)
                for allocs in all_allocs_by_round:
                    for pair, overlap in BlottoMetrics.resource_targeting_overlap(allocs).items():
                        all_overlaps[pair].append(overlap)
                report["joint"]["blotto_targeting_overlap"] = {
                    f"{a}_{b}": float(np.mean(v))
                    for (a, b), v in all_overlaps.items()
                }

        # Multilateral cooperation index (time-series)
        cooperative_game_types = ("prisoners_dilemma", "stag_hunt", "public_goods", "blotto_coalition")
        if match.game_type in cooperative_game_types:
            all_binary = {
                a: CooperativeMetrics._to_binary(match.actions(a))
                for a in agents
            }
            report["joint"]["multilateral_cooperation_index"] = \
                CooperativeMetrics.multilateral_cooperation_index(all_binary)

            # Pairwise reciprocity matrix
            report["pairwise"]["reciprocity_matrix"] = {
                f"{a}_{b}": v
                for (a, b), v in CooperativeMetrics.pairwise_reciprocity_matrix(
                    all_binary, agents
                ).items()
            }

        # ── Per-agent metrics ─────────────────────────────────────────────────
        for agent_id in agents:
            actions   = match.actions(agent_id)
            payoffs   = match.payoffs(agent_id)
            opponents = [a for a in agents if a != agent_id]

            ar: dict = {
                "total_payoff":            match.total_payoff(agent_id),
                "avg_payoff":              float(np.mean(payoffs)) if payoffs else 0.0,
                "strategy_entropy":        BehavioralMetrics.strategy_entropy(actions),
                "behavioral_consistency":  BehavioralMetrics.behavioral_consistency(actions),
                "cumulative_regret":       BehavioralMetrics.regret(
                                               payoffs,
                                               config.get("best_response_payoff",
                                                          max(payoffs) if payoffs else 0.0)
                                           ),
                "adaptive_regret_series":  BehavioralMetrics.adaptive_regret(payoffs),
                "nash_gap":                nash_gaps.get(agent_id, 0.0),
            }

            # Cooperative signals — vs. EVERY opponent
            if match.game_type in cooperative_game_types:
                bin_acts = CooperativeMetrics._to_binary(actions)
                ar["cooperation_rate"] = CooperativeMetrics.cooperation_rate(bin_acts)

                opp_bin_actions = {
                    opp: CooperativeMetrics._to_binary(match.actions(opp))
                    for opp in opponents
                }

                ar["conditional_cooperation"] = \
                    CooperativeMetrics.conditional_cooperation_rates(bin_acts, opp_bin_actions)
                ar["tit_for_tat_adherence"]    = \
                    CooperativeMetrics.tit_for_tat_adherence(bin_acts, opp_bin_actions)
                ar["forgiveness_index"]         = \
                    CooperativeMetrics.forgiveness_index(bin_acts, opp_bin_actions)

                # Mean across opponents for quick comparison
                ar["mean_tft_adherence"] = float(np.mean(list(ar["tit_for_tat_adherence"].values()))) \
                                           if ar["tit_for_tat_adherence"] else 0.0
                ar["mean_forgiveness"]   = float(np.mean(list(ar["forgiveness_index"].values()))) \
                                           if ar["forgiveness_index"] else 0.0

            # Blotto per-agent signals
            if match.game_type == "colonel_blotto" and actions and isinstance(actions[0], list):
                allocs = [a for a in actions if isinstance(a, list)]
                total_res = config.get("resources", sum(allocs[0]) if allocs else 1)
                total_res_all = config.get("total_resources_all_agents",
                                           total_res * n)
                fronts_won_frac = report["joint"].get("blotto_fronts_won", {}).get(agent_id, 0.0)

                ar["blotto"] = {
                    "avg_hhi":               float(np.mean(
                                                 [BlottoMetrics.herfindahl_hirschman_index(a) for a in allocs]
                                             )),
                    "strategy_diversity":    BlottoMetrics.strategy_diversity_over_match(allocs),
                    "pattern_exploitability": BlottoMetrics.pattern_exploitability_score(allocs),
                    "underdog_performance":  BlottoMetrics.underdog_performance(
                                                 total_res, total_res_all, fronts_won_frac
                                             ),
                }

            report["agents"][agent_id] = ar

        # ── Registry update ───────────────────────────────────────────────────
        avg_results = {a: float(np.mean(v)) for a, v in payoffs_per_agent.items() if v}
        self.registry.record_match(match, avg_results)

        return report

    def population_report(self, agent_ids: list[str]) -> dict:
        alpha_scores = self.registry.compute_alpha_rank_scores(agent_ids)
        return {
            "elo_ratings":         {a: self.registry.elo_ratings[a] for a in agent_ids},
            "alpha_rank_scores":   alpha_scores,
            "alpha_rank_ranking":  sorted(alpha_scores, key=alpha_scores.get, reverse=True),
            "population_diversity": self.registry.population_diversity(agent_ids),
            "matches_played":      len(self.registry.match_history),
        }