from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field

from nash_arena.game_engine import GameEngine
from games.core.prisonersdilemma.metrics import PDMetrics
from games.core.prisonersdilemma.scenarios import get_scenario, ScenarioId

VALID_ACTIONS = frozenset({"cooperate", "defect"})
_OUTCOMES: dict[tuple[str, str], str] = {
    ("cooperate", "cooperate"): "CC",
    ("cooperate", "defect"):    "CD",
    ("defect",    "cooperate"): "DC",
    ("defect",    "defect"):    "DD",
}


@dataclass
class PDState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_actions: dict[str, str]
    history: list[dict]
    total_scores: dict[str, float]
    messages: list = field(default_factory=list)


class PDGame(GameEngine):
    def __init__(
        self,
        num_rounds: int = 10,
        T: float = 5.0,
        R: float = 3.0,
        P: float = 1.0,
        S: float = 0.0,
        noise: float = 0.0,
        seed: int | None = None,
        scenario: ScenarioId = "prison",
        system_prompt: str = "",
    ):
        self.num_rounds = num_rounds
        self.T = T
        self.R = R
        self.P = P
        self.S = S
        self.noise = noise
        self._rng = random.Random(seed)
        self.metrics_engine = PDMetrics()
        self.scenario = get_scenario(scenario)
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> "PDGame":
        return cls(
            num_rounds=config.rounds,
            T=config.payoff_T,
            R=config.payoff_R,
            P=config.payoff_P,
            S=config.payoff_S,
            noise=config.noise,
            seed=config.seed,
            scenario=config.scenario,
            system_prompt=config.system_prompt,
        )

    def initial_state(self) -> PDState:
        return PDState(
            round_number=1,
            phase="awaiting_action",
            awaiting=["A", "B"],
            pending_actions={},
            history=[],
            total_scores={"A": 0.0, "B": 0.0},
        )

    def state_from_dict(self, d: dict) -> PDState:
        return PDState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, str) and action in VALID_ACTIONS

    def validate_player_action(self, state: PDState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} has already submitted this round")
        if not self.validate_action(action):
            raise ValueError(f"invalid action {action!r}; must be 'cooperate' or 'defect'")
        return True

    def _maybe_flip(self, action: str) -> str:
        if self.noise > 0 and self._rng.random() < self.noise:
            return "defect" if action == "cooperate" else "cooperate"
        return action

    def apply_action(self, state: PDState, player: str, action: str) -> PDState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_actions[player] = action
        state.awaiting = [p for p in state.awaiting if p != player]
        if not state.awaiting:
            state = self._resolve_round(state)
        return state

    def _resolve_round(self, state: PDState) -> PDState:
        a_intended = state.pending_actions["A"]
        b_intended = state.pending_actions["B"]
        a = self._maybe_flip(a_intended)
        b = self._maybe_flip(b_intended)
        outcome = _OUTCOMES[(a, b)]

        if outcome == "CC":
            payoff_a, payoff_b = self.R, self.R
        elif outcome == "CD":
            payoff_a, payoff_b = self.S, self.T
        elif outcome == "DC":
            payoff_a, payoff_b = self.T, self.S
        else:
            payoff_a, payoff_b = self.P, self.P

        state.total_scores["A"] += payoff_a
        state.total_scores["B"] += payoff_b

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

    def is_terminal(self, state: PDState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: PDState,
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
        state: PDState,
        config,
        session_id: str,
        config_hash: str,
    ) -> dict:
        scenario_obj = self.scenario
        return {
            "session_id":   session_id,
            "config_hash":  config_hash,
            "round":        state.round_number,
            "round_total":  self.num_rounds,
            "phase":        state.phase,
            "awaiting":     list(state.awaiting),
            "total_scores": dict(state.total_scores),
            "history":      list(state.history),
            "scenario": {
                "id":               scenario_obj.id,
                "name":             scenario_obj.name,
                "description":      scenario_obj.description,
                "cooperate_label":  scenario_obj.cooperate_label,
                "defect_label":     scenario_obj.defect_label,
            },
            "messages": self.communication_log(state),
            "communication_config": self.communication_config().to_dict(),
            "system_prompt": self._system_prompt,
        }

    def forfeit_round(self, state: PDState, player: str) -> PDState:
        opponent = "B" if player == "A" else "A"
        state = deepcopy(state)
        # Forfeit treated as player defecting, opponent cooperating
        payoff_player   = self.S
        payoff_opponent = self.T
        state.total_scores[player]   += payoff_player
        state.total_scores[opponent] += payoff_opponent
        outcome = "DC" if player == "B" else "CD"
        state.history.append({
            "round":        state.round_number,
            "actions":      {opponent: "cooperate"},
            "outcome":      outcome,
            "payoffs":      {player: payoff_player, opponent: payoff_opponent},
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
