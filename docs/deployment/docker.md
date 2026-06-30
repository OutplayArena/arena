# Docker Compose

Deploy OutplayArena to a single server using the production Compose file at
`deploy/docker-compose.yml`. It pulls pre-built images from Docker Hub and
configures Traefik with automatic TLS.

This file's `deploy:` keys mean production actually runs it as a **single-node
Docker Swarm stack**, not via plain `docker compose up`. That's what gets you
zero-downtime releases: Swarm only stops the old container for a service once
the new one has passed its healthcheck. `docker compose` itself ignores
`deploy:` entirely, so a plain `docker compose up -d` on this file would
still work, but every update becomes a hard restart that drops connections —
not what you want for a server with live users. See [Single VPS](single-vps.md)
for the fully worked example (Hetzner-specific, but the Swarm steps apply to
any single server).

## Prerequisites

- Docker Engine 24+ (includes Swarm mode — no extra install)
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
| `IMAGE_TAG` | Release tag (e.g. `v0.2.1`) |
| `POSTGRES_PASSWORD` | `openssl rand -hex 16` |
| `REDIS_PASSWORD` | `openssl rand -hex 16` |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `TRAEFIK_DASHBOARD_AUTH` | `htpasswd -nb admin <password>` |

See [Environment Configuration](configuration.md) for all variables.

### 3. Configure OAuth (optional but recommended)

Without OAuth, the platform has no user login. To enable it:

1. Create a GitHub or Google OAuth app (see [OAuth setup](configuration.md#setting-up-github-oauth))
2. Add the client ID/secret to `.env`
3. Set the callback URL in your OAuth provider to `https://your-domain.com/api/auth/github/callback` or `/api/auth/google/callback`

### 4. Initialize the Swarm and Start the Stack

One-time, turns this host into a single-node Swarm:

```bash
docker swarm init
```

Then deploy the stack (`docker stack deploy`, not `docker compose up` — it
reads the same file but honors the `deploy:` keys that make rolling updates
work):

```bash
./scripts/stack-deploy.sh
```

!!! warning
    Don't run a bare `docker stack deploy -c docker-compose.yml arena --with-registry-auth`
    here. Unlike `docker compose`, `docker stack deploy` does **not** auto-read
    `.env` from the working directory for `${VAR}` interpolation — there's no
    `--env-file` flag either. Run it directly and every `${DOMAIN}`,
    `${POSTGRES_PASSWORD}`, etc. silently resolves to an empty string.
    `scripts/stack-deploy.sh` exports `.env` into the shell first, then deploys.

Watch it come up:

```bash
docker stack ps arena
docker service logs -f arena_backend
```

### 5. Migrations

The backend applies pending Alembic migrations itself on startup (its FastAPI
`lifespan()`, idempotent). To run them ahead of time or check on them, see
[Database Migrations](migrations.md).

### 6. Verify

```bash
# Check all services are running (should all show 1/1)
docker service ls

# Check backend health
curl https://your-domain.com/api/health
```

## Architecture

```
Internet → Traefik (:80/:443)
              ├── your-domain.com         → backend (:8000)
              └── your-domain.com/mcp/    → mcp (:8001)
                       │
                       ├── PostgreSQL (:5432, internal)
                       └── Redis (:6379, internal)
```

## Services

| Service | Image | Description |
|---|---|---|
| `traefik` | `traefik:v3.7` | Reverse proxy with Let's Encrypt TLS, swarm-mode Docker provider |
| `postgres` | `postgres:16-alpine` | PostgreSQL database |
| `redis` | `redis:7-alpine` | Redis pub/sub and cache |
| `backend` | `her3ert/outplayarena-backend:TAG` | FastAPI backend + React frontend (runs migrations on boot) |
| `mcp` | `her3ert/outplayarena-mcp:TAG` | Single long-running MCP server |

## Updating

Routine updates happen automatically: pushing a `v*.*.*` tag builds new
images and rolls them out via CI — see
[Single VPS — Continuous deployment](single-vps.md#continuous-deployment).

To roll a release manually instead of waiting on CI:

```bash
sudo ./scripts/swarm-deploy.sh v0.3.0
```

That migrates, then does a healthcheck-gated rolling update of `backend` and
`mcp` one at a time — no `docker compose up -d` hard restart.

## Backup and Restore

```bash
# Scheduled/manual backup
./scripts/backup.sh

# Manual Postgres dump
docker exec "$(docker ps -q -f name=arena_postgres)" \
  pg_dump -U outplayarena outplayarena > backup.sql

# Restore
./scripts/restore.sh latest
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
docker service logs arena_backend
docker service ps arena_backend --no-trunc   # shows the failing task's error
```

**Migrations fail:** see [Database Migrations](migrations.md).

**TLS certificate not issued:**
- Verify port 80 is open (Let's Encrypt HTTP challenge uses port 80)
- Check Traefik logs: `docker service logs arena_traefik`
- Ensure DNS is pointing to the server before starting

**A `docker service update` rolled back unexpectedly:** Swarm auto-rolls back
when the new task fails its healthcheck. Check `docker service ps
arena_backend --no-trunc` for the failure reason.
