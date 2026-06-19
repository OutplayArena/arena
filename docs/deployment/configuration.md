# Configuration Reference

Complete reference for all OutplayLabs Arena environment variables.

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://outplaylabs-arena:outplaylabs-arena@localhost:5432/outplaylabs-arena` | PostgreSQL connection string |

## API

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PREFIX` | `/api` | API route prefix |
| `ENABLE_AGENT_REST_API` | `false` | Allow external REST API access to game endpoints |

## MCP

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_RUNTIME` | `auto` | Runtime environment: `auto`, `docker`, `k8s` |
| `MCP_BACKEND_URL` | — | Backend URL for MCP servers to connect to |
| `MCP_DOCKER_NETWORK` | `outplaylabs-arena_mcp` | Docker network for MCP containers |
| `MCP_NAMESPACE` | `outplaylabs-arena` | Kubernetes namespace for MCP pods |
| `MCP_IMAGE` | `outplaylabs-arena-mcp:latest` | Docker image for MCP servers |
| `MCP_MAX_CONCURRENT` | `50` | Maximum concurrent MCP servers |
| `MCP_JOB_TTL` | `300` | Seconds before completed jobs are cleaned up |
| `MCP_PORT` | `8001` | Port MCP servers listen on |
| `MCP_EXPOSE_PORTS` | `false` | Expose MCP ports to host (Docker only) |
| `MCP_PUBLIC_BASE_URL` | — | Public base URL for MCP gateway |
| `MCP_ALLOWED_IPS` | `127.0.0.1` | Comma-separated IPs allowed for MCP access |

## OAuth

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_CLIENT_ID` | — | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | — | GitHub OAuth app client secret |
| `GOOGLE_CLIENT_ID` | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth client secret |
| `JWT_SECRET` | — | JWT signing secret (generate with `openssl rand -hex 32`) |
| `OAUTH_CALLBACK_BASE_URL` | `http://127.0.0.1:8000` | Base URL for OAuth callbacks |

## W&B Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPLAYLABS_ARENA_WANDB_ENCRYPTION_KEY` | — | 32-byte hex encryption key for W&B API keys |

## Internal

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPLAYLABS_ARENA_INTERNAL_API_TOKEN` | — | Internal API token for admin operations |

## Generating Secrets

### JWT Secret

```bash
openssl rand -hex 32
```

### W&B Encryption Key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Internal API Token

```bash
openssl rand -hex 32
```

## Configuration by Deployment

### Local Development

```bash
DATABASE_URL=postgresql+asyncpg://outplaylabs-arena:outplaylabs-arena@localhost:5432/outplaylabs-arena
API_PREFIX=/api
ENABLE_AGENT_REST_API=true  # For testing
MCP_RUNTIME=docker
MCP_BACKEND_URL=http://localhost:8000/api
MCP_EXPOSE_PORTS=true
MCP_PUBLIC_BASE_URL=http://localhost
```

### Docker Compose

```bash
DATABASE_URL=postgresql+asyncpg://outplaylabs-arena:outplaylabs-arena@db:5432/outplaylabs-arena
API_PREFIX=/api
ENABLE_AGENT_REST_API=false
MCP_RUNTIME=docker
MCP_BACKEND_URL=http://backend:8000/api
MCP_DOCKER_NETWORK=outplaylabs-arena_mcp
MCP_IMAGE=outplaylabs-arena-mcp:latest
MCP_EXPOSE_PORTS=true
MCP_PUBLIC_BASE_URL=http://localhost
MCP_ALLOWED_IPS=127.0.0.1,172.0.0.0/8
```

### Kubernetes

```bash
DATABASE_URL=postgresql+asyncpg://outplaylabs-arena:outplaylabs-arena@outplaylabs-arena-db:5432/outplaylabs-arena
API_PREFIX=/api
ENABLE_AGENT_REST_API=false
MCP_RUNTIME=k8s
MCP_BACKEND_URL=http://outplaylabs-arena-backend:8000/api
MCP_NAMESPACE=outplaylabs-arena
MCP_IMAGE=your-registry/outplaylabs-arena-mcp:latest
MCP_PUBLIC_BASE_URL=https://api.agent-arena.local
MCP_ALLOWED_IPS=10.0.0.0/8
```

## OAuth Setup

### GitHub

1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Create new OAuth app
3. Set callback URL: `https://agent-arena.local/api/auth/github/callback`
4. Copy Client ID and Client Secret

### Google

1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID
3. Set authorized redirect URI: `https://agent-arena.local/api/auth/google/callback`
4. Copy Client ID and Client Secret

## Security Best Practices

1. **Never commit secrets** — Use environment variables or secret managers
2. **Rotate secrets regularly** — JWT secret, OAuth secrets, API keys
3. **Use strong secrets** — At least 32 bytes of randomness
4. **Restrict MCP IPs** — Only allow trusted MCP server IPs
5. **Use HTTPS** — Always use TLS in production
6. **Disable REST API** — Keep `ENABLE_AGENT_REST_API=false` unless needed
7. **Monitor access** — Check API key usage and MCP access logs
