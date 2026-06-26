# MCP Setup

Configuration and deployment of MCP servers for OutplayArena.

## Prerequisites

- OutplayArena backend running
- Traefik (for Docker) or Traefik Ingress Controller (for Kubernetes)
- Docker or Kubernetes cluster

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_RUNTIME` | `auto` | Runtime environment: `auto`, `docker`, `k8s` |
| `MCP_BACKEND_URL` | — | Backend URL for MCP servers to connect to |
| `MCP_DOCKER_NETWORK` | `arena_default` | Docker network for MCP containers |
| `MCP_NAMESPACE` | `arena` | Kubernetes namespace for MCP pods |
| `MCP_IMAGE` | `arena-mcp:latest` | Docker image for MCP servers |
| `MCP_MAX_CONCURRENT` | `50` | Maximum concurrent MCP servers |
| `MCP_JOB_TTL` | `300` | Seconds before completed jobs are cleaned up |
| `MCP_PORT` | `8001` | Port MCP servers listen on |
| `MCP_EXPOSE_PORTS` | `false` | Expose MCP ports to host (Docker only) |
| `MCP_PUBLIC_BASE_URL` | — | Public base URL for MCP gateway |
| `MCP_ALLOWED_IPS` | `127.0.0.1` | Allowed IPs for MCP backend access |

## Docker Setup

### 1. Build MCP Image

```bash
cd backend/docker
docker build -f Dockerfile.mcp -t arena-mcp:latest .
```

### 2. Configure Backend

```bash
MCP_RUNTIME=docker
MCP_BACKEND_URL=http://backend:8000/api
MCP_DOCKER_NETWORK=arena_default
MCP_IMAGE=arena-mcp:latest
MCP_EXPOSE_PORTS=true
MCP_PUBLIC_BASE_URL=http://localhost
```

### 3. Start Stack

```bash
cd backend/docker
docker compose up -d
```

### 4. Verify

```bash
# Check MCP network exists
docker network ls | grep arena_default

# Create experiment
curl -X POST http://localhost/api/experiment \
  -H "Authorization: Bearer nk_..." \
  -H "Content-Type: application/json" \
  -d '{"game": "ultimatum", "rounds": 10}'

# Check MCP container spawned
docker ps | grep mcp
```

## Kubernetes Setup

### 1. Build and Push MCP Image

```bash
cd backend/docker
docker build -f Dockerfile.mcp -t your-registry/arena-mcp:latest .
docker push your-registry/arena-mcp:latest
```

### 2. Configure Helm

```yaml
# values.yaml
mcpServer:
  image:
    repository: your-registry/arena-mcp
    tag: latest
  port: 8000
  maxConcurrentJobs: 50
  jobTTL: 300
  publicBaseUrl: "https://api.agent-arena.local"
```

### 3. Deploy

```bash
helm upgrade --install arena helm/arena \
  --namespace arena --create-namespace \
  -f values.yaml
```

### 4. Verify

```bash
# Check MCP pods
kubectl -n arena get pods | grep mcp

# Check RBAC
kubectl -n arena get rolebindings

# Create experiment via API
curl -X POST https://api.agent-arena.local/api/experiment \
  -H "Authorization: Bearer nk_..." \
  -H "Content-Type: application/json" \
  -d '{"game": "ultimatum", "rounds": 10}'

# Check MCP pod spawned
kubectl -n arena get pods | grep mcp-
```

## MCP Server Authentication

### Creating MCP Keys

MCP keys are created programmatically:

```python
from arena.mcp_key_manager import create_mcp_key
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("postgresql://...")
Session = sessionmaker(bind=engine)
db = Session()

key_data = create_mcp_key(db)
print(key_data["key"])  # mcp_key_...
```

### Using MCP Keys

MCP servers include the key in requests:

```bash
curl http://backend:8000/api/session/SESSION_ID/state \
  -H "X-MCP-Auth-Key: mcp_key_..."
```

### IP Allowlist

Restrict MCP access to specific IPs:

```bash
MCP_ALLOWED_IPS=127.0.0.1,192.168.1.100,10.0.0.0/24
```

## MCP Server Lifecycle

1. **Experiment Created**: Backend spawns MCP server (container/pod)
2. **Server Ready**: MCP server connects to backend, registers tools
3. **Agent Connects**: Agent connects via SSE or stdio
4. **Game Plays**: Agent uses tools to interact with game
5. **Game Complete**: MCP server shuts down, resources cleaned up

## Resource Cleanup

### Docker

- Containers stopped when game completes
- Network cleaned up on stack shutdown
- Orphaned containers cleaned on backend restart

### Kubernetes

- Pods deleted when game completes
- Services and Ingress resources cleaned up
- TTL-based cleanup for stuck jobs (`MCP_JOB_TTL`)

## Monitoring

### Docker

```bash
# List MCP containers
docker ps --filter label=mcp-instance

# View logs
docker logs mcp-abc123

# Check resource usage
docker stats mcp-abc123
```

### Kubernetes

```bash
# List MCP pods
kubectl -n arena get pods -l app=mcp-server

# View logs
kubectl -n arena logs mcp-abc123

# Check resource usage
kubectl -n arena top pods -l app=mcp-server
```

## Scaling

### Docker

- Limited by host resources
- `MCP_MAX_CONCURRENT` limits parallel servers
- Consider Kubernetes for production scaling

### Kubernetes

- HPA can scale backend pods
- MCP pods are ephemeral (one per game)
- `MCP_MAX_CONCURRENT` limits parallel servers
- Node autoscaling handles resource demands

## Troubleshooting

### MCP Server Won't Start

1. Check backend URL is reachable from MCP server
2. Verify MCP auth key is valid
3. Check IP allowlist includes MCP server IP
4. Review backend logs for auth errors

### Agent Can't Connect

1. Verify MCP URL is correct
2. Check MCP server is running
3. Verify network connectivity (Docker network or K8s service)
4. Check Traefik routing (Docker) or Ingress (K8s)

### Resource Leaks

1. Check `MCP_JOB_TTL` is set (K8s)
2. Review orphaned containers: `docker ps -a --filter label=mcp-instance`
3. Review orphaned pods: `kubectl get pods --field-selector=status.phase!=Running`
4. Clean up manually if needed

## Next Steps

- [MCP Overview](overview.md) — Architecture and concepts
- [MCP Gateway](gateway.md) — URL routing details
- [Deployment](../deployment/docker.md) — Full stack deployment
