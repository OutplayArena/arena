from __future__ import annotations

import random
from abc import abstractmethod

from outplaylabs_arena.game_components.game_agent import GameAgent


class StagHuntAgent(GameAgent):
    @abstractmethod
    def act(self, history: list[dict]) -> str: ...


class AlwaysStag(StagHuntAgent):
    def act(self, history: list[dict]) -> str:
        return "stag"


class AlwaysHare(StagHuntAgent):
    def act(self, history: list[dict]) -> str:
        return "hare"


class NashEquilibriumAgent(StagHuntAgent):
    """Plays the risk-dominant (Hare,Hare) Nash equilibrium."""

    def act(self, history: list[dict]) -> str:
        return "hare"


class ParetoOptimalAgent(StagHuntAgent):
    """Always attempts the Pareto-optimal (Stag,Stag) equilibrium."""

    def act(self, history: list[dict]) -> str:
        return "stag"


class TitForTat(StagHuntAgent):
    """Starts with stag; mirrors opponent's last move thereafter."""

    def __init__(self, player: str = "A"):
        self._opponent = "B" if player == "A" else "A"

    def act(self, history: list[dict]) -> str:
        if not history:
            return "stag"
        last = history[-1].get("actions", {}).get(self._opponent, "stag")
        return last


class OptimisticAgent(StagHuntAgent):
    """Hunts stag until betrayed once, then switches to hare forever."""

    def __init__(self, player: str = "A"):
        self._opponent = "B" if player == "A" else "A"
        self._betrayed = False

    def act(self, history: list[dict]) -> str:
        if self._betrayed:
            return "hare"
        for entry in history:
            if entry.get("actions", {}).get(self._opponent) == "hare":
                self._betrayed = True
                return "hare"
        return "stag"


class RandomAgent(StagHuntAgent):
    def act(self, history: list[dict]) -> str:
        return random.choice(["stag", "hare"])
