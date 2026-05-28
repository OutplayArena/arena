from abc import ABC, abstractmethod
from typing import Any


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
