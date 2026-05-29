from abc import ABC, abstractmethod
from typing import Any


class GameMetrics(ABC):
    """Base contract every arena game metrics implementation must implement."""

    @abstractmethod
    def compute(self, history: list[dict], total_scores: dict[str, Any]) -> dict:
        raise NotImplementedError
