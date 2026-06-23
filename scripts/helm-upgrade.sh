#!/usr/bin/env bash
# Usage: ./scripts/helm-upgrade.sh [--build] [--with-traefik] [-h]
#
# Bootstraps the local dev cluster by deploying the arena chart with
# NodePort services (so URLs are reachable by IP:port from any Tailscale
# node), and prints the URLs at the end. Reads .env for OAuth + JWT secrets.
#
# Re-runnable: helm upgrades are rolling. Image builds are SKIPPED by
# default; pass --build to (re)build arena-backend, arena-mcp, and
# arena-docs from source.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BUILD_IMAGES=0
INSTALL_TRAEFIK=0
usage() {
  cat <<EOF
Usage: $0 [--build] [--with-traefik] [-h|--help]

  --build         Build the three arena images (arena-backend, arena-mcp,
                  arena-docs) into minikube before deploying. Without this
                  flag the script only re-applies the existing chart.

  --with-traefik  Also install/upgrade the Traefik ingress controller and
                  the chart's IngressRoute resources. Off by default —
                  kubectl port-forward (see scripts/dev-tunnel.sh) is the
                  recommended way to expose services for local dev.

  -h, --help      Show this help.

Examples:
  $0                  # re-apply chart; pod images unchanged
  $0 --build          # rebuild all three images, then re-apply chart
  $0 --with-traefik   # also install/upgrade Traefik (if you need its
                      # ingress features on top of the NodePort URLs)
EOF
}
for arg in "$@"; do
  case "$arg" in
    --build) BUILD_IMAGES=1 ;;
    --with-traefik) INSTALL_TRAEFIK=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; usage; exit 2 ;;
  esac
done

cd "$PROJECT_ROOT"

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in your secrets."
  exit 1
fi

set -a
source .env
set +a

NS="${NAMESPACE:-arena}"
RELEASE="${RELEASE:-arena}"
TRAEFIK_NS="${TRAEFIK_NAMESPACE:-traefik}"

# Host ports the user maps via `kubectl port-forward` (see scripts/dev-tunnel.sh).
# These are arbitrary — change them if they collide with something on your host.
BACKEND_PORT=30090
MCP_PORT=9998
DOCS_PORT=8080
DB_PORT=5432
REDIS_PORT=6379

echo "==============================================================="
echo "  OutplayLabs Arena — local dev cluster bootstrap"
echo "==============================================================="
echo "Project root:  $PROJECT_ROOT"
echo "Helm release:  $RELEASE  (namespace: $NS)"
echo "Traefik:       $([ "$INSTALL_TRAEFIK" -eq 1 ] && echo yes || echo no)"
echo "Build images:  $([ "$BUILD_IMAGES" -eq 1 ] && echo yes || echo no)"
echo "==============================================================="
echo

# ── 1. Build images into the minikube container runtime (opt-in) ─
if [ "$BUILD_IMAGES" -eq 1 ]; then
  build_one() {
    local image="$1"
    local dockerfile="$2"
    echo "  → building $image from $dockerfile ..."
    minikube image build -t "$image" -f "$dockerfile" .
  }
  echo "[1/4] Building images into minikube ..."
  build_one arena-backend:latest backend/docker/Dockerfile
  build_one arena-mcp:latest     backend/docker/Dockerfile.mcp
  build_one arena-docs:latest    docs/Dockerfile
  echo
else
  echo "[1/4] Skipping image builds (run with --build to rebuild)"
  # Sanity-check: warn if any of the three images is missing.
  for img in arena-backend:latest arena-mcp:latest arena-docs:latest; do
    if ! minikube image ls 2>/dev/null | grep -qE "(^|/)${img//\//\\/}$"; then
      echo "  ! $img not found in minikube. Run '$0 --build' to build it."
    fi
  done
  echo
fi

