from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field

from arena.interactive_game_engine import InteractiveGameEngine
from games.core.public_goods.metrics import PublicGoodsMetrics


@dataclass
class PGGState:
    round_number: int
    phase: str  # "awaiting_contribution", "awaiting_punishment", "complete"
    awaiting: list[str]
    pending_contributions: dict[str, float]
    pending_punishments: dict[str, dict[str, float]]  # punisher -> {target: amount}
    history: list[dict]
    total_scores: dict[str, float]
    # Contribution payoffs held between contribution and punishment phases.
    # Stored as a proper field so state survives serialization round-trips.
    round_payoffs: dict[str, float] = field(default_factory=dict)


class PublicGoodsGame(InteractiveGameEngine):
    def __init__(
        self,
        num_players: int = 4,
        num_rounds: int = 10,
        endowment: float = 10.0,
        multiplier: float = 2.0,
        punishment: bool = False,
        punishment_cost: float = 1.0,
        punishment_effect: float = 3.0,
        seed: int | None = None,
        system_prompt: str = "",
    ):
        self.num_players = num_players
        self.player_ids = [chr(ord("A") + i) for i in range(num_players)]
        self.num_rounds = num_rounds
        self.endowment = endowment
        self.multiplier = multiplier
        self.punishment = punishment
        self.punishment_cost = punishment_cost
        self.punishment_effect = punishment_effect
        self._rng = random.Random(seed)
        self.metrics_engine = PublicGoodsMetrics()
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> "PublicGoodsGame":
        return cls(
            num_players=config.players,
            num_rounds=config.rounds,
            endowment=config.endowment,
            multiplier=config.multiplier,
            punishment=(config.variant == "punishment"),
            punishment_cost=config.punishment_cost,
            punishment_effect=config.punishment_effect,
            seed=config.seed,
            system_prompt=config.system_prompt,
        )

    def human_action_schema(self, config):
        endowment = config.endowment if hasattr(config, "endowment") else 10
        has_punishment = hasattr(config, "punishment_cost") and config.punishment_cost is not None

        properties = {
            "contribution": {
                "type": "number",
                "minimum": 0,
                "maximum": endowment,
                "description": f"Contribution to public goods (0 to {endowment})",
            }
        }

        if has_punishment:
            properties["punishment"] = {
                "type": "number",
                "minimum": 0,
                "description": "Punishment points to apply to opponent (optional)",
            }

        return {
            "type": "object",
            "properties": properties,
            "required": ["contribution"],
        }

    def format_human_action(self, raw_action, config):
        if isinstance(raw_action, (int, float)):
            return float(raw_action)
        if isinstance(raw_action, dict):
            contribution = float(raw_action.get("contribution", 0))
            if "punishment" in raw_action:
                return {
                    "contribution": contribution,
                    "punishment": float(raw_action["punishment"]),
                }
            return contribution
        return float(raw_action)

    def ui_metadata(self, config):
        endowment = config.endowment if hasattr(config, "endowment") else 10
        has_punishment = hasattr(config, "punishment_cost") and config.punishment_cost is not None
        return {
            "input_type": "slider",
            "min": 0,
            "max": endowment,
            "step": 1,
            "has_punishment": has_punishment,
            "layout": "public_goods",
        }

    def get_available_agents(self, config):
        return [
            {"id": "always_contribute_max", "label": "Always Max", "description": "Always contributes maximum"},
            {"id": "always_contribute_zero", "label": "Always Zero", "description": "Always contributes zero"},
            {"id": "nash_equilibrium", "label": "Nash Equilibrium", "description": "Always contributes zero (Nash)"},
            {"id": "linear_decay", "label": "Linear Decay", "description": "Contribution decreases linearly"},
        ]

    def initial_state(self) -> PGGState:
        return PGGState(
            round_number=1,
            phase="awaiting_contribution",
            awaiting=list(self.player_ids),
            pending_contributions={},
            pending_punishments={},
            history=[],
            total_scores={p: 0.0 for p in self.player_ids},
        )

    def state_from_dict(self, d: dict) -> PGGState:
        return PGGState(**d)

    def validate_action(self, action) -> bool:
        if isinstance(action, (int, float)):
            return 0.0 <= float(action) <= self.endowment
        if isinstance(action, dict):
            return True  # punishment dict
        return False

    def validate_player_action(self, state: PGGState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in self.player_ids:
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} has already submitted this phase")

        if state.phase == "awaiting_contribution":
            try:
                val = float(action)
            except (TypeError, ValueError):
                raise ValueError(f"contribution must be a number, got {action!r}")
            if not (0.0 <= val <= self.endowment):
                raise ValueError(f"contribution {val} out of range [0, {self.endowment}]")
        elif state.phase == "awaiting_punishment":
            if not isinstance(action, dict):
                raise ValueError("punishment action must be a dict mapping target_id -> amount")
            for target, amt in action.items():
                if target not in self.player_ids or target == player:
                    raise ValueError(f"invalid punishment target: {target!r}")
                if float(amt) < 0:
                    raise ValueError("punishment amounts must be non-negative")
        return True

    def apply_action(self, state: PGGState, player: str, action) -> PGGState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)

        if state.phase == "awaiting_contribution":
            state.pending_contributions[player] = float(action)
        elif state.phase == "awaiting_punishment":
            state.pending_punishments[player] = {k: float(v) for k, v in action.items()}

        state.awaiting = [p for p in state.awaiting if p != player]

        if not state.awaiting:
            if state.phase == "awaiting_contribution":
                if self.punishment:
                    state = self._resolve_contributions(state, resolve_final=False)
                    state.phase = "awaiting_punishment"
                    state.awaiting = list(self.player_ids)
                    state.pending_punishments = {}
                else:
                    state = self._resolve_contributions(state, resolve_final=True)
            elif state.phase == "awaiting_punishment":
                state = self._resolve_punishment(state)

        return state

    def _resolve_contributions(self, state: PGGState, resolve_final: bool) -> PGGState:
        contribs = state.pending_contributions
        total_pool = sum(contribs.values()) * self.multiplier
        share = total_pool / self.num_players

        round_payoffs: dict[str, float] = {}
        for p in self.player_ids:
            kept = self.endowment - contribs.get(p, 0.0)
            round_payoffs[p] = kept + share

        entry: dict = {
            "round":         state.round_number,
            "phase":         "contribution",
            "contributions": dict(contribs),
            "pool":          sum(contribs.values()),
            "total_pool":    total_pool,
            "share":         share,
            "round_payoffs": dict(round_payoffs),
        }
        state.history.append(entry)
        state.round_payoffs = round_payoffs

        if resolve_final:
            for p in self.player_ids:
                state.total_scores[p] = round(state.total_scores[p] + round_payoffs[p], 2)
            state.history[-1]["total_scores"] = dict(state.total_scores)
            state = self._advance_round(state)

        return state

    def _resolve_punishment(self, state: PGGState) -> PGGState:
        round_payoffs = state.round_payoffs
        # Apply contributions to total first
        for p in self.player_ids:
            state.total_scores[p] = round(state.total_scores[p] + round_payoffs.get(p, 0.0), 2)

        punishment_costs: dict[str, float] = {p: 0.0 for p in self.player_ids}
        punishment_received: dict[str, float] = {p: 0.0 for p in self.player_ids}

        for punisher, targets in state.pending_punishments.items():
            for target, amount in targets.items():
                cost = amount * self.punishment_cost
                effect = amount * self.punishment_effect
                punishment_costs[punisher] += cost
                punishment_received[target] += effect

        for p in self.player_ids:
            state.total_scores[p] -= punishment_costs[p] + punishment_received[p]

        state.history[-1]["punishment_costs"] = punishment_costs
        state.history[-1]["punishment_received"] = punishment_received
        state.history[-1]["punishments"] = {
            k: dict(v) for k, v in state.pending_punishments.items()
        }
        state.history[-1]["total_scores"] = dict(state.total_scores)

        state = self._advance_round(state)
        return state

    def _advance_round(self, state: PGGState) -> PGGState:
        state.round_payoffs = {}
        if state.round_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
        else:
            state.round_number += 1
            state.phase = "awaiting_contribution"
            state.awaiting = list(self.player_ids)
            state.pending_contributions = {}
            state.pending_punishments = {}
        return state

    def is_terminal(self, state: PGGState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: PGGState,
        session_id: str | None = None,
        config_hash: str | None = None,
    ) -> dict:
        if not self.is_terminal(state):
            raise ValueError("game is not complete")
        scores = state.total_scores
        max_score = max(scores.values()) if scores else 0.0
        winners = [p for p, s in scores.items() if s == max_score]
        winner = winners[0] if len(winners) == 1 else "Tie"
        result = {
            "total_scores": dict(scores),
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
        state: PGGState,
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
            "endowment":    self.endowment,
            "multiplier":   self.multiplier,
            "punishment":   self.punishment,
            "system_prompt": self._system_prompt,
        }
