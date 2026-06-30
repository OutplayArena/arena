#!/usr/bin/env bash
# update.sh — pull the latest code, rebuild images locally, and re-apply the
# Swarm stack definition. This is a FALLBACK, not the routine update path:
#
#   - Routine releases: push a v*.*.* tag. CI builds+pushes images to Docker
#     Hub and rolls them out via swarm-deploy.sh with zero-downtime
#     rolling updates (healthcheck-gated, auto-rollback on failure).
#   - This script: rebuilds from whatever's on disk and re-applies
#     docker-compose.yml as-is — useful for first-time bring-up, or
#     recovering a box where CI/SSH access is unavailable. It does a hard
#     `docker stack deploy` (no rolling-update gating), so it WILL briefly
#     interrupt live sessions; don't use it for routine deploys.
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

# 2. Rebuild images that have build: directives (local cache only; Swarm
#    itself ignores build: and deploys whatever IMAGE_TAG resolves to).
log "docker compose build --pull"
docker compose -f "$COMPOSE_FILE" build --pull

# 3. Re-apply the stack definition (picks up docker-compose.yml/.env changes).
#    Goes through stack-deploy.sh, not a bare `docker stack deploy` — unlike
#    `docker compose`, the stack-deploy parser does NOT auto-read .env from
#    the working directory for ${VAR} interpolation, so calling it directly
#    here would silently deploy with every ${DOMAIN}/${POSTGRES_PASSWORD}/etc.
#    blank.
log "stack-deploy"
bash "$STACK_DIR/deploy/scripts/stack-deploy.sh"

# 4. Wait for healthchecks, then prune dangling images
log "Waiting 30s for services to settle"
sleep 30
docker image prune -f

# 5. Tail logs briefly so the operator sees any startup error
log "Last 40 lines of each service:"
docker service logs --tail=40 --no-color arena_backend
docker service logs --tail=40 --no-color arena_mcp
log "Done."
