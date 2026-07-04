from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

import numpy as np

from arena.game_components.game_metrics import GameMetrics
from arena.metrics.behavioral import BehavioralMetrics
from arena.metrics.extension import GameMetricsExtension
from arena.metrics.risk import hhi as _herfindahl_hirschman_index


# ---------------------------------------------------------------------------
# Low-level helpers (private to this module)
# ---------------------------------------------------------------------------

def _fronts_won_nplayer(
    allocations: dict[str, list[int]],
    tie_policy: str = "split",
) -> dict[str, float]:
    """
    Plurality wins per battlefield across N agents.

    tie_policy:
      "split"  — tied agents split the front equally
      "no_win" — ties award no one
    """
    agents = list(allocations)
    if not agents:
        return {}
    num_fronts = len(next(iter(allocations.values())))
    wins: dict[str, float] = {a: 0.0 for a in agents}
    for f in range(num_fronts):
        front = {a: allocations[a][f] for a in agents}
        max_val = max(front.values())
        winners = [a for a, v in front.items() if v == max_val]
        if len(winners) == 1:
            wins[winners[0]] += 1.0
        elif tie_policy == "split":
            share = 1.0 / len(winners)
            for w in winners:
                wins[w] += share
    return wins


def _pattern_exploitability(allocations: list[list[int]]) -> float:
    """Mean lag-1 autocorrelation across battlefields. 0 = random, 1 = predictable."""
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
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = abs(np.corrcoef(n[:-1], n[1:])[0, 1])
        acs.append(0.0 if np.isnan(corr) else corr)
    return float(np.mean(acs))


def _resource_targeting_overlap(
    allocations: dict[str, list[int]],
) -> dict[tuple[str, str], float]:
    """
    Cosine similarity of allocation vectors for each agent pair.
    High = agents contest the same fronts; low = complementary or avoidant.
    """
    agents = list(allocations)
    overlaps = {}
    for a, b in combinations(agents, 2):
        va = np.array(allocations[a], dtype=float)
        vb = np.array(allocations[b], dtype=float)
        na, nb = np.linalg.norm(va), np.linalg.norm(vb)
        overlaps[(a, b)] = float(np.dot(va, vb) / (na * nb)) if na > 0 and nb > 0 else 0.0
    return overlaps


def _underdog_performance(
    agent_resources: int,
    total_resources: int,
    fronts_won_fraction: float,
) -> float:
    """Fronts won relative to resource share. > 1.0 = outperforms resource proportion."""
    share = agent_resources / total_resources if total_resources > 0 else 0.0
    return fronts_won_fraction / share if share > 0 else 0.0


def _mixed_ne_distance(
    observed_allocations: list[list[int]],
    ne_distribution: dict[tuple, float],
) -> float:
    """KL divergence between observed mixed strategy and a Nash equilibrium distribution."""
    if not observed_allocations or not ne_distribution:
        return float("inf")
    counts: dict = defaultdict(int)
    for a in observed_allocations:
        counts[tuple(a)] += 1
    n   = len(observed_allocations)
    obs = {k: v / n for k, v in counts.items()}
    eps = 1e-10
    keys = set(ne_distribution) | set(obs)
    return max(0.0, sum(
        obs.get(k, eps) * math.log(obs.get(k, eps) / ne_distribution.get(k, eps))
        for k in keys
    ))


# ---------------------------------------------------------------------------
# Main metrics class — implements both legacy GameMetrics and new extension
# ---------------------------------------------------------------------------

