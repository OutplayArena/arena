#!/usr/bin/env bash
# backup.sh — GFS-rotation backups for the OutplayArena deployment.
#
# Usage (called from cron, see docs/deployment/single-vps.md):
#   backup.sh daily    # every night at 03:00
#   backup.sh weekly   # Sunday at 23:59
#   backup.sh monthly  # 28th of the month at 23:59
#
# What it does:
#   1. If BACKUP_DIR is set, dump Postgres + .env into
#      ${BACKUP_DIR}/<tag>/<UTC-timestamp>/, then prune ${BACKUP_DIR}/<tag>/
#      to keep only its single most recent copy. This is the local GFS tier.
#   2. If RESTIC_REPO is set (production only), also push the same artifacts
#      to the restic repo and apply retention (7 daily / 4 weekly / 6 monthly).
#
# GFS rotation = Grandfather-Father-Son:
#   - daily   copy is overwritten every night
#   - weekly  copy is overwritten every Sunday
#   - monthly copy is overwritten on the 28th
# Each tier holds exactly one copy at any time. Space-efficient and
# deterministic; no retention math, no restic needed.
#
# Cron wiring (the user runs `crontab -e` once on the VPS):
#   0  3 *   *   *   /opt/arena/deploy/scripts/backup.sh daily   >> /var/log/arena/backup.log 2>&1
#   59 23 *   *   0   /opt/arena/deploy/scripts/backup.sh weekly  >> /var/log/arena/backup.log 2>&1
#   59 23 28  *   *   /opt/arena/deploy/scripts/backup.sh monthly >> /var/log/arena/backup.log 2>&1

set -euo pipefail

TAG="${1:-}"
case "$TAG" in
    daily|weekly|monthly) ;;
    *) echo "usage: $0 {daily|weekly|monthly}" >&2; exit 2 ;;
esac

STACK_DIR="${STACK_DIR:-/opt/arena}"
COMPOSE_FILE="$STACK_DIR/deploy/docker-compose.yml"
LOG_DIR="${LOG_DIR:-/var/log/arena}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${BACKUP_DIR:-}"
RESTIC_REPO="${RESTIC_REPO:-}"

mkdir -p "$LOG_DIR"

log() { echo "[$(date -u +%FT%TZ)] [backup:$TAG] $*"; }

cd "$STACK_DIR"

# ── 1. Postgres dump ────────────────────────────────────────────────
PG_DUMP_DIR="$(mktemp -d)"
trap 'rm -rf "$PG_DUMP_DIR"' EXIT
PG_DUMP="$PG_DUMP_DIR/db.sql.gz"
PG_CONTAINER="$(docker compose -f "$COMPOSE_FILE" ps -q postgres 2>/dev/null || true)"
if [[ -n "$PG_CONTAINER" ]]; then
    log "Dumping Postgres"
    docker exec "$PG_CONTAINER" pg_dump -U "${POSTGRES_USER:-outplayarena}" \
        "${POSTGRES_DB:-outplayarena}" | gzip -9 > "$PG_DUMP"
else
    log "WARN: postgres container not running — skipping pg_dump"
    : > "$PG_DUMP"
fi

# ── 2. .env ────────────────────────────────────────────────────────
ENV_SRC="$STACK_DIR/deploy/.env"
[[ -f "$ENV_SRC" ]] || { log "FATAL: $ENV_SRC not found"; exit 1; }

# ── 3. Local GFS rotation via BACKUP_DIR ───────────────────────────
if [[ -n "$BACKUP_DIR" ]]; then
    TARGET="$BACKUP_DIR/$TAG/$TS"
    log "Writing local snapshot to $TARGET"
    mkdir -p "$TARGET"
    chmod 700 "$TARGET"
    cp "$PG_DUMP" "$TARGET/db.sql.gz"
    cp "$ENV_SRC" "$TARGET/.env"
    chmod 600 "$TARGET/.env"

    # Prune: keep only the single most recent copy in this tier.
    # `ls -1t` sorts by mtime (newest first), so `tail -n +2` skips the first.
    prune_dir="$BACKUP_DIR/$TAG"
    if [[ -d "$prune_dir" ]]; then
        # Only operate on direct subdirs (each snapshot is a directory)
        shopt -s nullglob dotglob
        existing=( "$prune_dir"/*/ )
        shopt -u nullglob dotglob
        if (( ${#existing[@]} > 1 )); then
            log "Pruning $((${#existing[@]} - 1)) older $TAG snapshot(s)"
            for old in "${existing[@]}"; do
                # Sort by mtime, keep newest, remove the rest
                :
            done
            # Sort by mtime newest-first, keep [0], rm [1..]
            IFS=$'\n'
            sorted=( $(ls -1td "${existing[@]}" 2>/dev/null) )
            unset IFS
            for ((i=1; i<${#sorted[@]}; i++)); do
                rm -rf "${sorted[$i]}"
            done
        fi
    fi
else
    log "BACKUP_DIR is empty — skipping local GFS rotation"
fi

# ── 4. Restic push (production only) ───────────────────────────────
if [[ -n "$RESTIC_REPO" ]]; then
    ENV_FILE="${RESTIC_ENV_FILE:-/etc/arena/restic-env}"
    if [[ ! -f "$ENV_FILE" ]]; then
        log "WARN: RESTIC_REPO set but $ENV_FILE missing — skipping restic"
    else
        # shellcheck disable=SC1090
        set -a; source "$ENV_FILE"; set +a
        : "${RESTIC_PASSWORD:?RESTIC_PASSWORD must be set in $ENV_FILE}"

        log "Pushing to restic repo $RESTIC_REPO"
        restic backup \
            --tag "arena" --tag "$TAG" \
            --exclude-caches \
            "$PG_DUMP" \
            "$ENV_SRC" \
            "$LOG_DIR"

        log "Applying retention (7 daily / 4 weekly / 6 monthly)"
        restic forget \
            --tag "arena" \
            --keep-daily 7 --keep-weekly 4 --keep-monthly 6 \
            --prune
    fi
else
    log "RESTIC_REPO empty — skipping restic push"
fi

log "Backup ($TAG) complete."
