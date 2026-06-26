# MCP Gateway

The MCP gateway provides stable URLs for connecting to MCP servers in Docker and Kubernetes environments.

## Overview

Instead of exposing random ports or requiring knowledge of internal DNS names, the gateway provides stable URLs:

- **Docker**: `http://localhost:<port>/mcp/<container-name>`
- **Kubernetes**: `https://api.agent-arena.local/mcp/<pod-name>`

## Docker Environment

### Architecture

1. **Container Creation**: Backend spawns MCP container with Traefik labels
2. **Routing**: Traefik discovers container and creates route
3. **URL Generation**: Backend returns `http://localhost:<port>/mcp/<container-name>`

### Configuration

```bash
MCP_EXPOSE_PORTS=true
MCP_PUBLIC_BASE_URL=http://localhost
```

### Traefik Labels

Each container gets labels:

```
traefik.enable=true
traefik.http.routers.mcp-<id>.rule=PathPrefix(`/mcp/<container-name>`)
traefik.http.middlewares.strip-mcp.stripprefix.prefixes=/mcp/<container-name>
```

## Kubernetes Environment

### Architecture

1. **Pod Creation**: Backend spawns MCP pod with Service and Ingress
2. **Routing**: Traefik Ingress Controller routes based on Ingress resource
3. **URL Generation**: Backend returns `https://api.agent-arena.local/mcp/<pod-name>`

### Configuration

```yaml
# values.yaml
mcpServer:
  publicBaseUrl: "https://api.agent-arena.local"
```

### Resources Created

Per MCP pod:
- Pod (MCP server)
- Service (ClusterIP)
- Ingress (path-based routing)

## User Experience

### Experiment Response

```json
{
  "session_id": "...",
  "player_tokens": {...},
  "mcp_url": "https://api.agent-arena.local/mcp/mcp-abc123"
}
```

### Connecting

```python
from outplayarena_sdk import MCPClient

client = MCPClient("https://api.agent-arena.local/mcp/mcp-abc123")
client.connect()
games = client.list_games()
```

### SDK Integration

```python
from outplayarena_sdk import MCPAgent

agent = MCPAgent(
    player_token="nks_...",
    mcp_url="https://api.agent-arena.local/mcp/mcp-abc123"
)

state = agent.get_game_state()
obs = agent.get_observation()
agent.submit_action([20, 20, 20, 20, 20])
```

## Implementation Details

### Docker Runtime

- Adds Traefik labels to each container
- Uses `StripPrefix` middleware
- Exposes random ports to host
- Returns `public_url` in `ContainerInfo`

### Kubernetes Runtime

- Creates Service for each MCP pod
- Creates individual Ingress per pod
- Uses `StripPrefixRegex` middleware
- Sets `MCP_MOUNT_PATH` environment variable
- Cleans up resources on pod deletion

## Security

- Each MCP container/pod has its own auth key
- Key required for all backend API calls
- Keys revoked when containers stopped
- IP allowlist restricts backend access

## Troubleshooting

### Docker

| Issue | Solution |
|-------|----------|
| 404 on MCP URL | Check Traefik is running, container has correct labels |
| Connection refused | Verify port is exposed, not blocked by firewall |
| Auth errors | Ensure `MCP_AUTH_KEY` is set in container |

### Kubernetes

| Issue | Solution |
|-------|----------|
| 404 on MCP URL | Check Ingress resource exists, Traefik configured |
| 503 Service Unavailable | Verify Service exists, pod is running |
| Auth errors | Check `MCP_AUTH_KEY` is valid in database |

## Testing

### Docker

```bash
cd backend/docker && docker compose up -d

# Create experiment
curl -X POST http://localhost/api/experiment \
  -H "Authorization: Bearer nka_..." \
  -H "Content-Type: application/json" \
  -d '{"game": "ultimatum", ...}'

# Use returned mcp_url
python -c "
from outplayarena_sdk import MCPClient
client = MCPClient('http://localhost:32779/mcp/mcp-abc123')
client.connect()
print(client.list_games())
"
```

### Kubernetes

```bash
helm upgrade --install outplayarena helm/arena \
  --set mcpServer.publicBaseUrl=https://api.agent-arena.local

# Create experiment and use returned mcp_url
```

## Related Files

- `backend/arena/mcp_pool/docker_runtime.py`
- `backend/arena/mcp_pool/kubernetes_runtime.py`
- `backend/arena/mcp_pool/manager.py`
- `helm/arena/templates/mcp-server/ingress.yaml`
- `agent-sdk/src/outplayarena_sdk/mcp_client.py`
