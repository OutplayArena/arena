from dataclasses import dataclass, field

from nash_arena.game_engine import GameEngine
from nash_arena.game_components.communication import (
    CommunicationConfig,
    PlayerMessage,
)


@dataclass
class ExampleState:
    round_number: int = 1
    phase: str = "awaiting_action"
    awaiting: list[str] = field(default_factory=lambda: ["A", "B"])
    history: list[dict] = field(default_factory=list)
    total_scores: dict[str, float] = field(default_factory=lambda: {"A": 0, "B": 0})
    messages: list[PlayerMessage] = field(default_factory=list)


class ExampleGame(GameEngine):
    def initial_state(self):
        return ExampleState()

    def communication_config(self) -> CommunicationConfig:
        return CommunicationConfig(
            enabled=True,
            mode="both",
            max_messages_per_round=3,
            max_message_length=500,
        )

    def validate_action(self, action):
        return action is not None

    def validate_player_action(self, state, player, action):
        if player not in state.awaiting:
            raise ValueError(f"player {player} is not awaiting action")
        if not self.validate_action(action):
            raise ValueError(f"invalid action: {action}")
        return True

    def apply_action(self, state, player, action):
        raise NotImplementedError("Implement game-specific transition logic")

    def is_terminal(self, state):
        return state.phase == "complete"

    def compute_results(self, state, session_id=None, config_hash=None):
        raise NotImplementedError("Implement game-specific results")

    def public_state(self, state, config, session_id, config_hash):
        raise NotImplementedError("Implement game-specific public state")
