from typing import Protocol
from dataclasses import dataclass, field


@dataclass
class ContainerInfo:
    container_name: str
    dns_name: str
    port: int
    public_url: str | None = field(default=None)


class ContainerRuntime(Protocol):
    async def spawn(
        self,
        container_name: str,
        mcp_auth_key: str,
        backend_url: str,
        session_key: str,
        image: str,
        port: int = 8001,
    ) -> ContainerInfo:
        """Spawn a new MCP container and return its connection info."""
        ...

    async def stop(self, container_name: str) -> None:
        """Stop and remove a container."""
        ...

    async def is_running(self, container_name: str) -> bool:
        """Check if a container is currently running."""
        ...
