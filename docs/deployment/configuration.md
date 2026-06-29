# Environment Configuration

All configuration is via environment variables. Copy the appropriate template to `.env` and fill in the values before starting any service.

- **Development:** `.env.example` in the repository root
- **Production:** `deploy/.env.production.example`

---

## Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes (dev) | `postgresql+asyncpg://outplayarena:outplayarena@localhost:5432/outplayarena` | Full PostgreSQL connection string (dev only — in production, set via `POSTGRES_*` vars) |
| `POSTGRES_USER` | Yes (prod) | — | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes (prod) | — | PostgreSQL password — **minimum 32 characters** |
| `POSTGRES_DB` | Yes (prod) | — | PostgreSQL database name |

!!! warning "Production database"
    In the production Docker Compose setup, `DATABASE_URL` is constructed automatically from `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`. Do not set `DATABASE_URL` directly when using the production compose file.

## Redis

| Variable | Required | Default | Description |
|---|---|---|---|
| `REDIS_URL` | Yes (dev) | `redis://localhost:6379/0` | Redis connection string (dev only — in prod, set via `REDIS_PASSWORD`) |
| `REDIS_PASSWORD` | Yes (prod) | — | Redis password — **minimum 32 characters** |

## API

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_PREFIX` | No | `/api` | Path prefix for all API routes |
| `ENABLE_AGENT_REST_API` | No | `false` | Allow agents to call game endpoints directly via REST. In production, keep `false` — only MCP servers should access game endpoints |
| `CORS_ALLOW_ORIGINS` | Yes (prod) | `*` | Comma-separated allowed CORS origins. Set to your domain in production (e.g. `https://arena.example.com`) |

!!! danger "CORS in production"
    `CORS_ALLOW_ORIGINS=*` combined with credentials allows cross-site authenticated requests. Always set this to your specific domain in production.

## MCP Runtime

The backend spawns per-session MCP containers on demand. Configure the runtime to match your deployment.

| Variable | Required | Default | Description |
|---|---|---|---|
| `MCP_RUNTIME` | No | `auto` | `auto` (detect from environment), `docker`, or `k8s` |
| `MCP_BACKEND_URL` | Yes | — | URL that MCP containers use to reach the backend API (e.g. `http://backend:8000/api`) |
| `MCP_IMAGE` | No | `arena-mcp:latest` | Docker image for MCP containers |
| `MCP_MAX_CONCURRENT` | No | `50` | Maximum concurrent MCP sessions |
| `MCP_JOB_TTL` | No | `300` | Seconds before idle MCP containers are cleaned up |
| `MCP_PORT` | No | `8001` | Port MCP containers listen on internally |
| `MCP_DOCKER_NETWORK` | No | `arena_default` | Docker network name for MCP containers (Docker runtime) |
| `MCP_NAMESPACE` | No | `arena` | Kubernetes namespace for MCP pods (K8s runtime) |
| `MCP_PUBLIC_BASE_URL` | Yes | — | Public base URL for MCP connections (e.g. `https://arena.example.com`) |
| `MCP_ALLOWED_IPS` | No | `127.0.0.1` | Comma-separated IPs allowed to reach MCP containers directly |

## OAuth / Authentication

OAuth is required for user login. Configure at least one provider.

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_CLIENT_ID` | No | — | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | No | — | GitHub OAuth app client secret |
| `GOOGLE_CLIENT_ID` | No | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | — | Google OAuth client secret |
| `JWT_SECRET` | Yes | — | JWT signing secret — **minimum 64 hex characters** — generate with `openssl rand -hex 32` |
| `SESSION_KEY_SECRET` | No | — | Signs game session keys (`nks_…`) separately from JWTs. Falls back to `JWT_SECRET` when unset |
| `OAUTH_CALLBACK_BASE_URL` | No | (auto from Host header) | Base URL for OAuth callbacks. Set in production to lock to a single origin |
| `OAUTH_ALLOWED_BASES` | Yes (prod) | — | Comma-separated origins allowed as OAuth redirect_uri base (prevents Host-header injection) |

### Setting up GitHub OAuth

1. Go to [GitHub Settings → Developer settings → OAuth Apps](https://github.com/settings/developers)
2. Click **New OAuth App**
3. Set **Authorization callback URL** to `https://your-domain.com/api/auth/github/callback`
4. Copy **Client ID** and **Client Secret** to `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`

