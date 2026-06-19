from __future__ import annotations

import random

from outplaylabs_arena.game_components.game_agent import GameAgent

MOVES = ("fold", "check", "call", "raise")


class TexasHoldEmAgent(GameAgent):
    def act(self, history: list[dict]) -> str:
        raise NotImplementedError


class RandomAgent(TexasHoldEmAgent):
    def act(self, history: list[dict]) -> str:
        return random.choice(list(MOVES))


class ConservativeAgent(TexasHoldEmAgent):
    def act(self, history: list[dict]) -> str:
        return random.choices(MOVES, weights=[0.4, 0.3, 0.2, 0.1])[0]


class AggressiveAgent(TexasHoldEmAgent):
    def act(self, history: list[dict]) -> str:
        return random.choices(MOVES, weights=[0.05, 0.15, 0.3, 0.5])[0]


class CallStationAgent(TexasHoldEmAgent):
    def act(self, history: list[dict]) -> str:
        return random.choices(MOVES, weights=[0.0, 0.2, 0.6, 0.2])[0]
