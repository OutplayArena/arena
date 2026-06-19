from __future__ import annotations

import random

from abc import abstractmethod
from outplaylabs_arena.game_components.game_agent import GameAgent


class BoSAgent(GameAgent):
    @abstractmethod
    def act(self, history: list[dict]) -> str:
        ...


class AlwaysA(BoSAgent):
    def __init__(self, option_a: str = "opera"):
        self.option_a = option_a

    def act(self, history: list[dict]) -> str:
        return self.option_a


class AlwaysB(BoSAgent):
    def __init__(self, option_b: str = "football"):
        self.option_b = option_b

    def act(self, history: list[dict]) -> str:
        return self.option_b


class TitForTat(BoSAgent):
    """Mirrors opponent's last action; starts with own preferred option."""

    def __init__(self, player: str = "A", option_a: str = "opera", option_b: str = "football"):
        self.player = player
        self._opponent = "B" if player == "A" else "A"
        self._preferred = option_a if player == "A" else option_b

    def act(self, history: list[dict]) -> str:
        if not history:
            return self._preferred
        return history[-1].get("actions", {}).get(self._opponent, self._preferred)


class MixedNashAgent(BoSAgent):
    """
    Plays mixed-strategy Nash equilibrium.
    With symmetric payoffs (pref=3, nonpref=2, mismatch=0):
      A plays option_a with prob 3/(3+2)=0.6; B plays option_b with prob 0.6.
    """

    def __init__(
        self, player: str = "A",
        option_a: str = "opera", option_b: str = "football",
        prob_a: float = 0.6,
    ):
        self.player = player
        self.option_a = option_a
        self.option_b = option_b
        self.prob_a = prob_a if player == "A" else (1.0 - prob_a)

    def act(self, history: list[dict]) -> str:
        return self.option_a if random.random() < self.prob_a else self.option_b


class RandomAgent(BoSAgent):
    def __init__(self, option_a: str = "opera", option_b: str = "football"):
        self.option_a = option_a
        self.option_b = option_b

    def act(self, history: list[dict]) -> str:
        return random.choice([self.option_a, self.option_b])
