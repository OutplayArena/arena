import os
import logging
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from .runtime import ContainerInfo

logger = logging.getLogger(__name__)


class KubernetesRuntime:
    def __init__(
        self,
        namespace: str | None = None,
        public_base_url: str | None = None,
    ):
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        self.namespace = namespace or os.environ.get("MCP_NAMESPACE", "nasharena")
        self.public_base_url = public_base_url
        self.batch_v1 = client.BatchV1Api()
        self.core_v1 = client.CoreV1Api()
        self.networking_v1 = client.NetworkingV1Api()

    async def spawn(
        self,
        container_name: str,
        mcp_auth_key: str,
        backend_url: str,
        session_key: str,
        image: str,
        port: int = 8000,
    ) -> ContainerInfo:
        """Spawn a Kubernetes Job running the MCP server."""
        job_name = container_name
        hostname = container_name
        subdomain = "mcp-pool"

        env_vars = [
            client.V1EnvVar(name="NASH_ARENA_BASE_URL", value=backend_url),
            client.V1EnvVar(name="NASH_ARENA_KEY", value=session_key),
            client.V1EnvVar(name="MCP_AUTH_KEY", value=mcp_auth_key),
            client.V1EnvVar(name="FASTMCP_PORT", value=str(port)),
            client.V1EnvVar(name="FASTMCP_HOST", value="0.0.0.0"),
            client.V1EnvVar(name="MCP_TRANSPORT", value="sse"),
        ]

        # Set mount path for public URL routing (only when using gateway)
        if self.public_base_url:
            mount_path = f"/mcp/{container_name}"
            env_vars.append(client.V1EnvVar(name="MCP_MOUNT_PATH", value=mount_path))

        container = client.V1Container(
            name="mcp-server",
            image=image,
            image_pull_policy="IfNotPresent",
            ports=[client.V1ContainerPort(container_port=port)],
            env=env_vars,
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={"app": "mcp-server", "mcp-instance": container_name}
            ),
            spec=client.V1PodSpec(
                hostname=hostname,
                subdomain=subdomain,
                restart_policy="Never",
                containers=[container],
            ),
        )

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                labels={"app": "mcp-server", "mcp-instance": container_name},
            ),
            spec=client.V1JobSpec(
                template=template,
                backoff_limit=0,
                ttl_seconds_after_finished=300,
            ),
        )

        try:
            self.batch_v1.create_namespaced_job(namespace=self.namespace, body=job)
            logger.info(f"Created MCP Job {job_name} in namespace {self.namespace}")
        except ApiException as e:
            logger.error(f"Failed to create MCP Job {job_name}: {e}")
            raise

        dns_name = f"{hostname}.{subdomain}.{self.namespace}.svc.cluster.local"
        public_url = None

        # Create Service and Ingress for gateway routing
        if self.public_base_url:
            try:
                await self._create_service(container_name, port)
                await self._update_ingress(container_name, port)
                public_url = f"{self.public_base_url}/mcp/{container_name}"
                logger.info(f"Created Service and Ingress for {container_name}")
            except ApiException as e:
                logger.error(f"Failed to create Service/Ingress for {container_name}: {e}")
                # Continue anyway - direct DNS access still works

        return ContainerInfo(
            container_name=container_name,
            dns_name=dns_name,
            port=port,
            public_url=public_url,
        )

    async def stop(self, container_name: str) -> None:
        """Delete the Kubernetes Job (cascades to pod) and clean up Service/Ingress."""
        job_name = container_name
        
        # Clean up Service and Ingress first
        if self.public_base_url:
            await self._cleanup_service_and_ingress(container_name)
        
        try:
            self.batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=self.namespace,
                propagation_policy="Background",
            )
            logger.info(f"Deleted MCP Job {job_name}")
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Failed to delete MCP Job {job_name}: {e}")
                raise

    async def is_running(self, container_name: str) -> bool:
        """Check if the Job's pod is running."""
        job_name = container_name
        try:
            job = self.batch_v1.read_namespaced_job(
                name=job_name, namespace=self.namespace
            )
            return job.status.active is not None and job.status.active > 0
        except ApiException as e:
            if e.status == 404:
                return False
            raise

    async def _create_service(self, container_name: str, port: int) -> None:
        """Create a Service for the MCP pod."""
        service_name = container_name
        
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(
                name=service_name,
                labels={"app": "mcp-server", "mcp-instance": container_name},
            ),
            spec=client.V1ServiceSpec(
                selector={"app": "mcp-server", "mcp-instance": container_name},
                ports=[client.V1ServicePort(port=port, target_port=port)],
                type="ClusterIP",
            ),
        )

        try:
            self.core_v1.create_namespaced_service(
                namespace=self.namespace, body=service
            )
            logger.info(f"Created Service {service_name}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.debug(f"Service {service_name} already exists")
            else:
                raise

    async def _update_ingress(self, container_name: str, port: int) -> None:
        """Create an Ingress resource for this MCP pod."""
        ingress_name = container_name
        path = f"/mcp/{container_name}"
        
        # Extract host from public_base_url (strip port if present)
        from urllib.parse import urlparse
        parsed = urlparse(self.public_base_url)
        host_with_port = parsed.netloc
        host = host_with_port.split(":")[0]  # Remove port if present
        
        # Check if host is an IP address (Kubernetes requires DNS names for host field)
        import re
        is_ip = re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host)
        
        # Build Ingress rule - omit host if it's an IP address
        ingress_rule = client.V1IngressRule(
            http=client.V1HTTPIngressRuleValue(
                paths=[
                    client.V1HTTPIngressPath(
                        path=path,
                        path_type="Prefix",
                        backend=client.V1IngressBackend(
                            service=client.V1IngressServiceBackend(
                                name=container_name,
                                port=client.V1ServiceBackendPort(number=port),
                            )
                        ),
                    )
                ]
            )
        )
        
        # Only set host if it's not an IP address
        if not is_ip:
            ingress_rule.host = host

        ingress = client.V1Ingress(
            api_version="networking.k8s.io/v1",
            kind="Ingress",
            metadata=client.V1ObjectMeta(
                name=ingress_name,
                labels={"app": "mcp-server", "mcp-instance": container_name},
                annotations={
                    # Use regex to capture the path and strip it
                    "traefik.ingress.kubernetes.io/router.middlewares": f"{self.namespace}-strip-mcp-prefix@kubernetescrd",
                },
            ),
            spec=client.V1IngressSpec(
                ingress_class_name="traefik",
                rules=[ingress_rule]
            ),
        )

        try:
            self.networking_v1.create_namespaced_ingress(
                namespace=self.namespace, body=ingress
            )
            logger.info(f"Created Ingress {ingress_name}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.debug(f"Ingress {ingress_name} already exists")
            else:
                raise

    async def _cleanup_service_and_ingress(self, container_name: str) -> None:
        """Clean up Service and Ingress for a container."""
        # Delete Service
        try:
            self.core_v1.delete_namespaced_service(
                name=container_name, namespace=self.namespace
            )
            logger.info(f"Deleted Service {container_name}")
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Failed to delete Service {container_name}: {e}")

        # Delete Ingress
        ingress_name = container_name
        try:
            self.networking_v1.delete_namespaced_ingress(
                name=ingress_name, namespace=self.namespace
            )
            logger.info(f"Deleted Ingress {ingress_name}")
        except ApiException as e:
            if e.status != 404:
                logger.error(f"Failed to delete Ingress {ingress_name}: {e}")
