#!/usr/bin/env bash
# stack-deploy.sh — apply docker-compose.yml to the Swarm stack, the way it
# actually needs to be run.
#
# Unlike `docker compose`, `docker stack deploy` does NOT auto-read .env
# from the working directory for ${VAR} interpolation — there's no
# --env-file flag either. Run it bare and every ${DOMAIN}, ${POSTGRES_PASSWORD},
# etc. in docker-compose.yml silently resolves to an empty string (Postgres
# then refuses to start — "you must specify POSTGRES_PASSWORD" — which is
# at least loud, but every other ${VAR} fails just as silently and some,
# like Redis's ${REDIS_PASSWORD}, won't fail loudly at all).
#
# This wraps the one fix: export .env into the process environment first,
# then deploy. Use this instead of a bare `docker stack deploy` anywhere
# you'd otherwise run it by hand (first bring-up, re-applying after editing
# docker-compose.yml/.env). Routine releases don't go through this at all —
# swarm-deploy.sh uses `docker service update --image`, which doesn't
# re-parse the compose file.

set -euo pipefail

STACK_DIR="${STACK_DIR:-/opt/arena}"
COMPOSE_DIR="$STACK_DIR/deploy"
ENV_FILE="$COMPOSE_DIR/.env"

[[ -f "$ENV_FILE" ]] || { echo "no $ENV_FILE — set STACK_DIR" >&2; exit 1; }
cd "$COMPOSE_DIR"

# `source .env` would run the file as bash, not parse it as plain
# KEY=VALUE — any literal `$` in a value (e.g. TRAEFIK_DASHBOARD_AUTH's
# htpasswd hash, `$apr1$.../...`) gets expanded as a shell variable
# reference instead of kept as-is. Read it line by line and export
# verbatim instead.
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*(#.*)?$ ]] && continue
  export "$line"
done < "$ENV_FILE"

docker stack deploy -c docker-compose.yml arena --with-registry-auth "$@"
