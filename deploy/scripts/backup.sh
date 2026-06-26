#!/usr/bin/env bash
# backup.sh — nightly backup of Postgres, Docker volumes, .env, and logs
#             to a Hetzner Storage Box via restic.
#
# Set up once (see docs/deployment/single-vps.md):
#   1. Buy a Hetzner Storage Box (€3.81/mo, 1 TB)
#   2. Get its SFTP credentials (u<id>, password) from Hetzner Robot
#   3. Create the sub-directory on the box:  sftp u<id>@u<id>.your-storagebox.de
#                                          mkdir arena-backups
#   4. sudo apt-get install -y restic
#   5. sudo install -m 600 /dev/null /etc/arena/restic-env   # see below
#   6. Install the cron entry:
#        sudo crontab -e
#        0 3 * * * /opt/arena/deploy/scripts/backup.sh >> /var/log/arena/backup.log 2>&1
#
# This script reads /etc/arena/restic-env for the secrets:
#   RESTIC_REPO=sftp:u123456@u123456.your-storagebox.de:/arena-backups
#   RESTIC_PASSWORD=<long-random-string>
#   STORAGE_BOX_SFTP_KEY=/etc/arena/storagebox_id_ed25519   # optional
#
# Retention: 7 daily, 4 weekly, 6 monthly snapshots.

set -euo pipefail

ENV_FILE="/etc/arena/restic-env"
[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 1; }
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

: "${RESTIC_REPO:?RESTIC_REPO must be set in $ENV_FILE}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD must be set in $ENV_FILE}"

STACK_DIR="${STACK_DIR:-/opt/arena}"
BACKUP_TAG="${BACKUP_TAG:-arena}"
COMPOSE_FILE="$STACK_DIR/deploy/docker-compose.yml"
LOG_DIR="${LOG_DIR:-/var/log/arena}"
TS="$(date -u +%Y%m%d-%H%M%S)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$LOG_DIR"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

cd "$STACK_DIR"

# ── 1. Postgres dump ────────────────────────────────────────────────
log "Dumping Postgres"
PG_CONTAINER="$(docker compose -f "$COMPOSE_FILE" ps -q postgres)"
[[ -n "$PG_CONTAINER" ]] || { log "postgres container not running"; exit 1; }
PG_DUMP="$TMP_DIR/arena-db-${TS}.sql.gz"
docker exec "$PG_CONTAINER" pg_dump -U "${POSTGRES_USER:-outplayarena}" \
    "${POSTGRES_DB:-outplayarena}" | gzip -9 > "$PG_DUMP"
[[ -s "$PG_DUMP" ]] || { log "pg_dump produced empty file"; exit 1; }
log "  $(du -h "$PG_DUMP" | cut -f1)  $PG_DUMP"

# ── 2. Snapshot Docker volumes via restic ──────────────────────────
log "Snapshotting volumes, .env, and logs"
restic backup \
    --tag "$BACKUP_TAG" \
    --tag "automated" \
    --exclude-caches \
    "$PG_DUMP" \
    "$STACK_DIR/deploy/.env" \
    "$LOG_DIR"

# ── 3. Retention ───────────────────────────────────────────────────
log "Applying retention (keep 7 daily, 4 weekly, 6 monthly)"
restic forget \
    --tag "$BACKUP_TAG" \
    --keep-daily 7 \
    --keep-weekly 4 \
    --keep-monthly 6 \
    --prune

# ── 4. Stats ───────────────────────────────────────────────────────
log "Repository stats:"
restic stats --mode raw-data
log "Latest snapshot:"
restic snapshots --latest 1 --tag "$BACKUP_TAG"

log "Backup complete."