class ColonelBlottoMetrics(GameMetrics, GameMetricsExtension):
    """
    All metrics for Colonel Blotto.

    Implements GameMetrics.compute() for backward-compatible use inside
    compute_results(), and GameMetricsExtension for rich per-match reports
    via MatchEvaluator.
    """

    # ── GameMetrics (legacy, used by compute_results) ────────────────────────

    def compute(self, history: list[dict], total_scores: dict) -> dict:
        payoff_average = self._average_payoff(history, total_scores)
        win_counts = self._round_win_counts(history)
        win_rate = self._round_win_rate(history, win_counts)
        concentration = self._allocation_concentration(history, total_scores)
        return {
            "total_payoff":          dict(total_scores),
            "average_payoff":        payoff_average,
            "round_win_counts":      win_counts,
            "round_win_rate":        win_rate,
            "allocation_concentration": concentration,
        }

    def _average_payoff(self, history, total_scores):
        n = len(history)
        if n == 0:
            return {player: 0 for player in total_scores}
        return {player: score / n for player, score in total_scores.items()}

    def _round_win_counts(self, history):
        counts = {"A": 0, "B": 0, "Tie": 0}
        for entry in history:
            winner = entry.get("winner")
            if winner not in counts:
                raise ValueError(f"unknown round winner: {winner}")
            counts[winner] += 1
        return counts

    def _round_win_rate(self, history, win_counts):
        n = len(history)
        if n == 0:
            return {player: 0 for player in win_counts}
        return {player: count / n for player, count in win_counts.items()}

    def _allocation_concentration(self, history, total_scores=None):
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for entry in history:
            for player, allocation in entry.get("allocations", {}).items():
                total = sum(allocation)
                c = 0.0 if total == 0 else max(allocation) / total
                totals[player] = totals.get(player, 0.0) + c
                counts[player] = counts.get(player, 0) + 1
        if not totals and total_scores:
            return {player: 0 for player in total_scores}
        return {
            player: (totals[player] / counts[player] if counts.get(player) else 0)
            for player in totals
        }

    # ── GameMetricsExtension (rich, used by MatchEvaluator) ─────────────────

    def compute_joint(self, match, config: dict) -> dict:
        agents = match.agent_ids
        n = len(agents)
        tie_policy = config.get("tie_policy", "split")

        all_allocs_by_round: list[dict[str, list[int]]] = []
        for r in range(match.num_rounds()):
            round_moves = {
                m.agent_id: m.action
                for m in match.moves_by_round(r)
                if isinstance(m.action, list)
            }
            if len(round_moves) == n:
                all_allocs_by_round.append(round_moves)

        if not all_allocs_by_round:
            return {}

        # Fronts won across all rounds
        total_fronts_won: dict[str, float] = defaultdict(float)
        for allocs in all_allocs_by_round:
            for agent_id, fw in _fronts_won_nplayer(allocs, tie_policy).items():
                total_fronts_won[agent_id] += fw

        num_fronts = len(next(iter(all_allocs_by_round[0].values())))
        total_possible = len(all_allocs_by_round) * num_fronts

        # Targeting overlap — averaged across rounds
        all_overlaps: dict[tuple, list[float]] = defaultdict(list)
        for allocs in all_allocs_by_round:
            for pair, overlap in _resource_targeting_overlap(allocs).items():
                all_overlaps[pair].append(overlap)

        return {
            "blotto_fronts_won": {
                a: total_fronts_won[a] / total_possible for a in agents
            },
            "blotto_targeting_overlap": {
                f"{a}_{b}": float(np.mean(v))
                for (a, b), v in all_overlaps.items()
            },
        }

    def compute_agent(self, match, agent_id: str, config: dict, joint: dict) -> dict:
        actions = match.actions(agent_id)
        allocs  = [a for a in actions if isinstance(a, list)]
        if not allocs:
            return {}

        n             = len(match.agent_ids)
        total_res     = config.get("resources", sum(allocs[0]) if allocs else 1)
        total_res_all = config.get("total_resources_all_agents", total_res * n)
        fronts_won_frac = joint.get("blotto_fronts_won", {}).get(agent_id, 0.0)

        return {
            "blotto": {
                "avg_hhi": float(np.mean(
                    [_herfindahl_hirschman_index(a) for a in allocs]
                )),
                "strategy_diversity":     BehavioralMetrics.strategy_entropy(allocs),
                "pattern_exploitability": _pattern_exploitability(allocs),
                "underdog_performance":   _underdog_performance(
                                              total_res, total_res_all, fronts_won_frac
                                          ),
            }
        }

    # ── Public helpers (optional standalone use) ─────────────────────────────

    @staticmethod
    def mixed_ne_distance(
        observed_allocations: list[list[int]],
        ne_distribution: dict[tuple, float],
    ) -> float:
        """KL divergence from a known Nash equilibrium distribution."""
        return _mixed_ne_distance(observed_allocations, ne_distribution)


def compute_colonel_blotto_metrics(history, total_scores):
    return ColonelBlottoMetrics().compute(history, total_scores)


# Module-level wrappers kept for backward compatibility with existing tests and callers
def average_payoff(history, total_scores):
    return ColonelBlottoMetrics()._average_payoff(history, total_scores)


def round_win_counts(history):
    return ColonelBlottoMetrics()._round_win_counts(history)


def round_win_rate(history, win_counts):
    return ColonelBlottoMetrics()._round_win_rate(history, win_counts)


def allocation_concentration(history, total_scores=None):
    return ColonelBlottoMetrics()._allocation_concentration(history, total_scores)
