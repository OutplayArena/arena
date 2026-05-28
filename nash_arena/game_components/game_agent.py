from abc import ABC, abstractmethod
from typing import Any


class GameAgent(ABC):
    """Base contract every arena game agent must implement."""

    @abstractmethod
    def act(self, history: list[dict]) -> Any:
        raise NotImplementedError
