from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass

from arena.interactive_game_engine import InteractiveGameEngine

from games.community.chicken_game.metrics import ChickenGameMetrics

VALID_ACTIONS = frozenset({"swerve", "dare"})

_OUTCOMES: dict[tuple[str, str], str] = {
    ("dare", "dare"): "DD",
    ("dare", "swerve"): "DS",
    ("swerve", "dare"): "SD",
    ("swerve", "swerve"): "SS",
}


@dataclass
class ChickenGameState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_actions: dict[str, str]
    history: list[dict]
    total_scores: dict[str, float]


class ChickenGameGame(InteractiveGameEngine):
    def __init__(
        self,
        num_rounds: int = 10,
        payoff_win: float = 1.0,
        payoff_tie: float = 0.0,
        payoff_lose: float = -1.0,
        payoff_crash: float = -10.0,
        noise: float = 0.0,
        seed: int | None = None,
        system_prompt: str = "",
    ):
        self.num_rounds = num_rounds
        self.payoff_win = payoff_win
        self.payoff_tie = payoff_tie
        self.payoff_lose = payoff_lose
        self.payoff_crash = payoff_crash
        self.noise = noise
        self._rng = random.Random(seed)
        self.metrics_engine = ChickenGameMetrics(
            payoff_win=payoff_win,
            payoff_tie=payoff_tie,
            payoff_lose=payoff_lose,
            payoff_crash=payoff_crash,
        )
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> ChickenGameGame:
        return cls(
            num_rounds=config.rounds,
            payoff_win=config.payoff_win,
            payoff_tie=config.payoff_tie,
            payoff_lose=config.payoff_lose,
            payoff_crash=config.payoff_crash,
            noise=config.noise,
            seed=config.seed,
            system_prompt=config.system_prompt,
        )

    def human_action_schema(self, config):
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["swerve", "dare"],
                    "description": "Swerve (yield) or Dare (commit and hold course)",
                }
            },
            "required": ["action"],
        }

    def format_human_action(self, raw_action, config):
        if isinstance(raw_action, str):
            return raw_action.lower()
        if isinstance(raw_action, dict):
            return raw_action.get("action", "").lower()
        return str(raw_action).lower()

    def ui_metadata(self, config):
        return {
            "input_type": "choice",
            "choices": ["swerve", "dare"],
            "layout": "chicken_game",
        }

    def get_available_agents(self, config):
        return [
            {"id": "always_swerve", "label": "Always Swerve", "description": "Always yields"},
            {"id": "always_dare", "label": "Always Dare", "description": "Always holds course"},
            {"id": "tit_for_tat", "label": "Tit for Tat", "description": "Copies opponent's last move"},
        ]

    def initial_state(self) -> ChickenGameState:
        return ChickenGameState(
            round_number=1,
            phase="awaiting_action",
            awaiting=["A", "B"],
            pending_actions={},
            history=[],
            total_scores={"A": 0.0, "B": 0.0},
        )

    def state_from_dict(self, d: dict) -> ChickenGameState:
        return ChickenGameState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, str) and action in VALID_ACTIONS

    def validate_player_action(self, state: ChickenGameState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} has already submitted this round")
        if not self.validate_action(action):
            raise ValueError(f"invalid action {action!r}; must be 'swerve' or 'dare'")
        return True

    def _maybe_flip(self, action: str) -> str:
        if self.noise > 0 and self._rng.random() < self.noise:
            return "dare" if action == "swerve" else "swerve"
        return action

    def apply_action(self, state: ChickenGameState, player: str, action: str) -> ChickenGameState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_actions[player] = action
        state.awaiting = [p for p in state.awaiting if p != player]
        if not state.awaiting:
            state = self._resolve_round(state)
        return state

    def _resolve_round(self, state: ChickenGameState) -> ChickenGameState:
        a_intended = state.pending_actions["A"]
        b_intended = state.pending_actions["B"]
        a = self._maybe_flip(a_intended)
        b = self._maybe_flip(b_intended)
        outcome = _OUTCOMES[(a, b)]

        if outcome == "DD":
            payoff_a = payoff_b = self.payoff_crash
        elif outcome == "DS":
            payoff_a, payoff_b = self.payoff_win, self.payoff_lose
        elif outcome == "SD":
            payoff_a, payoff_b = self.payoff_lose, self.payoff_win
        else:
            payoff_a = payoff_b = self.payoff_tie

        state.total_scores["A"] = round(state.total_scores["A"] + payoff_a, 2)
        state.total_scores["B"] = round(state.total_scores["B"] + payoff_b, 2)

        entry: dict = {
            "round":        state.round_number,
            "actions":      {"A": a, "B": b},
            "outcome":      outcome,
            "payoffs":      {"A": payoff_a, "B": payoff_b},
            "total_scores": dict(state.total_scores),
        }
        if self.noise > 0:
            entry["intended_actions"] = {"A": a_intended, "B": b_intended}
        state.history.append(entry)

        if state.round_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
        else:
            state.round_number += 1
            state.awaiting = ["A", "B"]
            state.pending_actions = {}

        return state

    def forfeit_round(self, state: ChickenGameState, player: str) -> ChickenGameState:
        """Player forfeits — treated as swerving while the opponent dares."""
        opponent = "B" if player == "A" else "A"
        state = deepcopy(state)
        if player == "A":
            outcome = "SD"
            payoff_a, payoff_b = self.payoff_lose, self.payoff_win
        else:
            outcome = "DS"
            payoff_a, payoff_b = self.payoff_win, self.payoff_lose
        state.total_scores["A"] = round(state.total_scores["A"] + payoff_a, 2)
        state.total_scores["B"] = round(state.total_scores["B"] + payoff_b, 2)
        state.history.append({
            "round":        state.round_number,
            "actions":      {player: "swerve", opponent: "dare"},
            "outcome":      outcome,
            "payoffs":      {"A": payoff_a, "B": payoff_b},
            "forfeit":      True,
            "forfeit_by":   player,
            "total_scores": dict(state.total_scores),
        })
        if state.round_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
        else:
            state.round_number += 1
            state.awaiting = ["A", "B"]
            state.pending_actions = {}
        return state

    def is_terminal(self, state: ChickenGameState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: ChickenGameState,
        session_id: str | None = None,
        config_hash: str | None = None,
    ) -> dict:
        if not self.is_terminal(state):
            raise ValueError("game is not complete")
        sa, sb = state.total_scores["A"], state.total_scores["B"]
        winner = "A" if sa > sb else ("B" if sb > sa else "Tie")
        result = {
            "total_scores": dict(state.total_scores),
            "winner":       winner,
            "history":      list(state.history),
            "metrics":      self.metrics_engine.compute(state.history, state.total_scores),
        }
        if session_id:
            result["session_id"] = session_id
        if config_hash:
            result["config_hash"] = config_hash
        return result

    def public_state(
        self,
        state: ChickenGameState,
        config,
        session_id: str,
        config_hash: str,
    ) -> dict:
        return {
            "session_id":   session_id,
            "config_hash":  config_hash,
            "config":       config.to_dict() if hasattr(config, "to_dict") else {},
            "round":        state.round_number,
            "round_total":  self.num_rounds,
            "phase":        state.phase,
            "awaiting":     list(state.awaiting),
            "total_scores": dict(state.total_scores),
            "history":      list(state.history),
            "payoffs": {
                "win":   self.payoff_win,
                "tie":   self.payoff_tie,
                "lose":  self.payoff_lose,
                "crash": self.payoff_crash,
            },
            "system_prompt": self._system_prompt,
        }
