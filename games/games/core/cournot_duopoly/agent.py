from __future__ import annotations

import random

from abc import abstractmethod
from outplaylabs_arena.game_components.game_agent import GameAgent


class CournotAgent(GameAgent):
    @abstractmethod
    def act(self, history: list[dict]) -> float:
        ...


class NashEquilibriumAgent(CournotAgent):
    """Plays the Cournot Nash equilibrium quantity: (a-c)/(3b)."""

    def __init__(self, nash_quantity: float = 40.0):
        self.nash_quantity = nash_quantity

    def act(self, history: list[dict]) -> float:
        return self.nash_quantity


class CollussiveAgent(CournotAgent):
    """Plays the joint-maximizing (collusive) quantity: (a-c)/(4b)."""

    def __init__(self, collusive_quantity: float = 30.0):
        self.collusive_quantity = collusive_quantity

    def act(self, history: list[dict]) -> float:
        return self.collusive_quantity


class GreedyAgent(CournotAgent):
    """Plays best-response to opponent's last quantity."""

    def __init__(self, demand_a: float = 120.0, demand_b: float = 1.0,
                 cost: float = 0.0, max_q: float = 120.0, nash_q: float = 40.0):
        self.demand_a = demand_a
        self.demand_b = demand_b
        self.cost = cost
        self.max_q = max_q
        self.nash_q = nash_q
        self._player = None

    def _best_response(self, q_other: float) -> float:
        br = (self.demand_a - self.cost - self.demand_b * q_other) / (2 * self.demand_b)
        return max(0.0, min(self.max_q, br))

    def act(self, history: list[dict]) -> float:
        if not history:
            return self.nash_q
        last = history[-1]
        quantities = last.get("quantities", {})
        opp_q = None
        for k, v in quantities.items():
            opp_q = v  # take any value; we don't know player assignment here
        if opp_q is None:
            return self.nash_q
        return self._best_response(opp_q)


class RandomAgent(CournotAgent):
    def __init__(self, max_quantity: float = 120.0):
        self.max_quantity = max_quantity

    def act(self, history: list[dict]) -> float:
        return random.uniform(0.0, self.max_quantity)
