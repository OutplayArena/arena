from __future__ import annotations

import random

from nash_arena.game_components.game_agent import GameAgent


class PDAgent(GameAgent):
    def act(self, history: list[dict]) -> str:
        raise NotImplementedError


class AlwaysCooperate(PDAgent):
    def act(self, history: list[dict]) -> str:
        return "cooperate"


class AlwaysDefect(PDAgent):
    def act(self, history: list[dict]) -> str:
        return "defect"


class TitForTat(PDAgent):
    def __init__(self, player: str = "A"):
        self._opponent = "B" if player == "A" else "A"

    def act(self, history: list[dict]) -> str:
        if not history:
            return "cooperate"
        return history[-1].get("actions", {}).get(self._opponent, "cooperate")


class GrimTrigger(PDAgent):
    def __init__(self, player: str = "A"):
        self._opponent = "B" if player == "A" else "A"
        self._triggered = False

    def act(self, history: list[dict]) -> str:
        if self._triggered:
            return "defect"
        for entry in history:
            if entry.get("actions", {}).get(self._opponent) == "defect":
                self._triggered = True
                return "defect"
        return "cooperate"


class ForgivingTFT(PDAgent):
    def __init__(self, player: str = "A", forgiveness_prob: float = 0.1):
        self._opponent = "B" if player == "A" else "A"
        self._forgiveness_prob = forgiveness_prob

    def act(self, history: list[dict]) -> str:
        if not history:
            return "cooperate"
        last_opp = history[-1].get("actions", {}).get(self._opponent, "cooperate")
        if last_opp == "defect" and random.random() < self._forgiveness_prob:
            return "cooperate"
        return last_opp


class Pavlov(PDAgent):
    """Win-stay/lose-shift: cooperate if last outcome was CC or DC, defect otherwise."""

    def __init__(self, player: str = "A"):
        self._player = player

    def act(self, history: list[dict]) -> str:
        if not history:
            return "cooperate"
        outcome = history[-1].get("outcome", "")
        if self._player == "A":
            return "cooperate" if outcome in ("CC", "DC") else "defect"
        return "cooperate" if outcome in ("CC", "CD") else "defect"


class RandomAgent(PDAgent):
    def act(self, history: list[dict]) -> str:
        return random.choice(["cooperate", "defect"])
