from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass

from arena.interactive_game_engine import InteractiveGameEngine
from games.core.battle_of_the_sexes.metrics import BoSMetrics


@dataclass
class BoSState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_actions: dict[str, str]
    history: list[dict]
    total_scores: dict[str, float]


class BoSGame(InteractiveGameEngine):
    """
    Player A prefers option_a; Player B prefers option_b.
    Payoff matrix:
               B: option_a    B: option_b
    A: option_a  (pref_a, nonpref)  (mismatch, mismatch)
    A: option_b  (mismatch, mismatch)  (nonpref, pref_b)
    """

    def __init__(
        self,
        num_rounds: int = 10,
        payoff_preferred_a: float = 3.0,
        payoff_preferred_b: float = 3.0,
        payoff_nonpreferred: float = 2.0,
        payoff_mismatch: float = 0.0,
        option_a_label: str = "opera",
        option_b_label: str = "football",
        seed=None,
        system_prompt: str = "",
    ):
        self.num_rounds = num_rounds
        self.payoff_preferred_a = payoff_preferred_a
        self.payoff_preferred_b = payoff_preferred_b
        self.payoff_nonpreferred = payoff_nonpreferred
        self.payoff_mismatch = payoff_mismatch
        self.option_a = option_a_label
        self.option_b = option_b_label
        self._valid_actions = frozenset({option_a_label, option_b_label})
        self._rng = random.Random(seed)
        self.metrics_engine = BoSMetrics()
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> "BoSGame":
        return cls(
            num_rounds=config.rounds,
            payoff_preferred_a=config.payoff_preferred_a,
            payoff_preferred_b=config.payoff_preferred_b,
            payoff_nonpreferred=config.payoff_nonpreferred,
            payoff_mismatch=config.payoff_mismatch,
            option_a_label=config.option_a_label,
            option_b_label=config.option_b_label,
            seed=config.seed,
            system_prompt=config.system_prompt,
        )

    def human_action_schema(self, config):
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [self.option_a, self.option_b],
                    "description": f"Choose {self.option_a} or {self.option_b}",
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
            "choices": [self.option_a, self.option_b],
            "layout": "bos",
        }

    def get_available_agents(self, config):
        return [
            {"id": "always_opera", "label": "Always Opera", "description": "Always chooses opera"},
            {"id": "always_football", "label": "Always Football", "description": "Always chooses football"},
            {"id": "tit_for_tat", "label": "Tit for Tat", "description": "Copies opponent's last move"},
            {"id": "mixed_nash", "label": "Mixed Nash", "description": "Plays mixed Nash equilibrium"},
        ]

    def initial_state(self) -> BoSState:
        return BoSState(
            round_number=1,
            phase="awaiting_action",
            awaiting=["A", "B"],
            pending_actions={},
            history=[],
            total_scores={"A": 0.0, "B": 0.0},
        )

    def state_from_dict(self, d: dict) -> BoSState:
        return BoSState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, str) and action in self._valid_actions

    def validate_player_action(self, state: BoSState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} has already submitted this round")
        if not self.validate_action(action):
            raise ValueError(
                f"invalid action {action!r}; must be {self.option_a!r} or {self.option_b!r}"
            )
        return True

    def apply_action(self, state: BoSState, player: str, action: str) -> BoSState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_actions[player] = action
        state.awaiting = [p for p in state.awaiting if p != player]
        if not state.awaiting:
            state = self._resolve_round(state)
        return state

    def _resolve_round(self, state: BoSState) -> BoSState:
        a_act = state.pending_actions["A"]
        b_act = state.pending_actions["B"]
        coordinated = (a_act == b_act)

        if coordinated and a_act == self.option_a:
            payoff_a = self.payoff_preferred_a
            payoff_b = self.payoff_nonpreferred
            outcome = "AA"
        elif coordinated and a_act == self.option_b:
            payoff_a = self.payoff_nonpreferred
            payoff_b = self.payoff_preferred_b
            outcome = "BB"
        else:
            payoff_a = self.payoff_mismatch
            payoff_b = self.payoff_mismatch
            outcome = "AB" if a_act == self.option_a else "BA"

        state.total_scores["A"] = round(state.total_scores["A"] + payoff_a, 2)
        state.total_scores["B"] = round(state.total_scores["B"] + payoff_b, 2)

        state.history.append({
            "round":        state.round_number,
            "actions":      {"A": a_act, "B": b_act},
            "outcome":      outcome,
            "coordinated":  coordinated,
            "payoffs":      {"A": payoff_a, "B": payoff_b},
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

    def is_terminal(self, state: BoSState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: BoSState,
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

    def public_state(self, state, config, session_id, config_hash) -> dict:
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
            "option_a":     self.option_a,
            "option_b":     self.option_b,
            "system_prompt": self._system_prompt,
        }
