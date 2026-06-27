from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass

from arena.interactive_game_engine import InteractiveGameEngine
from games.core.stag_hunt.metrics import StagHuntMetrics

VALID_ACTIONS = frozenset({"stag", "hare"})

_OUTCOMES: dict[tuple[str, str], str] = {
    ("stag", "stag"): "SS",
    ("stag", "hare"): "SH",
    ("hare", "stag"): "HS",
    ("hare", "hare"): "HH",
}


@dataclass
class StagHuntState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_actions: dict[str, str]
    history: list[dict]
    total_scores: dict[str, float]


class StagHuntGame(InteractiveGameEngine):
    def __init__(
        self,
        num_rounds: int = 10,
        payoff_stag_stag: float = 4.0,
        payoff_hare_hare: float = 2.0,
        payoff_stag_hare: float = 0.0,
        noise: float = 0.0,
        seed: int | None = None,
        system_prompt: str = "",
    ):
        self.num_rounds = num_rounds
        self.payoff_stag_stag = payoff_stag_stag
        self.payoff_hare_hare = payoff_hare_hare
        self.payoff_stag_hare = payoff_stag_hare
        self.noise = noise
        self._rng = random.Random(seed)
        self.metrics_engine = StagHuntMetrics()
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> "StagHuntGame":
        return cls(
            num_rounds=config.rounds,
            payoff_stag_stag=config.payoff_stag_stag,
            payoff_hare_hare=config.payoff_hare_hare,
            payoff_stag_hare=config.payoff_stag_hare,
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
                    "enum": ["stag", "hare"],
                    "description": "Hunt stag (cooperate) or hunt hare (defect)",
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
            "choices": ["stag", "hare"],
            "layout": "stag_hunt",
        }

    def get_available_agents(self, config):
        return [
            {"id": "always_stag", "label": "Always Stag", "description": "Always hunts stag"},
            {"id": "always_hare", "label": "Always Hare", "description": "Always hunts hare"},
            {"id": "tit_for_tat", "label": "Tit for Tat", "description": "Copies opponent's last move"},
        ]

    def initial_state(self) -> StagHuntState:
        return StagHuntState(
            round_number=1,
            phase="awaiting_action",
            awaiting=["A", "B"],
            pending_actions={},
            history=[],
            total_scores={"A": 0.0, "B": 0.0},
        )

    def state_from_dict(self, d: dict) -> StagHuntState:
        return StagHuntState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, str) and action in VALID_ACTIONS

    def validate_player_action(self, state: StagHuntState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} has already submitted this round")
        if not self.validate_action(action):
            raise ValueError(f"invalid action {action!r}; must be 'stag' or 'hare'")
        return True

    def _maybe_flip(self, action: str) -> str:
        if self.noise > 0 and self._rng.random() < self.noise:
            return "hare" if action == "stag" else "stag"
        return action

    def apply_action(self, state: StagHuntState, player: str, action: str) -> StagHuntState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_actions[player] = action
        state.awaiting = [p for p in state.awaiting if p != player]
        if not state.awaiting:
            state = self._resolve_round(state)
        return state

    def _resolve_round(self, state: StagHuntState) -> StagHuntState:
        a_intended = state.pending_actions["A"]
        b_intended = state.pending_actions["B"]
        a = self._maybe_flip(a_intended)
        b = self._maybe_flip(b_intended)
        outcome = _OUTCOMES[(a, b)]

        if outcome == "SS":
            payoff_a = payoff_b = self.payoff_stag_stag
        elif outcome == "SH":
            payoff_a, payoff_b = self.payoff_stag_hare, self.payoff_hare_hare
        elif outcome == "HS":
            payoff_a, payoff_b = self.payoff_hare_hare, self.payoff_stag_hare
        else:
            payoff_a = payoff_b = self.payoff_hare_hare

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

    def forfeit_round(self, state: StagHuntState, player: str) -> StagHuntState:
        """Player forfeits — treated as choosing hare while opponent chooses stag."""
        opponent = "B" if player == "A" else "A"
        state = deepcopy(state)
        # Forfeiting = choosing hare; opponent gets stag-vs-hare advantage.
        if player == "A":
            outcome = "HS"
            payoff_a, payoff_b = self.payoff_hare_hare, self.payoff_stag_hare
        else:
            outcome = "SH"
            payoff_a, payoff_b = self.payoff_stag_hare, self.payoff_hare_hare
        state.total_scores["A"] = round(state.total_scores["A"] + payoff_a, 2)
        state.total_scores["B"] = round(state.total_scores["B"] + payoff_b, 2)
        state.history.append({
            "round":        state.round_number,
            "actions":      {player: "hare", opponent: "stag"},
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

    def is_terminal(self, state: StagHuntState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: StagHuntState,
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
        state: StagHuntState,
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
                "stag_stag": self.payoff_stag_stag,
                "hare_hare": self.payoff_hare_hare,
                "stag_hare": self.payoff_stag_hare,
            },
            "system_prompt": self._system_prompt,
        }
