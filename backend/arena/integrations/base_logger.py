from abc import ABC, abstractmethod
from typing import Any


class BaseLogger(ABC):
    """Contract every results logger (W&B, TensorBoard, ...) must implement."""

    @abstractmethod
    def start(self) -> "BaseLogger":
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def log_round(self, payload: dict[str, Any], step: int) -> None:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def log_terminal(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def finish(self) -> None:
        raise NotImplementedError  # pragma: no cover
