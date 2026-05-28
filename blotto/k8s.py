import asyncio
import os
import uuid

MCP_IMAGE = os.environ.get("MCP_IMAGE", "blotto-mcp:latest")
MCP_NAMESPACE = os.environ.get("MCP_NAMESPACE", "default")
MCP_PORT = 8001


class MCPOrchestrator:
    async def start_mcp_server(
        self, session_id: str, player: str, base_url: str, token: str
    ) -> str:
        """Start an MCP server and return the pod IP."""
        raise NotImplementedError

    async def stop_mcp_server(self, session_id: str, player: str):
        """Stop an MCP server."""
        raise NotImplementedError


class LocalMCPOrchestrator(MCPOrchestrator):
    def __init__(self):
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def start_mcp_server(
        self, session_id: str, player: str, base_url: str, token: str
    ) -> str:
        key = f"{session_id}_{player}"
        port = self._pick_port(key)

        env = os.environ.copy()
        env.update({
            "FASTMCP_HOST": "127.0.0.1",
            "FASTMCP_PORT": str(port),
            "FASTMCP_LOG_LEVEL": "ERROR",
            "MCP_TRANSPORT": "sse",
            "MCP_MOUNT_PATH": "/",
            "ARENA_BASE_URL": base_url,
            "ARENA_SESSION_ID": session_id,
            "ARENA_SESSION_TOKEN": token,
        })

        proc = await asyncio.create_subprocess_exec(
            "python3", "-m", "blotto.mcp_server",
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._processes[key] = proc
        await asyncio.sleep(1)
        return f"http://127.0.0.1:{port}"

    async def stop_mcp_server(self, session_id: str, player: str):
        key = f"{session_id}_{player}"
        proc = self._processes.pop(key, None)
        if proc:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()

    def _pick_port(self, key: str) -> int:
        base = 9000 + (hash(key) % 1000)
        return base


class KubernetesMCPOrchestrator(MCPOrchestrator):
    def __init__(self):
        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        self.batch = client.BatchV1Api()
        self.core = client.CoreV1Api()
        self.namespace = MCP_NAMESPACE
        self.image = MCP_IMAGE
        self._store: dict[str, dict] = {}

    async def start_mcp_server(
        self, session_id: str, player: str, base_url: str, token: str
    ) -> str:
        from kubernetes import client

        key = f"{session_id}_{player}"
        job_name = f"mcp-{session_id[:8]}-{player.lower()}"

        job = client.V1Job(
            metadata=client.V1ObjectMeta(name=job_name, labels={
                "app": "blotto-mcp",
                "session_id": session_id,
                "player": player,
            }),
            spec=client.V1JobSpec(
                ttl_seconds_after_finished=300,
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={
                        "app": "blotto-mcp",
                        "session_id": session_id,
                        "player": player,
                    }),
                    spec=client.V1PodSpec(
                        restart_policy="Never",
                        containers=[
                            client.V1Container(
                                name="mcp",
                                image=self.image,
                                image_pull_policy="Never",
                                env=[
                                    client.V1EnvVar(name="FASTMCP_HOST", value="0.0.0.0"),
                                    client.V1EnvVar(name="FASTMCP_PORT", value=str(MCP_PORT)),
                                    client.V1EnvVar(name="FASTMCP_LOG_LEVEL", value="INFO"),
                                    client.V1EnvVar(name="MCP_TRANSPORT", value="sse"),
                                    client.V1EnvVar(name="MCP_MOUNT_PATH", value="/"),
                                    client.V1EnvVar(name="ARENA_BASE_URL", value=base_url),
                                    client.V1EnvVar(name="ARENA_SESSION_ID", value=session_id),
                                    client.V1EnvVar(name="ARENA_SESSION_TOKEN", value=token),
                                ],
                                ports=[client.V1ContainerPort(container_port=MCP_PORT)],
                            )
                        ],
                    ),
                ),
            ),
        )

        created = self.batch.create_namespaced_job(self.namespace, job)

        self._store[key] = {
            "job_name": job_name,
            "pod_ip": None,
        }

        pod_ip = await self._wait_for_pod_ip(key, job_name)
        return pod_ip

    async def stop_mcp_server(self, session_id: str, player: str):
        from kubernetes import client

        key = f"{session_id}_{player}"
        info = self._store.pop(key, None)
        if not info:
            return
        try:
            self.batch.delete_namespaced_job(
                info["job_name"], self.namespace,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
        except Exception:
            pass

    async def _wait_for_pod_ip(self, key: str, job_name: str, timeout: float = 30) -> str:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            pods = self.core.list_namespaced_pod(
                self.namespace,
                label_selector=f"app=blotto-mcp,job-name={job_name}",
            )
            for pod in pods.items:
                if pod.status.pod_ip and pod.status.phase == "Running":
                    self._store[key]["pod_ip"] = pod.status.pod_ip
                    return pod.status.pod_ip
            await asyncio.sleep(0.5)
        raise TimeoutError(f"MCP pod for job {job_name} did not become ready")


def get_orchestrator() -> MCPOrchestrator:
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return KubernetesMCPOrchestrator()
    return LocalMCPOrchestrator()
