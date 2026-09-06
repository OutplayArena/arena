from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field

from arena.interactive_game_engine import InteractiveGameEngine

from games.community.vickrey_auction.metrics import VickreyAuctionMetrics


@dataclass
class VickreyAuctionState:
    round_number: int
    phase: str
    awaiting: list[str]
    pending_bids: dict[str, float]
    private_values: dict[str, float]
    history: list[dict]
    total_scores: dict[str, float]
    forfeits: list[str] = field(default_factory=list)


class VickreyAuctionGame(InteractiveGameEngine):
    def __init__(
        self,
        num_players: int = 3,
        num_rounds: int = 10,
        value_min: float = 0.0,
        value_max: float = 100.0,
        max_bid: float = 200.0,
        truthful_tolerance: float = 1.0,
        seed: int | None = None,
        system_prompt: str = "",
    ):
        self.num_players = num_players
        self.player_ids = [chr(ord("A") + i) for i in range(num_players)]
        self.num_rounds = num_rounds
        self.value_min = value_min
        self.value_max = value_max
        self.max_bid = max_bid
        self.truthful_tolerance = truthful_tolerance
        self._rng = random.Random(seed)
        self.metrics_engine = VickreyAuctionMetrics(truthful_tolerance=truthful_tolerance)
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> VickreyAuctionGame:
        return cls(
            num_players=config.players,
            num_rounds=config.rounds,
            value_min=config.value_min,
            value_max=config.value_max,
            max_bid=config.max_bid,
            truthful_tolerance=config.truthful_tolerance,
            seed=config.seed,
            system_prompt=config.system_prompt,
        )

    def human_action_schema(self, config):
        max_bid = config.max_bid if hasattr(config, "max_bid") else 200
        return {
            "type": "object",
            "properties": {
                "bid": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": max_bid,
                    "description": f"Sealed bid (0 to {max_bid})",
                }
            },
            "required": ["bid"],
        }

    def format_human_action(self, raw_action, config):
        if isinstance(raw_action, (int, float)):
            return float(raw_action)
        if isinstance(raw_action, dict):
            return float(raw_action.get("bid", 0))
        return float(raw_action)

    def ui_metadata(self, config):
        max_bid = config.max_bid if hasattr(config, "max_bid") else 200
        return {
            "input_type": "slider",
            "min": 0,
            "max": max_bid,
            "step": 0.5,
            "layout": "vickrey_auction",
        }

    def get_available_agents(self, config):
        return [
            {"id": "truthful", "label": "Truthful", "description": "Always bids exactly its private value"},
            {"id": "shader", "label": "Shader", "description": "Underbids relative to its private value"},
            {"id": "overbidder", "label": "Overbidder", "description": "Overbids relative to its private value"},
            {"id": "random", "label": "Random", "description": "Bids uniformly at random up to the bid ceiling"},
        ]

    def _draw_values(self) -> dict[str, float]:
        return {p: round(self._rng.uniform(self.value_min, self.value_max), 2) for p in self.player_ids}

    def initial_state(self) -> VickreyAuctionState:
        return VickreyAuctionState(
            round_number=1,
            phase="awaiting_action",
            awaiting=list(self.player_ids),
            pending_bids={},
            private_values=self._draw_values(),
            history=[],
            total_scores={p: 0.0 for p in self.player_ids},
            forfeits=[],
        )

    def state_from_dict(self, d: dict) -> VickreyAuctionState:
        return VickreyAuctionState(**d)

    def validate_action(self, action) -> bool:
        try:
            bid = float(action)
        except (TypeError, ValueError):
            return False
        return 0.0 <= bid <= self.max_bid

    def validate_player_action(self, state: VickreyAuctionState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in self.player_ids:
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} has already submitted this round")
        try:
            bid = float(action)
        except (TypeError, ValueError):
            raise ValueError(f"bid must be a number, got {action!r}")
        if not (0.0 <= bid <= self.max_bid):
            raise ValueError(f"bid {bid} out of range [0, {self.max_bid}]")
        return True

    def apply_action(self, state: VickreyAuctionState, player: str, action) -> VickreyAuctionState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        state.pending_bids[player] = float(action)
        state.awaiting = [p for p in state.awaiting if p != player]
        if not state.awaiting:
            state = self._resolve_round(state)
        return state

    def _resolve_round(self, state: VickreyAuctionState) -> VickreyAuctionState:
        bids = state.pending_bids
        values = state.private_values

        ranked = sorted(self.player_ids, key=lambda p: bids[p], reverse=True)
        top_bid = bids[ranked[0]]
        tied_winners = [p for p in ranked if bids[p] == top_bid]
        winner = tied_winners[0] if len(tied_winners) == 1 else self._rng.choice(tied_winners)
        price = bids[ranked[1]]

        payoffs: dict[str, float] = {}
        for p in self.player_ids:
            payoffs[p] = round(values[p] - price, 2) if p == winner else 0.0
            state.total_scores[p] = round(state.total_scores[p] + payoffs[p], 2)

        entry: dict = {
            "round":        state.round_number,
            "values":       dict(values),
            "actions":      dict(bids),
            "winner":       winner,
            "price":        price,
            "payoffs":      dict(payoffs),
            "total_scores": dict(state.total_scores),
        }
        if state.forfeits:
            entry["forfeits"] = list(state.forfeits)
        state.history.append(entry)

        if state.round_number >= self.num_rounds:
            state.phase = "complete"
            state.awaiting = []
        else:
            state.round_number += 1
            state.awaiting = list(self.player_ids)
            state.pending_bids = {}
            state.private_values = self._draw_values()
            state.forfeits = []

        return state

    def forfeit_round(self, state: VickreyAuctionState, player: str) -> VickreyAuctionState:
        """Player forfeits — treated as submitting a zero bid."""
        state = deepcopy(state)
        if player in state.awaiting:
            state.pending_bids[player] = 0.0
            state.awaiting = [p for p in state.awaiting if p != player]
            state.forfeits.append(player)
            if not state.awaiting:
                state = self._resolve_round(state)
        return state

    def is_terminal(self, state: VickreyAuctionState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: VickreyAuctionState,
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
        state: VickreyAuctionState,
        config,
        session_id: str,
        config_hash: str,
    ) -> dict:
        return {
            "session_id":     session_id,
            "config_hash":    config_hash,
            "config":         config.to_dict() if hasattr(config, "to_dict") else {},
            "round":          state.round_number,
            "round_total":    self.num_rounds,
            "phase":          state.phase,
            "awaiting":       list(state.awaiting),
            "total_scores":   dict(state.total_scores),
            "history":        list(state.history),
            "private_values": dict(state.private_values),
            "value_min":      self.value_min,
            "value_max":      self.value_max,
            "max_bid":        self.max_bid,
            "system_prompt":  self._system_prompt,
        }
