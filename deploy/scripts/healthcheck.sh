#!/usr/bin/env bash
# healthcheck.sh — verify the stack is healthy.
#
# Usage:
#   /opt/arena/deploy/scripts/healthcheck.sh                    # localhost
#   DOMAIN=arena.example.com /opt/arena/deploy/scripts/healthcheck.sh  # remote
#
# Exit codes:
#   0  all checks passed
#   1  at least one check failed

set -uo pipefail

DOMAIN="${DOMAIN:-localhost}"
SCHEME="${SCHEME:-https}"
BASE="${SCHEME}://${DOMAIN}"
INSECURE=""
[[ "$SCHEME" == "https" && "$DOMAIN" == "localhost" ]] && INSECURE="-k"

FAIL=0
check() {
    local name="$1" url="$2" expected="${3:-200}"
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' $INSECURE --max-time 10 "$url" || echo 000)"
    if [[ "$code" == "$expected" ]]; then
        printf "  [OK]   %-30s %s  (HTTP %s)\n" "$name" "$url" "$code"
    else
        printf "  [FAIL] %-30s %s  (HTTP %s, expected %s)\n" "$name" "$url" "$code" "$expected"
        FAIL=1
    fi
}

echo "Healthcheck for $BASE"
check "Backend (root SPA)"        "$BASE/"
check "API root"                  "$BASE/api/" "404"
check "API site-config"           "$BASE/api/site-config"
check "API games"                 "$BASE/api/games"
check "MCP health"                "$BASE/mcp/health"
check "Docs index"                "$BASE/docs-static/"

if (( FAIL )); then
    echo "FAILED — at least one check above is red"
    exit 1
fi
echo "All checks passed."
