from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class MessageBroker(ABC):
    @abstractmethod
    async def publish(self, channel: str, message: dict) -> None:
        ...

    @abstractmethod
    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        ...

    @abstractmethod
    async def enqueue(self, queue: str, message: dict) -> None:
        ...

    @abstractmethod
    async def dequeue(self, queue: str, timeout: int = 5) -> dict | None:
        ...

    @abstractmethod
    async def cache_set(self, key: str, value: dict, ttl: int = 300) -> None:
        ...

    @abstractmethod
    async def cache_get(self, key: str) -> dict | None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
