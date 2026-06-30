#!/usr/bin/env bash
# swarm-deploy.sh <image-tag> — roll backend+mcp to <image-tag> with zero
# downtime, via Docker Swarm's healthcheck-gated rolling update.
#
# <image-tag> is a released version tag (e.g. v0.3.0) — the same format
# IMAGE_TAG takes in .env. Called by .github/workflows/release.yml's
# `deploy` job over SSH after a v*.*.* tag's images are pushed to Docker
# Hub; safe to run by hand too.
#
# What it does, in order:
#   1. Apply pending Alembic migrations using the *new* image, before
#      touching the running service — decouples migration timing from
#      rollout timing so the brief old+new overlap window during the
#      rolling update never has a replica running against a schema it
#      doesn't understand yet.
#   2. Roll backend, then mcp, one at a time (docker_swarm `start-first`
#      update_config in docker-compose.yml: new task must pass its
#      healthcheck before the old one is stopped; auto-rollback on
#      failure — see deploy/docker-compose.yml).
#   3. Persist IMAGE_TAG in .env so a future plain `docker stack deploy`
#      (e.g. after a host reboot) redeploys what's actually running.
#   4. Run healthcheck.sh against the live domain to confirm the
#      rollout actually succeeded.
set -euo pipefail

TAG="${1:?usage: swarm-deploy.sh <image-tag>}"
STACK_DIR="${STACK_DIR:-/opt/arena}"
COMPOSE_DIR="$STACK_DIR/deploy"
ENV_FILE="$COMPOSE_DIR/.env"

log() { echo "[swarm-deploy $(date -u +%FT%TZ)] $*"; }

[[ -f "$ENV_FILE" ]] || { echo "no $ENV_FILE — set STACK_DIR" >&2; exit 1; }
cd "$COMPOSE_DIR"

log "Applying migrations against her3ert/outplayarena-backend:${TAG}"
MIGRATE_IMAGE="her3ert/outplayarena-backend:${TAG}" bash "$COMPOSE_DIR/scripts/migrate.sh" upgrade

log "Rolling arena_backend -> ${TAG}"
docker service update --image "her3ert/outplayarena-backend:${TAG}" --with-registry-auth arena_backend

log "Rolling arena_mcp -> ${TAG}"
docker service update --image "her3ert/outplayarena-mcp:${TAG}" --with-registry-auth arena_mcp

log "Persisting IMAGE_TAG=${TAG} in .env"
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${TAG}/" "$ENV_FILE"

log "Running healthcheck.sh"
DOMAIN="${DOMAIN:-arena.core-aix.org}" bash "$COMPOSE_DIR/scripts/healthcheck.sh"

log "Done — ${TAG} is live."
