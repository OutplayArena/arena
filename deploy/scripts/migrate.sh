#!/usr/bin/env bash
# migrate.sh — apply pending Alembic migrations against the live database.
#
# This is the same upgrade-head step the backend runs in its lifespan
# on startup. Use this script to:
#   - Verify migrations are current without bouncing the API
#   - Pre-apply migrations before a deploy (e.g. on a maintenance
#     window or as a sanity check)
#   - Run migrations in a separate init container / job
#
# Usage:
#   /opt/arena/deploy/scripts/migrate.sh                # upgrade head
#   /opt/arena/deploy/scripts/migrate.sh current         # show current head
#   /opt/arena/deploy/scripts/migrate.sh history         # list revisions
#
# Reads the same DATABASE_URL as the backend (loaded from
# /opt/arena/deploy/.env so it matches what the API uses).
#
# Runs alembic in a throwaway `docker run` container on the stack's overlay
# network (Swarm, not plain `docker compose` — there's no compose project to
# exec/run against). Pass MIGRATE_IMAGE to target a specific image instead of
# whatever IMAGE_TAG is currently set in .env, e.g. to apply migrations
# against a new release *before* rolling the service (see swarm-deploy.sh).

set -euo pipefail

STACK_DIR="${STACK_DIR:-/opt/arena}"
COMPOSE_DIR="$STACK_DIR/deploy"
ENV_FILE="$COMPOSE_DIR/.env"
BACKEND_DIR="$STACK_DIR/backend"

# Load DATABASE_URL from the same .env the backend uses.
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

# The .env on this deploy only carries POSTGRES_USER / POSTGRES_PASSWORD /
# POSTGRES_DB — the backend constructs DATABASE_URL itself in docker-compose.
# Mirror that here so a manual migration run sees the same URL the API
# would use at runtime. (asyncpg → sync strip is the only transformation.)
if [[ -z "${DATABASE_URL:-}" ]]; then
    if [[ -n "${POSTGRES_USER:-}" && -n "${POSTGRES_PASSWORD:-}" && -n "${POSTGRES_DB:-}" ]]; then
        POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
        POSTGRES_PORT="${POSTGRES_PORT:-5432}"
        DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
    else
        echo "[migrate] DATABASE_URL is not set; check $ENV_FILE" >&2
        exit 1
    fi
fi

# Alembic runs against a synchronous URL. The backend's DATABASE_URL
# uses +asyncpg (asyncpg driver); strip that for alembic's sync engine.
SYNC_URL="${DATABASE_URL/%+asyncpg/}"

ACTION="${1:-upgrade}"

# Production runs as a single-node Swarm stack (`docker stack deploy`), not
# plain `docker compose` — there's no compose project to `exec`/`run`
# against. Run alembic in a throwaway container on the stack's overlay
# network instead; this also lets swarm-deploy.sh point MIGRATE_IMAGE at
# the *new* tag and apply migrations before rolling the running service.
IMAGE="${MIGRATE_IMAGE:-her3ert/outplayarena-backend:${IMAGE_TAG:-latest}}"
NETWORK="${MIGRATE_NETWORK:-arena_default}"
run_in_container() {
    docker run --rm --network "$NETWORK" \
        -e DATABASE_URL="$SYNC_URL" \
        "$IMAGE" python -m alembic "$@"
}

case "$ACTION" in
    upgrade|upgrade-head|head)
        echo "[migrate] Applying pending migrations..."
        run_in_container upgrade head
        ;;
    current)
        echo "[migrate] Current Alembic head:"
        run_in_container current
        ;;
    history)
        echo "[migrate] Alembic revision history:"
        run_in_container history
        ;;
    *)
        echo "Usage: $0 [upgrade|current|history]" >&2
        exit 2
        ;;
esac
