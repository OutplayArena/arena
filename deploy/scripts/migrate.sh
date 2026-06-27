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

# Run alembic inside the backend container so we don't have to keep
# alembic installed on the host (it's only in the backend image).
# The container's DATABASE_URL is set by docker-compose; we override
# it here so the migration sees the same sync URL this script computed
# from the .env.
run_in_container() {
    local cmd="$1"
    cd "$COMPOSE_DIR"
    if ! docker compose ps --status running backend >/dev/null 2>&1; then
        # Backend isn't running — start it ephemerally for the upgrade.
        # The lifespan's _run_alembic_upgrade would also do this, but
        # only after the API is fully up; running here is faster and
        # gives a clear "migrations applied" log line.
        docker compose run --rm \
            --entrypoint "" \
            -e DATABASE_URL="$SYNC_URL" \
            backend python -m alembic "$cmd"
    else
        docker compose exec -T \
            -e DATABASE_URL="$SYNC_URL" \
            backend python -m alembic "$cmd"
    fi
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
