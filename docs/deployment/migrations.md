# Database Migrations

OutplayArena uses **Alembic** with **SQLAlchemy** for database schema management. Migrations are versioned scripts in `backend/migrations/versions/` and must be applied before starting the backend.

## How Migrations Run

| Deployment method | How migrations run |
|---|---|
| **Docker Compose** | Automatic — a one-shot `migrations` service runs on every `docker compose up` |
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

## Production (Docker Compose)

The `migrations` service in the production compose file runs automatically:

```bash
docker compose up -d           # migrations run before backend starts
docker compose logs migrations # check migration output
```

To run migrations manually in the running container:

```bash
docker compose exec backend alembic -c /app/alembic.ini upgrade head
```

Using the migration script:

```bash
./deploy/scripts/migrate.sh              # upgrade head
./deploy/scripts/migrate.sh current      # show current version
./deploy/scripts/migrate.sh history      # list all versions
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
# Docker Compose backup
./deploy/scripts/backup.sh

# Manual backup
docker compose exec db pg_dump -U outplayarena outplayarena > backup_$(date +%Y%m%d).sql
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
