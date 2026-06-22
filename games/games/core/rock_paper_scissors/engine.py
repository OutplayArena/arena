from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from arena.interactive_game_engine import InteractiveGameEngine
from games.core.rock_paper_scissors.metrics import RPSMetrics

BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
VALID_MOVES = frozenset({"rock", "paper", "scissors"})


@dataclass
class RPSState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_actions: dict[str, str]
    history: list[dict]
    total_scores: dict[str, float]


class RPSGame(InteractiveGameEngine):
    def __init__(self, num_rounds: int = 10):
        self.num_rounds = num_rounds
        self.metrics_engine = RPSMetrics()

    @classmethod
    def from_config(cls, config) -> "RPSGame":
        return cls(num_rounds=config.rounds)

    def human_action_schema(self, config: Any) -> dict:
        return {
            "type": "object",
            "properties": {
                "move": {
                    "type": "string",
                    "enum": ["rock", "paper", "scissors"],
                    "description": "Your move choice",
                }
            },
            "required": ["move"],
        }

    def format_human_action(self, raw_action: Any, config: Any) -> str:
        if isinstance(raw_action, str):
            return raw_action.lower()
        if isinstance(raw_action, dict):
            return raw_action.get("move", "").lower()
        return str(raw_action).lower()

    def ui_metadata(self, config: Any) -> dict:
        return {
            "input_type": "choice",
            "choices": ["rock", "paper", "scissors"],
            "layout": "rps",
        }

    def get_available_agents(self, config: Any) -> list[dict]:
        return [
            {"id": "uniform", "label": "Uniform Random", "description": "Chooses randomly with equal probability"},
            {"id": "rock_heavy", "label": "Rock Heavy", "description": "Prefers rock over other moves"},
            {"id": "pattern_exploit", "label": "Pattern Exploit", "description": "Exploits predictable patterns"},
        ]

    def initial_state(self) -> RPSState:
        return RPSState(
            round_number=1,
            phase="awaiting_action",
            awaiting=["A", "B"],
            pending_actions={},
            history=[],
            total_scores={"A": 0.0, "B": 0.0},
        )

    def state_from_dict(self, d: dict) -> RPSState:
        return RPSState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, str) and action in VALID_MOVES

    def validate_player_action(self, state: RPSState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} has already submitted this round")
        if not self.validate_action(action):
            raise ValueError(
                f"invalid action {action!r}; must be one of {sorted(VALID_MOVES)}"
            )
        return True

    def apply_action(self, state: RPSState, player: str, action: str) -> RPSState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_actions[player] = action
        state.awaiting = [p for p in state.awaiting if p != player]
        if not state.awaiting:
            state = self._resolve_round(state)
        return state

    def _resolve_round(self, state: RPSState) -> RPSState:
        a, b = state.pending_actions["A"], state.pending_actions["B"]
        if a == b:
            score_a, score_b, winner = 0.0, 0.0, "Tie"
        elif BEATS[a] == b:
            score_a, score_b, winner = 1.0, -1.0, "A"
        else:
            score_a, score_b, winner = -1.0, 1.0, "B"

        state.total_scores["A"] = round(state.total_scores["A"] + score_a, 2)
        state.total_scores["B"] = round(state.total_scores["B"] + score_b, 2)

        state.history.append({
            "round":        state.round_number,
            "actions":      {"A": a, "B": b},
            "scores":       {"A": score_a, "B": score_b},
            "winner":       winner,
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

    def is_terminal(self, state: RPSState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: RPSState,
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
        state: RPSState,
        config,
        session_id: str,
        config_hash: str,
    ) -> dict:
        return {
            "session_id":   session_id,
            "config_hash":  config_hash,
            "round":        state.round_number,
            "round_total":  self.num_rounds,
            "phase":        state.phase,
            "awaiting":     list(state.awaiting),
            "total_scores": dict(state.total_scores),
            "history":      list(state.history),
        }

    def forfeit_round(self, state: RPSState, player: str) -> RPSState:
        opponent = "B" if player == "A" else "A"
        state = deepcopy(state)
        state.total_scores[opponent] = round(state.total_scores[opponent] + 1.0, 2)
        state.total_scores[player] = round(state.total_scores[player] - 1.0, 2)
        state.history.append({
            "round":        state.round_number,
            "actions":      {},
            "scores":       {player: -1.0, opponent: 1.0},
            "winner":       opponent,
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
