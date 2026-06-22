from __future__ import annotations

import random

from abc import abstractmethod
from arena.game_components.game_agent import GameAgent

MOVES = ("rock", "paper", "scissors")
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
BEATEN_BY = {v: k for k, v in BEATS.items()}


class RPSAgent(GameAgent):
    @abstractmethod
    def act(self, history: list[dict]) -> str:
        ...


class RandomAgent(RPSAgent):
    """Uniform random — the Nash equilibrium strategy."""

    def act(self, history: list[dict]) -> str:
        return random.choice(MOVES)


class BiasedAgent(RPSAgent):
    """Plays rock with higher probability; paper and scissors share the remainder."""

    def __init__(self, rock_weight: float = 0.5):
        self._weights = [rock_weight, (1 - rock_weight) / 2, (1 - rock_weight) / 2]

    def act(self, history: list[dict]) -> str:
        return random.choices(MOVES, weights=self._weights)[0]


class CopycatAgent(RPSAgent):
    """Copies the opponent's last move; plays randomly on round 1."""

    def __init__(self, player: str = "A"):
        self._player = player
        self._opponent = "B" if player == "A" else "A"

    def act(self, history: list[dict]) -> str:
        if not history:
            return random.choice(MOVES)
        return history[-1].get("actions", {}).get(self._opponent, random.choice(MOVES))


class CounterAgent(RPSAgent):
    """Plays the move that beats the opponent's last move; random on round 1."""

    def __init__(self, player: str = "A"):
        self._player = player
        self._opponent = "B" if player == "A" else "A"

    def act(self, history: list[dict]) -> str:
        if not history:
            return random.choice(MOVES)
        last = history[-1].get("actions", {}).get(self._opponent)
        if last is None or last not in BEATS:
            return random.choice(MOVES)
        return BEATEN_BY[last]
