from abc import ABC, abstractmethod
from typing import Any


class GameConfig(ABC):
    """Base contract every arena game config must implement."""

    @abstractmethod
    def player_ids(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def config_hash(self) -> str:
        raise NotImplementedError
