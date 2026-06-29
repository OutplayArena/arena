# Docker Compose

Deploy OutplayArena using Docker Compose for single-server production deployments. The production compose file pulls pre-built images from Docker Hub and configures Traefik with automatic TLS.

## Prerequisites

- Docker Engine 24+, Docker Compose v2
- A domain pointed at your server (A record in DNS)
- Ports 80 and 443 open on your server

## Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone https://github.com/OutplayArena/arena.git
cd arena/deploy
```

### 2. Configure Environment

```bash
cp .env.production.example .env
chmod 600 .env
$EDITOR .env
```

Required variables to fill in:

| Variable | How to set |
|---|---|
| `DOMAIN` | Your public domain (e.g. `arena.example.com`) |
| `ACME_EMAIL` | Email for Let's Encrypt |
| `IMAGE_TAG` | Release tag (e.g. `v0.1.0`) |
| `POSTGRES_PASSWORD` | `openssl rand -hex 16` |
| `REDIS_PASSWORD` | `openssl rand -hex 16` |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `TRAEFIK_DASHBOARD_AUTH` | `htpasswd -nb admin <password>` |
| `CORS_ALLOW_ORIGINS` | `https://your-domain.com` |
| `OAUTH_ALLOWED_BASES` | `https://your-domain.com` |

See [Environment Configuration](configuration.md) for all variables.

### 3. Configure OAuth (optional but recommended)

Without OAuth, the platform has no user login. To enable it:

1. Create a GitHub or Google OAuth app (see [OAuth setup](configuration.md#setting-up-github-oauth))
2. Add the client ID/secret to `.env`
3. Set the callback URL in your OAuth provider to `https://your-domain.com/api/auth/github/callback` or `/api/auth/google/callback`

### 4. Start the Stack

```bash
docker compose pull           # pull latest images from Docker Hub
docker compose up -d          # start all services
docker compose logs -f        # watch logs
```

### 5. Run Migrations

Migrations run automatically on startup via the `migrations` service. To check they succeeded:

```bash
docker compose logs migrations
```

To run migrations manually:

```bash
docker compose exec backend alembic -c /app/alembic.ini upgrade head
```

### 6. Verify

```bash
# Check all services are running
docker compose ps

# Check backend health
curl https://your-domain.com/api/health
```

## Architecture

```
Internet → Traefik (:80/:443)
              └── your-domain.com → Backend (:8000)
                                        ├── PostgreSQL (:5432, internal)
                                        ├── Redis (:6379, internal)
                                        └── MCP containers (spawned on demand)
```

## Services

The production compose file runs:

| Service | Image | Description |
|---|---|---|
| `traefik` | `traefik:v3.7` | Reverse proxy with Let's Encrypt TLS |
| `db` | `postgres:16-alpine` | PostgreSQL database |
| `redis` | `redis:7-alpine` | Redis pub/sub and cache |
| `migrations` | `her3ert/outplayarena-backend:TAG` | One-shot Alembic migration runner |
| `backend` | `her3ert/outplayarena-backend:TAG` | FastAPI backend + React frontend |
| `mcp` | `her3ert/outplayarena-mcp:TAG` | MCP server (always-on mode) |

## Updating

```bash
# Edit IMAGE_TAG in .env to the new release, then:
docker compose pull
docker compose up -d

# Migrations run automatically on restart
```

## Backup and Restore

```bash
# Backup database
./scripts/backup.sh

# Manual backup
docker compose exec db pg_dump -U outplayarena outplayarena > backup.sql

# Restore from backup
cat backup.sql | docker compose exec -T db psql -U outplayarena outplayarena
```

## Traefik Dashboard

The Traefik dashboard is accessible only via SSH tunnel for security:

```bash
ssh -L 8080:localhost:8080 user@your-server
```

Then open `http://localhost:8080` and log in with the credentials from `TRAEFIK_DASHBOARD_AUTH`.

## Troubleshooting

**Backend won't start:**
```bash
docker compose logs backend
```

**Migrations fail:**
```bash
docker compose logs migrations
# Run manually:
docker compose exec backend alembic -c /app/alembic.ini upgrade head
```

**TLS certificate not issued:**
- Verify port 80 is open (Let's Encrypt HTTP challenge uses port 80)
- Check Traefik logs: `docker compose logs traefik`
- Ensure DNS is pointing to the server before starting

**MCP containers not starting:**
```bash
docker compose logs backend | grep mcp
# Ensure Docker socket is accessible from the backend container
```
