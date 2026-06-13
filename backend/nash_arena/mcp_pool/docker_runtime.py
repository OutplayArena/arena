import logging
import docker
from docker.errors import NotFound, APIError

from .runtime import ContainerInfo

logger = logging.getLogger(__name__)


class DockerRuntime:
    def __init__(
        self,
        network: str | None = None,
        expose_ports: bool = False,
        public_base_url: str | None = None,
    ):
        self.client = docker.from_env()
        self.network = network or "nasharena_default"
        self.expose_ports = expose_ports
        self.public_base_url = public_base_url

    async def spawn(
        self,
        container_name: str,
        mcp_auth_key: str,
        backend_url: str,
        session_key: str,
        image: str,
        port: int = 8000,
    ) -> ContainerInfo:
        """Spawn a Docker container running the MCP server."""
        import os
        env = {
            "NASH_ARENA_BASE_URL": backend_url,
            "NASH_ARENA_KEY": session_key,
            "MCP_AUTH_KEY": mcp_auth_key,
            "FASTMCP_PORT": str(port),
            "FASTMCP_HOST": "0.0.0.0",
            "MCP_TRANSPORT": "sse",
            "JWT_SECRET": os.environ.get("JWT_SECRET", "dev-secret-change-me"),
        }

        # Set mount path for public URL routing (only when using gateway)
        # When using exposed ports directly, no prefix is needed
        if self.public_base_url:
            mount_path = f"/mcp/{container_name}"
            env["MCP_MOUNT_PATH"] = mount_path

        try:
            self.client.networks.get(self.network)
        except NotFound:
            logger.warning(f"Network {self.network} not found, creating it")
            self.client.networks.create(self.network, driver="bridge")

        # Build container config
        kwargs = {
            "image": image,
            "name": container_name,
            "environment": env,
            "network": self.network,
            "detach": True,
            "remove": False,
        }

        # Optionally expose port to host
        if self.expose_ports:
            kwargs["ports"] = {f"{port}/tcp": None}  # Random host port

        # Add traefik labels for routing (only when using gateway)
        if self.public_base_url:
            labels = {
                "traefik.enable": "true",
                f"traefik.http.routers.{container_name}.rule": f"PathPrefix(`/mcp/{container_name}`)",
                f"traefik.http.routers.{container_name}.entrypoints": "web,websecure",
                f"traefik.http.routers.{container_name}.middlewares": f"{container_name}-stripprefix",
                f"traefik.http.middlewares.{container_name}-stripprefix.stripprefix.prefixes": f"/mcp/{container_name}",
                f"traefik.http.services.{container_name}.loadbalancer.server.port": str(port),
            }
            kwargs["labels"] = labels

        try:
            container = self.client.containers.run(**kwargs)
            logger.info(f"Created MCP container {container_name}")
        except APIError as e:
            logger.error(f"Failed to create MCP container {container_name}: {e}")
            raise

        # Get the actual port mapping if exposed
        dns_name = container_name
        actual_port = port
        public_url = None

        if self.expose_ports:
            container.reload()
            port_bindings = container.attrs["NetworkSettings"]["Ports"].get(f"{port}/tcp", [])
            if port_bindings:
                actual_port = int(port_bindings[0]["HostPort"])
                dns_name = "localhost"
                # Direct connection, no path prefix
                public_url = f"http://localhost:{actual_port}"
        elif self.public_base_url:
            # Gateway connection, use path prefix
            public_url = f"{self.public_base_url}/mcp/{container_name}"

        return ContainerInfo(
            container_name=container_name,
            dns_name=dns_name,
            port=actual_port,
            public_url=public_url,
        )

    async def stop(self, container_name: str) -> None:
        """Stop and remove a Docker container."""
        try:
            container = self.client.containers.get(container_name)
            container.stop(timeout=10)
            container.remove()
            logger.info(f"Stopped and removed MCP container {container_name}")
        except NotFound:
            logger.warning(f"MCP container {container_name} not found")
        except APIError as e:
            logger.error(f"Failed to stop MCP container {container_name}: {e}")
            raise

    async def is_running(self, container_name: str) -> bool:
        """Check if a Docker container is running."""
        try:
            container = self.client.containers.get(container_name)
            return container.status == "running"
        except NotFound:
            return False
        except APIError as e:
            logger.error(f"Failed to check container {container_name}: {e}")
            raise
