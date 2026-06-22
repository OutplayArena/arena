from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass

from arena.interactive_game_engine import InteractiveGameEngine
from games.core.cournot_duopoly.metrics import CournotMetrics


@dataclass
class CournotState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_quantities: dict[str, float]
    history: list[dict]
    total_scores: dict[str, float]


class CournotGame(InteractiveGameEngine):
    def __init__(
        self,
        num_rounds: int = 10,
        demand_a: float = 120.0,
        demand_b: float = 1.0,
        cost_per_unit: float = 0.0,
        max_quantity: float = 120.0,
        seed=None,
        system_prompt: str = "",
    ):
        self.num_rounds = num_rounds
        self.demand_a = demand_a
        self.demand_b = demand_b
        self.cost_per_unit = cost_per_unit
        self.max_quantity = max_quantity
        self._rng = random.Random(seed)
        self.metrics_engine = CournotMetrics()
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> "CournotGame":
        return cls(
            num_rounds=config.rounds,
            demand_a=config.demand_a,
            demand_b=config.demand_b,
            cost_per_unit=config.cost_per_unit,
            max_quantity=config.max_quantity,
            seed=config.seed,
            system_prompt=config.system_prompt,
        )

    def human_action_schema(self, config):
        max_qty = config.max_quantity if hasattr(config, 'max_quantity') else 100
        return {
            "type": "object",
            "properties": {
                "quantity": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": max_qty,
                    "description": f"Production quantity (0 to {max_qty})",
                }
            },
            "required": ["quantity"],
        }

    def format_human_action(self, raw_action, config):
        if isinstance(raw_action, (int, float)):
            return float(raw_action)
        if isinstance(raw_action, dict):
            return float(raw_action.get("quantity", 0))
        return float(raw_action)

    def ui_metadata(self, config):
        max_qty = config.max_quantity if hasattr(config, 'max_quantity') else 100
        return {
            "input_type": "slider",
            "min": 0,
            "max": max_qty,
            "step": 1,
            "layout": "cournot",
        }

    def get_available_agents(self, config):
        return [
            {"id": "nash_equilibrium", "label": "Nash Equilibrium", "description": "Plays Nash equilibrium quantity"},
            {"id": "collussive", "label": "Collusive", "description": "Plays collusive quantity"},
            {"id": "greedy", "label": "Greedy", "description": "Best response to opponent's last move"},
            {"id": "random", "label": "Random", "description": "Random quantity"},
        ]

    @property
    def nash_quantity(self) -> float:
        return (self.demand_a - self.cost_per_unit) / (3 * self.demand_b)

    @property
    def collusive_quantity(self) -> float:
        return (self.demand_a - self.cost_per_unit) / (4 * self.demand_b)

    def _profit(self, q_self: float, q_other: float) -> float:
        price = max(0.0, self.demand_a - self.demand_b * (q_self + q_other))
        return (price - self.cost_per_unit) * q_self

    def initial_state(self) -> CournotState:
        return CournotState(
            round_number=1,
            phase="awaiting_action",
            awaiting=["A", "B"],
            pending_quantities={},
            history=[],
            total_scores={"A": 0.0, "B": 0.0},
        )

    def state_from_dict(self, d: dict) -> CournotState:
        return CournotState(**d)

    def validate_action(self, action) -> bool:
        try:
            q = float(action)
            return 0.0 <= q <= self.max_quantity
        except (TypeError, ValueError):
            return False

    def validate_player_action(self, state: CournotState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} has already submitted this round")
        try:
            q = float(action)
        except (TypeError, ValueError):
            raise ValueError(f"quantity must be a number, got {action!r}")
        if not (0.0 <= q <= self.max_quantity):
            raise ValueError(f"quantity {q} out of range [0, {self.max_quantity}]")
        return True

    def apply_action(self, state: CournotState, player: str, action) -> CournotState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_quantities[player] = float(action)
        state.awaiting = [p for p in state.awaiting if p != player]
        if not state.awaiting:
            state = self._resolve_round(state)
        return state

    def _resolve_round(self, state: CournotState) -> CournotState:
        qa = state.pending_quantities["A"]
        qb = state.pending_quantities["B"]
        total_q = qa + qb
        price = max(0.0, self.demand_a - self.demand_b * total_q)
        profit_a = self._profit(qa, qb)
        profit_b = self._profit(qb, qa)

        state.total_scores["A"] = round(state.total_scores["A"] + profit_a, 2)
        state.total_scores["B"] = round(state.total_scores["B"] + profit_b, 2)

        state.history.append({
            "round":          state.round_number,
            "quantities":     {"A": qa, "B": qb},
            "total_quantity": total_q,
            "price":          price,
            "payoffs":        {"A": profit_a, "B": profit_b},
            "total_scores":   dict(state.total_scores),
        })

        if state.round_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
        else:
            state.round_number += 1
            state.awaiting = ["A", "B"]
            state.pending_quantities = {}
        return state

    def is_terminal(self, state: CournotState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: CournotState,
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
            "metrics":      self.metrics_engine.compute(
                state.history, state.total_scores,
                nash_q=self.nash_quantity, collusive_q=self.collusive_quantity
            ),
        }
        if session_id:
            result["session_id"] = session_id
        if config_hash:
            result["config_hash"] = config_hash
        return result

    def public_state(self, state, config, session_id, config_hash) -> dict:
        return {
            "session_id":      session_id,
            "config_hash":     config_hash,
            "round":           state.round_number,
            "round_total":     self.num_rounds,
            "phase":           state.phase,
            "awaiting":        list(state.awaiting),
            "total_scores":    dict(state.total_scores),
            "history":         list(state.history),
            "demand_a":        self.demand_a,
            "demand_b":        self.demand_b,
            "cost_per_unit":   self.cost_per_unit,
            "max_quantity":    self.max_quantity,
            "nash_quantity":   self.nash_quantity,
            "collusive_quantity": self.collusive_quantity,
            "system_prompt":   self._system_prompt,
        }
