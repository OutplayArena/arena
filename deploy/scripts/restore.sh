#!/usr/bin/env bash
# restore.sh — interactive restore from a restic snapshot.
#
# Usage:
#   sudo /opt/arena/deploy/scripts/restore.sh                 # interactive: pick snapshot
#   sudo /opt/arena/deploy/scripts/restore.sh latest          # latest snapshot
#   sudo /opt/arena/deploy/scripts/restore.sh <snapshot-id>   # specific snapshot
#
# What it can restore:
#   1. Postgres  — pipes pg_dump output back into the running container
#   2. .env      — restored to /opt/arena/deploy/.env (if missing)
#   3. Logs      — restored to /var/log/arena
#
# Always restores to a temp dir first so you can inspect before applying.

set -euo pipefail

ENV_FILE="/etc/arena/restic-env"
[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 1; }
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${RESTIC_REPO:?RESTIC_REPO must be set in $ENV_FILE}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD must be set in $ENV_FILE}"

STACK_DIR="${STACK_DIR:-/opt/arena}"
COMPOSE_FILE="$STACK_DIR/deploy/docker-compose.yml"
LOG_DIR="${LOG_DIR:-/var/log/arena}"
RESTORE_DIR="$(mktemp -d)"
TARGET="${1:-}"

log() { echo "[restore] $*"; }

# ── 1. Pick a snapshot ─────────────────────────────────────────────
if [[ -z "$TARGET" || "$TARGET" == "latest" ]]; then
    log "Available snapshots:"
    restic snapshots
    echo
    read -r -p "Snapshot ID to restore (or 'latest'): " TARGET
    [[ -z "$TARGET" || "$TARGET" == "latest" ]] && TARGET="$(restic snapshots --latest 1 --json | python3 -c 'import sys, json; print(json.load(sys.stdin)[0]["id"])')"
fi

log "Restoring snapshot $TARGET to $RESTORE_DIR"
restic restore "$TARGET" --target "$RESTORE_DIR"

# ── 2. Postgres ────────────────────────────────────────────────────
PG_DUMP="$(find "$RESTORE_DIR" -name 'arena-db-*.sql.gz' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
if [[ -n "$PG_DUMP" ]]; then
    echo
    log "Found database dump: $PG_DUMP"
    read -r -p "Restore database from this dump? This OVERWRITES the current DB. [y/N] " ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        PG_CONTAINER="$(docker compose -f "$COMPOSE_FILE" ps -q postgres)"
        [[ -n "$PG_CONTAINER" ]] || { log "postgres container not running"; exit 1; }
        log "Stopping backend + mcp during restore"
        docker compose -f "$COMPOSE_FILE" stop backend mcp
        log "Piping dump into postgres"
        gunzip -c "$PG_DUMP" | docker exec -i "$PG_CONTAINER" \
            psql -U "${POSTGRES_USER:-outplayarena}" -d "${POSTGRES_DB:-outplayarena}" \
                --set ON_ERROR_STOP=on
        log "Restarting backend + mcp"
        docker compose -f "$COMPOSE_FILE" start backend mcp
    fi
else
    log "No database dump found in snapshot"
fi

# ── 3. .env ───────────────────────────────────────────────────────
ENV_SRC="$RESTORE_DIR/opt/arena/deploy/.env"
if [[ -f "$ENV_SRC" ]]; then
    if [[ -f "$STACK_DIR/deploy/.env" ]]; then
        log "Current .env already exists at $STACK_DIR/deploy/.env — leaving it"
    else
        log "Restoring .env from snapshot"
        cp "$ENV_SRC" "$STACK_DIR/deploy/.env"
        chmod 600 "$STACK_DIR/deploy/.env"
    fi
fi

# ── 4. Logs ───────────────────────────────────────────────────────
LOG_SRC="$RESTORE_DIR/var/log/arena"
if [[ -d "$LOG_SRC" ]]; then
    log "Restoring logs to $LOG_DIR"
    mkdir -p "$LOG_DIR"
    rsync -av "$LOG_SRC/" "$LOG_DIR/"
fi

# ── 5. Cleanup ────────────────────────────────────────────────────
log "Restore artifacts at $RESTORE_DIR (not auto-deleted for inspection)"
log "Run:  rm -rf $RESTORE_DIR  when done"

log "Done."
