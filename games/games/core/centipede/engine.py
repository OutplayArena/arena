from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from nash_arena.game_engine import GameEngine
from games.core.centipede.metrics import CentipedeMetrics

VALID_ACTIONS = frozenset({"take", "pass"})


@dataclass
class CentipedeState:
    step: int
    current_player: str  # "A" or "B"
    phase: str           # "awaiting_action", "complete"
    pot_a: float
    pot_b: float
    history: list[dict]
    total_scores: dict[str, float]
    game_ended_by: str | None  # player who took, or "forced" at max_steps
    messages: list = field(default_factory=list)


class CentipedeGame(GameEngine):
    """
    Standard centipede payoff structure:
      Step 1 (A moves): A can take (4,1) or pass → pots double
      Step 2 (B moves): B can take (2,8) or pass → pots double
      Step 3 (A moves): A can take (16,4) or pass → pots double
      ...
      At max_steps: forced payout at current pots.

    The TakeFirst payoff at step s for the taker is max(pot_a, pot_b)*factor,
    using the standard doubling setup.
    """

    def __init__(
        self,
        max_steps: int = 6,
        initial_pot_a: float = 4.0,
        initial_pot_b: float = 1.0,
        growth_factor: float = 2.0,
        seed=None,
        system_prompt: str = "",
    ):
        self.max_steps = max_steps
        self.initial_pot_a = initial_pot_a
        self.initial_pot_b = initial_pot_b
        self.growth_factor = growth_factor
        self.metrics_engine = CentipedeMetrics()
        self._system_prompt = system_prompt

    @classmethod
    def from_config(cls, config) -> "CentipedeGame":
        return cls(
            max_steps=config.max_steps,
            initial_pot_a=config.initial_pot_a,
            initial_pot_b=config.initial_pot_b,
            growth_factor=config.growth_factor,
            seed=config.seed,
            system_prompt=config.system_prompt,
        )

    def initial_state(self) -> CentipedeState:
        return CentipedeState(
            step=1,
            current_player="A",
            phase="awaiting_action",
            pot_a=self.initial_pot_a,
            pot_b=self.initial_pot_b,
            history=[],
            total_scores={"A": 0.0, "B": 0.0},
            game_ended_by=None,
        )

    def state_from_dict(self, d: dict) -> CentipedeState:
        return CentipedeState(**d)

    def validate_action(self, action) -> bool:
        return isinstance(action, str) and action.lower() in VALID_ACTIONS

    def validate_player_action(self, state: CentipedeState, player: str, action) -> bool:
        if state.phase == "complete":
            raise ValueError("game is already complete")
        if player not in ("A", "B"):
            raise ValueError(f"unknown player: {player!r}")
        if player != state.current_player:
            raise ValueError(f"it is {state.current_player}'s turn, not {player}'s")
        if not self.validate_action(action):
            raise ValueError(f"invalid action {action!r}; must be 'take' or 'pass'")
        return True

    def apply_action(self, state: CentipedeState, player: str, action: str) -> CentipedeState:
        self.validate_player_action(state, player, action)
        state = deepcopy(state)
        action = action.lower()

        entry = {
            "step":           state.step,
            "player":         player,
            "action":         action,
            "pot_a_before":   state.pot_a,
            "pot_b_before":   state.pot_b,
        }

        if action == "take":
            # Standard centipede: taker gets the larger pot, other gets smaller
            # When A takes: A gets pot_a (larger), B gets pot_b (smaller)
            # When B takes: B gets pot_a (larger), A gets pot_b (smaller)
            if player == "A":
                payoff_a = state.pot_a
                payoff_b = state.pot_b
            else:
                payoff_a = state.pot_b
                payoff_b = state.pot_a
            state.total_scores["A"] = payoff_a
            state.total_scores["B"] = payoff_b
            state.game_ended_by = player
            entry["payoffs"] = {"A": payoff_a, "B": payoff_b}
            entry["total_scores"] = dict(state.total_scores)
            state.history.append(entry)
            state.phase = "complete"

        else:  # pass
            state.pot_a *= self.growth_factor
            state.pot_b *= self.growth_factor
            entry["pot_a_after"] = state.pot_a
            entry["pot_b_after"] = state.pot_b
            state.history.append(entry)

            if state.step >= self.max_steps:
                # Forced payout
                state.total_scores["A"] = state.pot_a
                state.total_scores["B"] = state.pot_b
                state.game_ended_by = "forced"
                state.history[-1]["payoffs"] = dict(state.total_scores)
                state.history[-1]["total_scores"] = dict(state.total_scores)
                state.phase = "complete"
            else:
                state.step += 1
                state.current_player = "B" if player == "A" else "A"

        return state

    def is_terminal(self, state: CentipedeState) -> bool:
        return state.phase == "complete"

    def compute_results(
        self,
        state: CentipedeState,
        session_id: str | None = None,
        config_hash: str | None = None,
    ) -> dict:
        if not self.is_terminal(state):
            raise ValueError("game is not complete")
        sa, sb = state.total_scores["A"], state.total_scores["B"]
        winner = "A" if sa > sb else ("B" if sb > sa else "Tie")
        result = {
            "total_scores":    dict(state.total_scores),
            "winner":          winner,
            "steps_played":    len([e for e in state.history if e.get("action") == "take" or e.get("action") == "pass"]),
            "game_ended_by":   state.game_ended_by,
            "history":         list(state.history),
            "metrics":         self.metrics_engine.compute(state.history, state.total_scores),
        }
        if session_id:
            result["session_id"] = session_id
        if config_hash:
            result["config_hash"] = config_hash
        return result

    def public_state(
        self,
        state: CentipedeState,
        config,
        session_id: str,
        config_hash: str,
    ) -> dict:
        return {
            "session_id":      session_id,
            "config_hash":     config_hash,
            "step":            state.step,
            "max_steps":       self.max_steps,
            "phase":           state.phase,
            "current_player":  state.current_player,
            "awaiting":        [state.current_player] if state.phase != "complete" else [],
            "pot_a":           state.pot_a,
            "pot_b":           state.pot_b,
            "total_scores":    dict(state.total_scores),
            "history":         list(state.history),
            "game_ended_by":   state.game_ended_by,
            "messages": self.communication_log(state),
            "communication_config": self.communication_config().to_dict(),
            "system_prompt":   self._system_prompt,
        }
