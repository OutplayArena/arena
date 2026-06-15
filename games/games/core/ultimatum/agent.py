from __future__ import annotations

import random

from abc import abstractmethod
from nash_arena.game_components.game_agent import GameAgent


class UltimatumAgent(GameAgent):
    @abstractmethod
    def act(self, history: list[dict]) -> float | str:
        ...


class SPEAgent(UltimatumAgent):
    """Subgame-perfect equilibrium: proposes minimum offer; accepts any positive offer."""

    def __init__(self, player: str = "A", total: float = 100.0, min_offer: float = 1.0):
        self.player = player
        self.total = total
        self.min_offer = min_offer

    def act(self, history: list[dict]) -> float | str:
        # Determine if currently proposing or responding based on last history entry
        if not history:
            return self.min_offer  # propose minimum
        last = history[-1]
        if last.get("proposer") == self.player and last.get("response") is None:
            return self.min_offer
        if last.get("responder") == self.player:
            return "accept" if (last.get("offer", 0.0) or 0.0) >= self.min_offer else "reject"
        return self.min_offer


class FairAgent(UltimatumAgent):
    """Proposes equal split; accepts any offer >= 40% of total."""

    def __init__(self, player: str = "A", total: float = 100.0):
        self.player = player
        self.total = total

    def act(self, history: list[dict]) -> float | str:
        if not history:
            return self.total / 2.0
        last = history[-1]
        if last.get("responder") == self.player:
            offer = last.get("offer", 0.0) or 0.0
            return "accept" if offer >= 0.4 * self.total else "reject"
        return self.total / 2.0


class GreedyProposer(UltimatumAgent):
    """Proposes minimum offer; accepts anything above 30%."""

    def __init__(self, player: str = "A", total: float = 100.0, min_offer: float = 1.0):
        self.player = player
        self.total = total
        self.min_offer = min_offer

    def act(self, history: list[dict]) -> float | str:
        if not history:
            return self.min_offer
        last = history[-1]
        if last.get("responder") == self.player:
            offer = last.get("offer", 0.0) or 0.0
            return "accept" if offer >= 0.3 * self.total else "reject"
        return self.min_offer


class RandomAgent(UltimatumAgent):
    def __init__(self, player: str = "A", total: float = 100.0):
        self.player = player
        self.total = total

    def act(self, history: list[dict]) -> float | str:
        if not history:
            return random.uniform(0.0, self.total)
        last = history[-1]
        # Check if we're the responder (offer pending)
        if last.get("responder") == self.player and last.get("response") is None:
            return random.choice(["accept", "reject"])
        # Otherwise we're proposing
        return random.uniform(0.0, self.total)
