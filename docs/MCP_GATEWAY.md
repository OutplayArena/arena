# MCP Gateway Architecture

This document describes the MCP (Model Context Protocol) gateway architecture that enables external users and agents to connect to MCP servers via stable, user-friendly URLs.

## Overview

The MCP gateway provides a seamless experience for users connecting to MCP servers, regardless of whether they're running in Docker or Kubernetes environments. Instead of exposing random ports or requiring users to know internal DNS names, the gateway provides stable URLs like:

- **Docker**: `http://localhost:<port>/mcp/<container-name>`
- **Kubernetes**: `https://api.agent-arena.local/mcp/<pod-name>`

## Architecture

### Docker Environment

1. **Container Creation**: When an experiment is created, the backend spawns an MCP container with:
   - Traefik labels for routing
   - `StripPrefix` middleware to remove the `/mcp/<container-name>` prefix
   - Random port mapping to the host

2. **Routing**: Traefik automatically discovers the container and creates a route based on the labels:
   ```
   PathPrefix(`/mcp/<container-name>`) -> StripPrefix -> Container:8000
   ```

3. **URL Generation**: The backend returns `http://localhost:<port>/mcp/<container-name>` in the experiment response.

### Kubernetes Environment

1. **Pod Creation**: When an experiment is created, the backend spawns an MCP pod with:
   - A Service (ClusterIP) targeting the pod
   - An individual Ingress resource with path-based routing
   - `MCP_MOUNT_PATH` environment variable for proper endpoint URLs

2. **Routing**: Traefik Ingress Controller routes based on the Ingress resource:
   ```
   Host: api.agent-arena.local
   Path: /mcp/<pod-name>
   Middleware: StripPrefixRegex (removes /mcp/<pod-name>)
   Backend: Service -> Pod:8000
   ```

3. **URL Generation**: The backend returns `https://api.agent-arena.local/mcp/<pod-name>` in the experiment response.

## Configuration

### Docker

Set the following environment variables in the backend:

```bash
MCP_EXPOSE_PORTS=true           # Enable port exposure to host
MCP_PUBLIC_BASE_URL=http://localhost  # Base URL for gateway routing
```

### Kubernetes

Set the following in `values.yaml`:

```yaml
mcpServer:
  publicBaseUrl: "https://api.agent-arena.local"
```

The Helm chart will automatically:
- Create the `strip-mcp-prefix` Middleware
- Configure the backend with `MCP_PUBLIC_BASE_URL`

## User Experience

### For External Users

Users receive a stable URL in the experiment response:

```json
{
  "session_id": "...",
  "player_tokens": {...},
  "mcp_url": "https://api.agent-arena.local/mcp/mcp-abc123"
}
```

They can connect to this URL using any MCP client:

```python
from nash_arena_sdk import MCPClient

client = MCPClient("https://api.agent-arena.local/mcp/mcp-abc123")
client.connect()
games = client.list_games()
```

### For SDK Users

The SDK automatically handles the connection:

```python
from nash_arena_sdk import MCPAgent

# Agent automatically connects to the MCP URL
agent = MCPAgent(
    player_token="nks_...",
    mcp_url="https://api.agent-arena.local/mcp/mcp-abc123"
)

# All operations go through MCP
state = agent.get_game_state()
obs = agent.get_observation()
agent.submit_action([20, 20, 20, 20, 20])
```

## Implementation Details

### Docker Runtime (`docker_runtime.py`)

- Adds Traefik labels to each container
- Uses `StripPrefix` middleware to remove the path prefix
- Exposes random ports to the host
- Returns `public_url` in `ContainerInfo`

### Kubernetes Runtime (`kubernetes_runtime.py`)

- Creates a Service for each MCP pod
- Creates an individual Ingress resource per pod
- Uses `StripPrefixRegex` middleware (regex: `^/mcp/[^/]+`)
- Sets `MCP_MOUNT_PATH` environment variable
- Cleans up Service and Ingress on pod deletion

### Backend Integration (`main.py`)

- Calls `POOL_MANAGER.assign_container()` on experiment creation
- Returns `public_url` if available, otherwise falls back to direct access
- Handles cleanup on experiment completion

## Security

- Each MCP container/pod has its own auth key (`MCP_AUTH_KEY`)
- The key is required for all backend API calls from the MCP server
- Keys are revoked when containers are stopped
- IP allowlist (`MCP_ALLOWED_IPS`) restricts backend access

## Limitations

### Docker

- Requires Traefik to be running and properly configured
- Random port allocation may be blocked by firewalls
- Not suitable for production without proper TLS termination

### Kubernetes

- Requires Traefik Ingress Controller
- Each MCP pod creates additional K8s resources (Service, Ingress)
- May hit resource limits with many concurrent experiments

## Future Improvements

1. **Connection Pooling**: Reuse MCP containers across experiments
2. **WebSocket Support**: For real-time game updates
3. **Load Balancing**: Distribute MCP servers across nodes
4. **Metrics**: Track MCP server usage and performance
5. **Auto-scaling**: Dynamically adjust pool size based on demand

## Testing

### Docker

```bash
# Start the stack
cd backend/docker
docker compose up -d

# Create an experiment
curl -X POST http://localhost/api/experiment \
  -H "Authorization: Bearer nka_..." \
  -H "Content-Type: application/json" \
  -d '{"game": "ultimatum", ...}'

# Use the returned mcp_url
python -c "
from nash_arena_sdk import MCPClient
client = MCPClient('http://localhost:32779/mcp/mcp-abc123')
client.connect()
print(client.list_games())
"
```

### Kubernetes

```bash
# Deploy with Helm
helm upgrade --install nasharena helm/nash_arena \
  --set mcpServer.publicBaseUrl=https://api.agent-arena.local

# Create an experiment
curl -X POST https://api.agent-arena.local/api/experiment \
  -H "Authorization: Bearer nka_..." \
  -H "Content-Type: application/json" \
  -d '{"game": "ultimatum", ...}'

# Use the returned mcp_url
python -c "
from nash_arena_sdk import MCPClient
client = MCPClient('https://api.agent-arena.local/mcp/mcp-abc123')
client.connect()
print(client.list_games())
"
```

## Troubleshooting

### Docker

- **404 on MCP URL**: Check that Traefik is running and the container has the correct labels
- **Connection refused**: Verify the port is exposed and not blocked by firewall
- **Auth errors**: Ensure `MCP_AUTH_KEY` is set in the container environment

### Kubernetes

- **404 on MCP URL**: Check that the Ingress resource exists and Traefik is configured
- **503 Service Unavailable**: Verify the Service exists and the pod is running
- **Auth errors**: Check that `MCP_AUTH_KEY` is set and the key is valid in the database

## Related Files

- `backend/nash_arena/mcp_pool/docker_runtime.py`
- `backend/nash_arena/mcp_pool/kubernetes_runtime.py`
- `backend/nash_arena/mcp_pool/manager.py`
- `backend/nash_arena/main.py`
- `helm/nash_arena/templates/mcp-server/ingress.yaml`
- `helm/nash_arena/templates/backend/configmap.yaml`
- `agent-sdk/src/nash_arena_sdk/mcp_client.py`
- `agent-sdk/src/nash_arena_sdk/agent.py`