### Setting up Google OAuth

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Click **Create Credentials → OAuth 2.0 Client ID** (Web application)
3. Add `https://your-domain.com/api/auth/google/callback` as an Authorized redirect URI
4. Copy **Client ID** and **Client Secret** to `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`

## Security

| Variable | Required | Default | Description |
|---|---|---|---|
| `TRAEFIK_DASHBOARD_AUTH` | Yes (prod) | — | Basic-auth credentials for Traefik dashboard in `htpasswd` format. Generate with `htpasswd -nb admin your_password` |

## Production-Only

| Variable | Required | Default | Description |
|---|---|---|---|
| `DOMAIN` | Yes (prod) | — | Your public domain (e.g. `arena.example.com`) |
| `ACME_EMAIL` | Yes (prod) | — | Email for Let's Encrypt registration |
| `IMAGE_TAG` | Yes (prod) | `v0.1.0` | Docker image tag to pull from Docker Hub |
| `DOCKER_API_VERSION` | No | `1.55` | Docker daemon API version (set to output of `docker version`) |
| `BACKUP_DIR` | No | — | Directory for database backup rotation (leave empty to disable) |

## Generating Secrets

```bash
# JWT_SECRET / SESSION_KEY_SECRET (64 hex chars)
openssl rand -hex 32

# POSTGRES_PASSWORD / REDIS_PASSWORD (32+ chars)
openssl rand -hex 16

# TRAEFIK_DASHBOARD_AUTH
htpasswd -nb admin your_password_here
```

## Configuration by Environment

=== "Local Development"

    ```bash
    DATABASE_URL=postgresql+asyncpg://outplayarena:outplayarena@localhost:5432/outplayarena
    REDIS_URL=redis://localhost:6379/0
    API_PREFIX=/api
    ENABLE_AGENT_REST_API=true
    MCP_RUNTIME=auto
    MCP_BACKEND_URL=http://localhost:8000/api
    JWT_SECRET=dev-secret-change-me-in-production
    CORS_ALLOW_ORIGINS=*
    ```

=== "Docker Compose (production)"

    ```bash
    DOMAIN=arena.example.com
    ACME_EMAIL=ops@example.com
    IMAGE_TAG=v0.1.0
    POSTGRES_USER=outplayarena
    POSTGRES_PASSWORD=<openssl rand -hex 16>
    POSTGRES_DB=outplayarena
    REDIS_PASSWORD=<openssl rand -hex 16>
    JWT_SECRET=<openssl rand -hex 32>
    CORS_ALLOW_ORIGINS=https://arena.example.com
    OAUTH_ALLOWED_BASES=https://arena.example.com
    TRAEFIK_DASHBOARD_AUTH=admin:<htpasswd hash>
    MCP_PUBLIC_BASE_URL=https://arena.example.com
    ```

=== "Kubernetes"

    ```bash
    DATABASE_URL=postgresql+asyncpg://outplayarena:<pass>@arena-db:5432/outplayarena
    REDIS_URL=redis://:<pass>@arena-redis:6379/0
    API_PREFIX=/api
    MCP_RUNTIME=k8s
    MCP_BACKEND_URL=http://arena-backend:8000/api
    MCP_NAMESPACE=arena
    MCP_IMAGE=her3ert/outplayarena-mcp:v0.1.0
    MCP_PUBLIC_BASE_URL=https://arena.example.com
    JWT_SECRET=<openssl rand -hex 32>
    CORS_ALLOW_ORIGINS=https://arena.example.com
    ```
