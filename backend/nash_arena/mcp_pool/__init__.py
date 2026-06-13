import os
import logging

from .runtime import ContainerRuntime, ContainerInfo
from .kubernetes_runtime import KubernetesRuntime
from .docker_runtime import DockerRuntime
from .manager import PoolManager

logger = logging.getLogger(__name__)


def create_runtime() -> ContainerRuntime:
    """Create the appropriate container runtime based on environment."""
    runtime_type = os.environ.get("MCP_RUNTIME", "auto").lower()

    if runtime_type == "k8s":
        namespace = os.environ.get("MCP_NAMESPACE", "nasharena")
        public_base_url = os.environ.get("MCP_PUBLIC_BASE_URL")
        return KubernetesRuntime(namespace=namespace, public_base_url=public_base_url)

    if runtime_type == "docker":
        network = os.environ.get("MCP_DOCKER_NETWORK", "nasharena_default")
        expose_ports = os.environ.get("MCP_EXPOSE_PORTS", "false").lower() == "true"
        public_base_url = os.environ.get("MCP_PUBLIC_BASE_URL")
        return DockerRuntime(network=network, expose_ports=expose_ports, public_base_url=public_base_url)

    if runtime_type == "auto":
        if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
            namespace = os.environ.get("MCP_NAMESPACE", "nasharena")
            public_base_url = os.environ.get("MCP_PUBLIC_BASE_URL")
            logger.info("Auto-detected Kubernetes environment")
            return KubernetesRuntime(namespace=namespace, public_base_url=public_base_url)
        else:
            network = os.environ.get("MCP_DOCKER_NETWORK", "nasharena_default")
            expose_ports = os.environ.get("MCP_EXPOSE_PORTS", "false").lower() == "true"
            public_base_url = os.environ.get("MCP_PUBLIC_BASE_URL")
            logger.info("Auto-detected Docker environment")
            return DockerRuntime(network=network, expose_ports=expose_ports, public_base_url=public_base_url)

    raise ValueError(f"Unknown MCP_RUNTIME: {runtime_type}")


def create_pool_manager() -> PoolManager:
    """Create a PoolManager with the appropriate runtime."""
    runtime = create_runtime()

    return PoolManager(
        runtime=runtime,
        max_concurrent=int(os.environ.get("MCP_MAX_CONCURRENT", "50")),
        job_ttl=int(os.environ.get("MCP_JOB_TTL", "300")),
        backend_url=os.environ.get("MCP_BACKEND_URL", "http://localhost:8000/api"),
        image=os.environ.get("MCP_IMAGE", "nasharena-mcp:latest"),
        port=int(os.environ.get("MCP_PORT", "8000")),
    )


__all__ = [
    "ContainerRuntime",
    "ContainerInfo",
    "KubernetesRuntime",
    "DockerRuntime",
    "PoolManager",
    "create_runtime",
    "create_pool_manager",
]
