from __future__ import annotations

import random

from abc import abstractmethod
from outplaylabs_arena.game_components.game_agent import GameAgent


class CentipedeAgent(GameAgent):
    @abstractmethod
    def act(self, history: list[dict]) -> str:
        ...


class TakeFirstAgent(CentipedeAgent):
    """Backward induction: always take immediately (SPE)."""

    def act(self, history: list[dict]) -> str:
        return "take"


class AlwaysPassAgent(CentipedeAgent):
    """Always passes (cooperative but non-equilibrium)."""

    def act(self, history: list[dict]) -> str:
        return "pass"


class LastStepTakeAgent(CentipedeAgent):
    """Passes until the last opportunity, then takes."""

    def __init__(self, max_steps: int = 6, player: str = "A"):
        self.max_steps = max_steps
        self.player = player

    def act(self, history: list[dict]) -> str:
        step = len(history) + 1
        if step >= self.max_steps:
            return "take"
        return "pass"


class TitForTatAgent(CentipedeAgent):
    """Passes if opponent passed last time, else takes."""

    def __init__(self, player: str = "A"):
        self.player = player
        self._opponent = "B" if player == "A" else "A"

    def act(self, history: list[dict]) -> str:
        opp_entries = [e for e in history if e.get("player") == self._opponent]
        if not opp_entries:
            return "pass"
        return "pass" if opp_entries[-1].get("action") == "pass" else "take"


class RandomAgent(CentipedeAgent):
    def act(self, history: list[dict]) -> str:
        return random.choice(["take", "pass"])
