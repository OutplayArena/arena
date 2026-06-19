from __future__ import annotations

import random

from abc import abstractmethod
from outplaylabs_arena.game_components.game_agent import GameAgent


class PGGAgent(GameAgent):
    @abstractmethod
    def act(self, history: list[dict]) -> float | dict:
        ...


class AlwaysContributeMax(PGGAgent):
    """Contributes the full endowment every round."""

    def __init__(self, endowment: float = 10.0):
        self.endowment = endowment

    def act(self, history: list[dict]) -> float:
        return self.endowment


class AlwaysContributeZero(PGGAgent):
    """Free-rides; contributes nothing every round."""

    def act(self, history: list[dict]) -> float:
        return 0.0


class NashEquilibriumAgent(PGGAgent):
    """Plays Nash equilibrium: contribute zero (dominant strategy when r < n)."""

    def act(self, history: list[dict]) -> float:
        return 0.0


class LinearDecayAgent(PGGAgent):
    """Starts at full contribution and linearly decays to zero."""

    def __init__(self, endowment: float = 10.0, rounds: int = 10):
        self.endowment = endowment
        self.rounds = rounds

    def act(self, history: list[dict]) -> float:
        r = len(history) + 1
        return self.endowment * max(0.0, 1.0 - (r - 1) / max(1, self.rounds - 1))


class ConditionalCooperator(PGGAgent):
    """Matches the average contribution of others in the previous round."""

    def __init__(self, endowment: float = 10.0, player_id: str = "A"):
        self.endowment = endowment
        self.player_id = player_id

    def act(self, history: list[dict]) -> float:
        if not history:
            return self.endowment
        contrib_rounds = [e for e in history if e.get("phase") == "contribution"]
        if not contrib_rounds:
            return self.endowment
        last = contrib_rounds[-1]
        contribs = last.get("contributions", {})
        others = [v for k, v in contribs.items() if k != self.player_id]
        if not others:
            return self.endowment
        return min(self.endowment, max(0.0, sum(others) / len(others)))


class RandomAgent(PGGAgent):
    def __init__(self, endowment: float = 10.0):
        self.endowment = endowment

    def act(self, history: list[dict]) -> float:
        return random.uniform(0.0, self.endowment)


class PunishLowContributors(PGGAgent):
    """Contributes full endowment and punishes those below average (punishment variant)."""

    def __init__(self, endowment: float = 10.0, player_id: str = "A"):
        self.endowment = endowment
        self.player_id = player_id
        self._phase = "contribution"

    def act(self, history: list[dict]) -> float | dict:
        contrib_rounds = [e for e in history if e.get("phase") == "contribution"]
        if not contrib_rounds or "punishment_costs" not in contrib_rounds[-1]:
            # Contribution phase or pre-punishment
            return self.endowment
        # Punishment phase
        last = contrib_rounds[-1]
        contribs = last.get("contributions", {})
        others = {k: v for k, v in contribs.items() if k != self.player_id}
        if not others:
            return {}
        avg = sum(others.values()) / len(others)
        return {k: max(0.0, avg - v) for k, v in others.items()}
