#!/usr/bin/env bash
# update.sh — pull the latest code, rebuild images, and restart the stack.
#
# Safe to run repeatedly. Old images are pruned after a successful build.

set -euo pipefail

STACK_DIR="${STACK_DIR:-/opt/arena}"
COMPOSE_FILE="$STACK_DIR/deploy/docker-compose.yml"
cd "$STACK_DIR"

log() { echo "[update $(date -u +%FT%TZ)] $*"; }

# Sanity: do we look like a deployment?
[[ -f "$COMPOSE_FILE" ]] || { echo "no $COMPOSE_FILE — set STACK_DIR" >&2; exit 1; }
[[ -d .git ]] || { echo "$STACK_DIR is not a git repo" >&2; exit 1; }

# 1. Pull
log "git pull --ff-only"
git pull --ff-only

# 2. Rebuild images that have build: directives
log "docker compose build --pull"
docker compose -f "$COMPOSE_FILE" build --pull

# 3. Roll the stack
log "docker compose up -d"
docker compose -f "$COMPOSE_FILE" up -d

# 4. Wait for healthchecks, then prune dangling images
log "Waiting 30s for services to settle"
sleep 30
docker image prune -f

# 5. Tail logs briefly so the operator sees any startup error
log "Last 40 lines of each service:"
docker compose -f "$COMPOSE_FILE" logs --tail=40 --no-color
log "Done."
