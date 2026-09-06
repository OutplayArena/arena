from __future__ import annotations

import random
from abc import abstractmethod

from arena.game_components.game_agent import GameAgent


class ChickenGameAgent(GameAgent):
    @abstractmethod
    def act(self, history: list[dict]) -> str: ...


class AlwaysSwerve(ChickenGameAgent):
    def act(self, history: list[dict]) -> str:
        return "swerve"


class AlwaysDare(ChickenGameAgent):
    """Plays the maximally aggressive strategy — never yields."""

    def act(self, history: list[dict]) -> str:
        return "dare"


class TitForTat(ChickenGameAgent):
    """Starts with swerve; mirrors opponent's last move thereafter."""

    def __init__(self, player: str = "A"):
        self._opponent = "B" if player == "A" else "A"

    def act(self, history: list[dict]) -> str:
        if not history:
            return "swerve"
        last = history[-1].get("actions", {}).get(self._opponent, "swerve")
        return last


class GrimTrigger(ChickenGameAgent):
    """Swerves until the opponent dares once, then always dares (mutual crash risk)."""

    def __init__(self, player: str = "A"):
        self._opponent = "B" if player == "A" else "A"
        self._triggered = False

    def act(self, history: list[dict]) -> str:
        if self._triggered:
            return "dare"
        for entry in history:
            if entry.get("actions", {}).get(self._opponent) == "dare":
                self._triggered = True
                return "dare"
        return "swerve"


class AlternatingAgent(ChickenGameAgent):
    """Alternates between dare and swerve, starting with dare."""

    def act(self, history: list[dict]) -> str:
        return "dare" if len(history) % 2 == 0 else "swerve"


class RandomAgent(ChickenGameAgent):
    def act(self, history: list[dict]) -> str:
        return random.choice(["swerve", "dare"])
