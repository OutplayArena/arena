from abc import ABC, abstractmethod
from typing import Any

from nash_arena.game_components.communication import (
    CommunicationConfig,
    PlayerMessage,
)


class GameEngine(ABC):
    """Base contract every arena game engine must implement."""

    @abstractmethod
    def initial_state(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def validate_action(self, action: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def validate_player_action(self, state: Any, player: str, action: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def apply_action(self, state: Any, player: str, action: Any) -> Any:
        raise NotImplementedError

    @abstractmethod
    def is_terminal(self, state: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def compute_results(
        self,
        state: Any,
        session_id: str | None = None,
        config_hash: str | None = None,
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def public_state(
        self,
        state: Any,
        config: Any,
        session_id: str,
        config_hash: str,
    ) -> dict:
        raise NotImplementedError

    # Player communication 
    def communication_config(self) -> CommunicationConfig:
        return CommunicationConfig.default()

    def validate_communication(
        self,
        state: Any,
        from_player: str,
        to_player: str | None,
        content: str,
    ) -> bool:
        comm_config = self.communication_config()
        if not comm_config.enabled:
            raise ValueError("communication is not enabled for this game")
        if self.is_terminal(state):
            raise ValueError("game is already complete")
        if to_player is not None and to_player == from_player:
            raise ValueError("cannot send a message to yourself")

        messages = self._get_messages(state)
        round_msgs = [m for m in messages if m.round_number == self._get_round(state)]
        player_round_msgs = [m for m in round_msgs if m.from_player == from_player]
        if len(player_round_msgs) >= comm_config.max_messages_per_round:
            raise ValueError(
                f"player {from_player} has already sent "
                f"{comm_config.max_messages_per_round} messages this round"
            )
        if len(content) > comm_config.max_message_length:
            raise ValueError(
                f"message exceeds max length of {comm_config.max_message_length}"
            )

        allowed_players = self._get_players(state)
        if from_player not in allowed_players:
            raise ValueError(f"unknown player: {from_player}")
        if to_player is not None and to_player not in allowed_players:
            raise ValueError(f"unknown target player: {to_player}")

        if comm_config.mode == "direct" and to_player is None:
            raise ValueError("only direct messages are allowed in this game")
        if comm_config.mode == "broadcast" and to_player is not None:
            raise ValueError("only broadcast messages are allowed in this game")

        return True

    def apply_communication(
        self,
        state: Any,
        from_player: str,
        to_player: str | None,
        content: str,
    ) -> Any:
        self.validate_communication(state, from_player, to_player, content)
        message = PlayerMessage(
            from_player=from_player,
            to_player=to_player,
            content=content,
            round_number=self._get_round(state),
        )
        self._add_message(state, message)
        return state

    def communication_log(
        self,
        state: Any,
        player: str | None = None,
    ) -> list[dict]:
        messages = self._get_messages(state)
        if player is not None:
            messages = [
                m
                for m in messages
                if m.from_player == player or m.to_player is None or m.to_player == player
            ]
        return [m.to_dict() for m in messages]

    # Internal helpers for state access
    def _get_messages(self, state: Any) -> list[PlayerMessage]:
        return getattr(state, "messages", [])

    def _add_message(self, state: Any, message: PlayerMessage) -> None:
        if not hasattr(state, "messages"):
            state.messages = []
        state.messages.append(message)

    def _get_round(self, state: Any) -> int:
        return getattr(state, "round_number", 0)

    def _get_players(self, state: Any) -> list[str]:
        scores = getattr(state, "total_scores", {})
        return list(scores.keys())
