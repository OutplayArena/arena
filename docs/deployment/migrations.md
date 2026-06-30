# Database Migrations

OutplayArena uses **Alembic** with **SQLAlchemy** for database schema management. Migrations are versioned scripts in `backend/migrations/versions/` and must be applied before starting the backend.

## How Migrations Run

| Deployment method | How migrations run |
|---|---|
| **Docker Compose / Single VPS** | Automatic — the `backend` container applies pending migrations in its FastAPI `lifespan()` on every boot (idempotent). CI also pre-applies them against the *new* image before rolling the service — see below. |
| **Kubernetes** | Automatic — a `migrations` Kubernetes Job runs before the backend deployment |
| **Local development** | Manual — run `uv run alembic upgrade head` after cloning or pulling |

## Local Development

```bash
# Apply all pending migrations
uv run alembic -c backend/alembic.ini upgrade head

# Check current migration version
uv run alembic -c backend/alembic.ini current

# List all migration history
uv run alembic -c backend/alembic.ini history

# Roll back the last migration
uv run alembic -c backend/alembic.ini downgrade -1

# Roll back to a specific revision
uv run alembic -c backend/alembic.ini downgrade abc123
```

## Production (Docker Compose / Single VPS)

Production runs as a single-node Docker Swarm stack (`docker stack deploy`,
not plain `docker compose` — see [Docker Compose](docker.md)). There's no
compose project to `exec`/`run` against, so migrations run two ways:

1. **On every backend boot** — the `backend` container's FastAPI `lifespan()`
   applies pending migrations automatically (idempotent, fatal on failure).
2. **Pre-applied by CI before a rollout** — `deploy/scripts/swarm-deploy.sh`
   runs migrations against the *new* image in a throwaway container, before
   touching the running `backend`/`mcp` services. This avoids a window where
   the old and new task (briefly running side by side during the
   healthcheck-gated rolling update) disagree on schema.

To run migrations manually, use `deploy/scripts/migrate.sh` — it runs
Alembic in a throwaway `docker run` container on the stack's overlay network:

```bash
./deploy/scripts/migrate.sh              # upgrade head
./deploy/scripts/migrate.sh current      # show current version
./deploy/scripts/migrate.sh history      # list all versions

# Apply migrations against a specific release tag's image, e.g. before
# rolling the service to it (this is what swarm-deploy.sh does):
MIGRATE_IMAGE=her3ert/outplayarena-backend:v0.3.0 ./deploy/scripts/migrate.sh upgrade
```

## Kubernetes

Migrations run as a Kubernetes Job at deploy time:

```bash
# Check migration job status
kubectl -n arena get jobs

# View migration logs
kubectl -n arena logs job/arena-migrations

# Run migrations manually in a running backend pod
kubectl -n arena exec -it deployment/arena-backend -- \
  alembic -c /app/alembic.ini upgrade head
```

## Before Migrating in Production

!!! warning "Always back up before migrating"
    Run a database backup before any migration, especially downgrade operations.

```bash
# Docker Compose / Single VPS backup
./deploy/scripts/backup.sh

# Manual backup
docker exec "$(docker ps -q -f name=arena_postgres)" \
  pg_dump -U outplayarena outplayarena > backup_$(date +%Y%m%d).sql
```

## Migration Files

Migration scripts are in `backend/migrations/versions/`. Each file:
- Has a unique revision ID
- References its parent (`down_revision`)
- Contains `upgrade()` and `downgrade()` functions

```
backend/
  alembic.ini              # Alembic config (points to migrations/ directory)
  migrations/
    env.py                 # Alembic runtime environment
    versions/
      0f0e87320c1f_add_public_url_to_mcp_instances.py
      a2d3e4f5b001_add_api_keys_and_session_agents.py
      d4569ee22af1_initial_sessions.py
      ...
```

## Writing New Migrations

If you're contributing a schema change (see [Contributing](../contributing.md)), generate a migration with:

```bash
# Auto-generate from SQLAlchemy model changes
uv run alembic -c backend/alembic.ini revision \
  --autogenerate \
  -m "describe_your_change"

# Create an empty migration to write manually
uv run alembic -c backend/alembic.ini revision \
  -m "describe_your_change"
```

Always review the auto-generated migration before committing — Alembic's diff detection is good but not perfect for complex schema changes.
