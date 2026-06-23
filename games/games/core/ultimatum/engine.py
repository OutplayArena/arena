from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from arena.interactive_game_engine import InteractiveGameEngine
from games.core.ultimatum.metrics import UltimatumMetrics


@dataclass
class UltimatumState:
    round_number: int
    phase: str  # "awaiting_proposal", "awaiting_response", "complete"
    proposer: str  # who proposes this round
    responder: str
    awaiting: list[str]
    pending_offer: float | None  # offer amount for proposer
    history: list[dict]
    total_scores: dict[str, float]


class UltimatumGame(InteractiveGameEngine):
    def __init__(
        self,
        num_rounds: int = 10,
        total: float = 100.0,
        min_offer: float = 1.0,
        seed=None,
        system_prompt: str = "",
    ):
        self.num_rounds = num_rounds
        self.total = total
        self.min_offer = min_offer
        self.metrics_engine = UltimatumMetrics()
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> "UltimatumGame":
        return cls(
            num_rounds=config.rounds,
            total=config.total,
            min_offer=config.min_offer,
            seed=config.seed,
            system_prompt=config.system_prompt,
        )

    def human_action_schema(self, config):
        endowment = config.total if hasattr(config, 'total') else 100

        return {
            "type": "object",
            "properties": {
                "offer": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": endowment,
                    "description": f"Offer to responder (0 to {endowment})",
                },
                "accept": {
                    "type": "boolean",
                    "description": "Accept or reject the offer (responder only)",
                }
            },
        }

    def format_human_action(self, raw_action, config):
        if isinstance(raw_action, dict):
            if "offer" in raw_action:
                return {"offer": float(raw_action["offer"])}
            if "accept" in raw_action:
                return {"accept": bool(raw_action["accept"])}
        return raw_action

    def ui_metadata(self, config):
        endowment = config.total if hasattr(config, 'total') else 100
        return {
            "input_type": "ultimatum",
            "endowment": endowment,
            "layout": "ultimatum",
        }

    def get_available_agents(self, config):
        return [
            {"id": "spe", "label": "SPE", "description": "Subgame perfect equilibrium"},
            {"id": "fair", "label": "Fair", "description": "Offers/accepts fair split"},
            {"id": "greedy_proposer", "label": "Greedy Proposer", "description": "Offers minimum"},
            {"id": "random", "label": "Random", "description": "Random offers/decisions"},
        ]

    def _proposer_for_round(self, round_number: int) -> tuple[str, str]:
        """Roles alternate each round."""
        if round_number % 2 == 1:
            return "A", "B"
        return "B", "A"

    def initial_state(self) -> UltimatumState:
        proposer, responder = self._proposer_for_round(1)
        return UltimatumState(
            round_number=1,
            phase="awaiting_proposal",
            proposer=proposer,
            responder=responder,
            awaiting=[proposer],
            pending_offer=None,
            history=[],
            total_scores={"A": 0.0, "B": 0.0},
        )

    def state_from_dict(self, d: dict) -> UltimatumState:
        return UltimatumState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, (int, float, str, dict))

    def validate_player_action(self, state: UltimatumState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player not in state.awaiting:
            raise ValueError(f"player {player!r} is not expected to act now")

        if state.phase == "awaiting_proposal":
            offer = self._parse_offer(action)
            if offer is None or not (0.0 <= offer <= self.total):
                raise ValueError(f"offer must be a number in [0, {self.total}], got {action!r}")
        elif state.phase == "awaiting_response":
            resp = self._parse_response(action)
            if resp not in ("accept", "reject"):
                raise ValueError(f"response must be 'accept' or 'reject', got {action!r}")
        return True

    def _parse_offer(self, action) -> float | None:
        if isinstance(action, (int, float)):
            return float(action)
        if isinstance(action, str):
            try:
                return float(action)
            except ValueError:
                return None
        if isinstance(action, dict):
            v = action.get("offer") or action.get("amount")
            return float(v) if v is not None else None
        return None

    def _parse_response(self, action) -> str:
        if isinstance(action, str):
            return action.lower().strip()
        if isinstance(action, dict):
            if "accept" in action:
                return "accept" if action["accept"] else "reject"
            return str(action.get("response", "reject")).lower()
        return "reject"

    def _round_offer(self, offer: float) -> float:
        """Round offer to nearest min_offer increment."""
        return round(offer / self.min_offer) * self.min_offer

    def apply_action(self, state: UltimatumState, player: str, action) -> UltimatumState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)

        if state.phase == "awaiting_proposal":
            raw_offer = self._parse_offer(action)
            offer = max(0.0, min(self.total, self._round_offer(raw_offer)))
            state.pending_offer = offer
            state.phase = "awaiting_response"
            state.awaiting = [state.responder]

        elif state.phase == "awaiting_response":
            resp = self._parse_response(action)
            offer = state.pending_offer or 0.0
            accepted = (resp == "accept")

            if accepted:
                proposer_payoff = self.total - offer
                responder_payoff = offer
            else:
                proposer_payoff = 0.0
                responder_payoff = 0.0

            state.total_scores[state.proposer] = round(state.total_scores[state.proposer] + proposer_payoff, 2)
            state.total_scores[state.responder] = round(state.total_scores[state.responder] + responder_payoff, 2)

            entry = {
                "round":            state.round_number,
                "proposer":         state.proposer,
                "responder":        state.responder,
                "offer":            offer,
                "offer_fraction":   offer / self.total if self.total > 0 else 0.0,
                "response":         resp,
                "accepted":         accepted,
                "payoffs":          {state.proposer: proposer_payoff, state.responder: responder_payoff},
                "total_scores":     dict(state.total_scores),
            }
            state.history.append(entry)
            state.awaiting = []
            state = self._advance_round(state)

        return state

    def _advance_round(self, state: UltimatumState) -> UltimatumState:
        if state.round_number >= self.num_rounds:
            state.phase = "complete"
        else:
            state.round_number += 1
            state.proposer, state.responder = self._proposer_for_round(state.round_number)
            state.phase = "awaiting_proposal"
            state.awaiting = [state.proposer]
            state.pending_offer = None
        return state

    def is_terminal(self, state: UltimatumState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: UltimatumState,
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
        state: UltimatumState,
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
            "proposer":     state.proposer,
            "responder":    state.responder,
            "awaiting":     list(state.awaiting),
            "pending_offer": state.pending_offer,
            "total_scores": dict(state.total_scores),
            "history":      list(state.history),
            "total":        self.total,
            "system_prompt": self._system_prompt,
        }