# ── 2. (optional) Install/upgrade Traefik ────────────────────────
if [ "$INSTALL_TRAEFIK" -eq 1 ]; then
  echo "[2/4] Installing/Upgrading Traefik ..."
  if helm -n "$TRAEFIK_NS" list -q 2>/dev/null | grep -q "^traefik$"; then
    echo "  → traefik already installed in $TRAEFIK_NS, upgrading ..."
    helm -n "$TRAEFIK_NS" upgrade traefik traefik/traefik
  else
    echo "  → installing traefik into $TRAEFIK_NS ..."
    helm -n "$TRAEFIK_NS" install traefik traefik/traefik --create-namespace
  fi
  kubectl -n "$TRAEFIK_NS" rollout status deploy/traefik --timeout=180s
  echo
else
  echo "[2/4] Skipping Traefik (pass --with-traefik to install it)"
  echo
fi

# ── 3. Install/upgrade the arena chart ─────────────────────────────
echo "[3/4] Installing/Upgrading arena release '$RELEASE' in namespace '$NS' ..."
helm upgrade "$RELEASE" helm/arena \
  --install \
  --create-namespace \
  --namespace "$NS" \
  --set oauth.githubClientId="${GITHUB_CLIENT_ID}" \
  --set oauth.githubClientSecret="${GITHUB_CLIENT_SECRET}" \
  --set oauth.googleClientId="${GOOGLE_CLIENT_ID}" \
  --set oauth.googleClientSecret="${GOOGLE_CLIENT_SECRET}" \
  --set oauth.jwtSecret="${JWT_SECRET}" \
  --set oauth.callbackBaseUrl="${OAUTH_CALLBACK_BASE_URL:-http://localhost:${BACKEND_PORT}}" \
  --set mcpServer.publicBaseUrl="${MCP_PUBLIC_BASE_URL:-http://localhost:${MCP_PORT}}"
echo

# ── 4. Wait for migrations to finish and main pods to be ready ──────
echo "[4/4] Waiting for migrations Job and main pods ..."
kubectl -n "$NS" wait --for=condition=complete --timeout=300s \
  "job/${RELEASE}-migrations" 2>/dev/null || \
  echo "  (migrations job not found or still running — check with: kubectl -n $NS get jobs)"
kubectl -n "$NS" rollout status deploy/"${RELEASE}-backend" --timeout=180s
kubectl -n "$NS" rollout status deploy/"${RELEASE}-mcp"     --timeout=180s
kubectl -n "$NS" rollout status deploy/"${RELEASE}-docs"    --timeout=180s
echo

# ── Print the URLs the user can hit ────────────────────────────────
HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
cat <<EOF
===============================================================
  Cluster is up.  Expose to host with kubectl port-forward:
===============================================================
  One-shot (manual, foreground):
      kubectl -n $NS port-forward svc/${RELEASE}-backend ${BACKEND_PORT}:8000 --address 0.0.0.0
      kubectl -n $NS port-forward svc/${RELEASE}-mcp     ${MCP_PORT}:9999      --address 0.0.0.0
      kubectl -n $NS port-forward svc/${RELEASE}-docs    ${DOCS_PORT}:80       --address 0.0.0.0

  Or run them all in the background:
      ./scripts/dev-tunnel.sh start        # tails logs to /tmp/arena-dev/pf-*.log
      ./scripts/dev-tunnel.sh stop
      ./scripts/dev-tunnel.sh status

  URLs (replacing ${HOST_IP} with your host's LAN/Tailscale IP, e.g. 100.106.18.87):
      Backend    http://${HOST_IP}:${BACKEND_PORT}/   (also serves the SPA at /)
      MCP        http://${HOST_IP}:${MCP_PORT}/
      Docs       http://${HOST_IP}:${DOCS_PORT}/
      Postgres   ${HOST_IP}:${DB_PORT}
      Redis      ${HOST_IP}:${REDIS_PORT}

  Frontend with HMR (local):
      cd frontend && npm run dev
      open http://localhost:5173   (vite proxies /api to localhost:${BACKEND_PORT})

  To rebuild after backend code changes:
      $0 --build

  To tear down:
      ./scripts/dev-tunnel.sh stop   # if started
      helm -n $NS uninstall $RELEASE
===============================================================
EOF
