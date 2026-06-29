#!/usr/bin/env bash
# Usage: ./scripts/helm-upgrade.sh [--build | --pull [TAG]] [--with-traefik] [-h]
#
# Bootstraps the local dev cluster by deploying the arena chart with
# NodePort services (so URLs are reachable by IP:port from any Tailscale
# node), and prints the URLs at the end. Reads .env for OAuth + JWT secrets.
#
# Re-runnable: helm upgrades are rolling. Image management is OFF by
# default; pass exactly one of:
#   --build          Build the three arena images (arena-backend,
#                    arena-mcp, arena-docs) from source into minikube.
#   --pull [TAG]     Pull arena-backend and arena-mcp from Docker Hub
#                    (her3ert/outplayarena-*) and load them into minikube.
#                    The docs image has no registry counterpart and is
#                    built locally in this mode. TAG defaults to `latest`
#                    (e.g. `--pull v0.2.0` for the v0.2.0 release).
#
# Architecture: --pull requires amd64 (the published images are amd64-only).
# On arm64/aarch64 hosts, the script tells you to use --build instead.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BUILD_IMAGES=0
PULL_IMAGES=0
PULL_TAG="latest"
INSTALL_TRAEFIK=0

usage() {
  cat <<EOF
Usage: $0 [--build | --pull [TAG]] [--with-traefik] [-h|--help]

  --build         Build the three arena images (arena-backend, arena-mcp,
                  arena-docs) into minikube from source. Mutually exclusive
                  with --pull.

  --pull [TAG]    Pull arena-backend and arena-mcp from Docker Hub
                  (her3ert/outplayarena-*) and load them into minikube.
                  Docs has no registry counterpart and is built locally.
                  TAG defaults to 'latest'. Mutually exclusive with --build.
                  Requires amd64 host (the published images are amd64-only).

  --with-traefik  Also install/upgrade the Traefik ingress controller and
                  the chart's IngressRoute resources. Off by default —
                  kubectl port-forward (see scripts/dev-tunnel.sh) is the
                  recommended way to expose services for local dev.

  -h, --help      Show this help.

Examples:
  $0                          # re-apply chart; pod images unchanged
  $0 --build                  # rebuild all three images, then re-apply chart
  $0 --pull                   # pull backend + mcp (latest) from Docker Hub
  $0 --pull v0.2.0            # pull backend + mcp at v0.2.0
  $0 --pull --with-traefik    # pull latest + install Traefik
EOF
}

# Two-pass arg parse: --pull may be followed by an optional TAG (not a flag).
i=1
while [ $i -le $# ]; do
  arg="${!i}"
  case "$arg" in
    --build)        BUILD_IMAGES=1 ;;
    --with-traefik) INSTALL_TRAEFIK=1 ;;
    -h|--help)      usage; exit 0 ;;
    --pull)
      PULL_IMAGES=1
      # If the next arg exists and doesn't start with '-', treat it as TAG.
      next_i=$((i + 1))
      if [ $next_i -le $# ]; then
        next_arg="${!next_i}"
        case "$next_arg" in
          -*) : ;;            # next is a flag → no TAG, use default
          *)  PULL_TAG="$next_arg"; i=$next_i ;;
        esac
      fi
      ;;
    *) echo "Unknown argument: $arg" >&2; usage; exit 2 ;;
  esac
  i=$((i + 1))
done

if [ "$BUILD_IMAGES" -eq 1 ] && [ "$PULL_IMAGES" -eq 1 ]; then
  echo "ERROR: --build and --pull are mutually exclusive." >&2
  usage; exit 2
fi

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

# Canonical production image references (must match helm/arena/values.yaml).
REGISTRY_ORG="her3ert"
REGISTRY_REPO_BACKEND="outplayarena-backend"
REGISTRY_REPO_MCP="outplayarena-mcp"
LOCAL_REPO_BACKEND="arena-backend"
LOCAL_REPO_MCP="arena-mcp"
LOCAL_REPO_DOCS="arena-docs"

MODE_LABEL="none"
[ "$BUILD_IMAGES" -eq 1 ] && MODE_LABEL="build (local source)"
[ "$PULL_IMAGES" -eq 1 ] && MODE_LABEL="pull (Docker Hub, tag=$PULL_TAG)"

echo "==============================================================="
echo "  OutplayArena — local dev cluster bootstrap"
echo "==============================================================="
echo "Project root:  $PROJECT_ROOT"
echo "Helm release:  $RELEASE  (namespace: $NS)"
echo "Traefik:       $([ "$INSTALL_TRAEFIK" -eq 1 ] && echo yes || echo no)"
echo "Image mode:    $MODE_LABEL"
echo "==============================================================="
echo

# ── 1. Image management (build OR pull OR skip) ────────────────────

# Return the active minikube driver ("docker", "podman", "kvm", etc.) or
# "none" if minikube is missing/stopped, or "unknown" if detection fails.
# Used by build_one to decide whether the in-container build fast path is
# likely to reach upstream registries.
_minikube_driver() {
  if ! command -v minikube >/dev/null 2>&1; then
    echo "none"
    return
  fi
  # JSON output is machine-readable and ANSI-free (the table output embeds
  # colour codes which complicate parsing). If the field is empty or
  # literal "null" (minikube not started), treat it as "none" so we skip
  # the fast path.
  local driver
  driver=$(minikube profile list -o json 2>/dev/null \
    | grep -oE '"Driver"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -1 \
    | sed -E 's/.*"Driver"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')
  if [ -n "$driver" ] && [ "$driver" != "null" ]; then
    echo "$driver"
  else
    echo "none"
  fi
}

build_one() {
  local image="$1"
  local dockerfile="$2"
  echo "  → building $image from $dockerfile ..."

  local driver
  driver=$(_minikube_driver)
  if [ "$driver" = "docker" ]; then
    # Fast path: in-container build with the docker driver has working
    # network (buildkit inside the minikube container shares the host's
    # network namespace via the docker daemon), so the upstream registry
    # is reachable. This is also where minikube's image cache lives.
    if minikube image build -t "$image" -f "$dockerfile" "$PROJECT_ROOT"; then
      return 0
    fi
    echo "  ! minikube image build (driver=docker) failed; falling back to host build + tar load"
  else
    # Skip the fast path for non-docker drivers. podman/kvm/qemu/parallels/
    # hyperkit run the minikube container/VM with an isolated network
    # namespace; buildah inside it can't reach upstream registries like
    # Docker Hub from a typical NAT'd setup, so the build hangs for ~90s
    # on registry timeouts before failing. Going straight to the host
    # build + tar load avoids the wait.
    echo "  (minikube driver: ${driver} — skipping in-container build, going straight to host build + tar load)"
  fi

  # Fallback: build on the host with docker, then load the resulting tar
  # into minikube. The tar handoff is the portable fix — `minikube image
  # load <name>` only works for images already known to the minikube
  # container runtime; images that only exist in the host's docker daemon
  # need to be exported and re-imported.
  #
  # We require docker specifically (no podman fallback). Podman rootless
  # has recurring stability issues with the user-namespace setup
  # (newuidmap failures, userns remap bugs) that are out of scope for
  # this script to work around; docker is the supported builder.
  local builder="docker"
  if ! command -v docker >/dev/null 2>&1; then
    echo "  ERROR: docker is not installed; cannot build $image" >&2
    return 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "  ERROR: docker daemon is unreachable; cannot build $image" >&2
    echo "         (the user may not be in the 'docker' group, or the daemon is not running)" >&2
    return 1
  fi
  echo "  → docker build -t $image -f $dockerfile ."
  if ! docker build -t "$image" -f "$dockerfile" "$PROJECT_ROOT"; then
    echo "  ERROR: docker build failed for $image" >&2
    return 1
  fi
  local tar_path
  tar_path="$(mktemp -t arena-image-XXXXXX.tar)"
  echo "  → docker save $image → $tar_path"
  if ! docker save "$image" -o "$tar_path"; then
    echo "  ERROR: docker save failed for $image" >&2
    rm -f "$tar_path"
    return 1
  fi
  echo "  → minikube image load $tar_path"
  if ! minikube image load "$tar_path"; then
    echo "  ERROR: minikube image load failed for $image (tar: $tar_path)" >&2
    rm -f "$tar_path"
    return 1
  fi
  rm -f "$tar_path"
}

if [ "$BUILD_IMAGES" -eq 1 ]; then
  echo "[1/4] Building all three images from source into minikube ..."
  build_one "${LOCAL_REPO_BACKEND}:latest" backend/docker/Dockerfile
  build_one "${LOCAL_REPO_MCP}:latest"     backend/docker/Dockerfile.mcp
  build_one "${LOCAL_REPO_DOCS}:latest"    docs/Dockerfile
  echo

  # In --build mode we need to override the chart's repository defaults
  # (which point at Docker Hub) to the locally-built tags.
  HELM_IMAGE_OVERRIDES=(
    "--set" "backend.image.repository=${LOCAL_REPO_BACKEND}"
    "--set" "mcpServer.image.repository=${LOCAL_REPO_MCP}"
    "--set" "migrations.image.repository=${LOCAL_REPO_BACKEND}"
  )

elif [ "$PULL_IMAGES" -eq 1 ]; then
  # amd64 gate: published images are amd64-only (the release workflow builds
  # for linux/amd64 exclusively; multi-arch was removed in v0.1.5).
  HOST_ARCH="$(uname -m)"
  case "$HOST_ARCH" in
    x86_64|amd64) ;;  # supported
    aarch64|arm64)
      cat >&2 <<EOF
ERROR: --pull requires an amd64 host. Detected architecture: $HOST_ARCH.

The Docker Hub images at ${REGISTRY_ORG}/${REGISTRY_REPO_BACKEND} and
${REGISTRY_ORG}/${REGISTRY_REPO_MCP} are amd64-only. On arm64 hosts
(Apple Silicon, AWS Graviton, etc.) the containers will fail to start
with "exec format error".

To use this cluster on $HOST_ARCH, build the images from source instead:

    $0 --build

This builds arena-backend, arena-mcp, and arena-docs into the minikube
container runtime directly, so no registry amd64 image is required.
EOF
      exit 2
      ;;
    *)
      echo "WARNING: unrecognised host architecture '$HOST_ARCH'." >&2
      echo "         --pull assumes amd64; continuing may fail at runtime." >&2
      ;;
  esac

  echo "[1/4] Pulling backend + mcp from Docker Hub (tag: $PULL_TAG) ..."
  pull_one() {
    local repo="$1" tag="$2"
    local full="${REGISTRY_ORG}/${repo}:${tag}"
    echo "  → docker pull $full"
    if ! docker pull "$full"; then
      echo "ERROR: failed to pull $full from Docker Hub." >&2
      echo "       Check that the tag exists at https://hub.docker.com/r/${REGISTRY_ORG}/${repo}/tags" >&2
      exit 1
    fi
    echo "  → minikube image load $full"
    if ! minikube image load "$full"; then
      echo "ERROR: failed to load $full into minikube." >&2
      echo "       Is minikube running? Try: minikube status" >&2
      exit 1
    fi
  }
  pull_one "$REGISTRY_REPO_BACKEND" "$PULL_TAG"
  pull_one "$REGISTRY_REPO_MCP"     "$PULL_TAG"
  echo

  # Docs has no registry counterpart — build it locally so the docs
  # service in the chart can start.
  echo "[1/4] Building docs locally (no registry counterpart) ..."
  build_one "${LOCAL_REPO_DOCS}:latest" docs/Dockerfile
  echo

  # In --pull mode the chart's repository defaults already point at
  # the registry; we just need to override the tag.
  HELM_IMAGE_OVERRIDES=(
    "--set" "backend.image.tag=${PULL_TAG}"
    "--set" "mcpServer.image.tag=${PULL_TAG}"
    "--set" "migrations.image.tag=${PULL_TAG}"
  )

else
  echo "[1/4] Skipping image management (run with --build or --pull [TAG] to manage images)"
  # Sanity-check: warn if any of the expected images is missing in minikube.
  # The chart defaults to her3ert/outplayarena-*:latest, so check both
  # the registry-tagged form (for --pull users) and the local-tag form
  # (for --build users) to cover both workflows.
  for img in \
      "${REGISTRY_ORG}/${REGISTRY_REPO_BACKEND}:latest" \
      "${REGISTRY_ORG}/${REGISTRY_REPO_MCP}:latest" \
      "${LOCAL_REPO_DOCS}:latest"; do
    if ! minikube image ls 2>/dev/null | grep -qE "(^|/)$(echo "$img" | sed 's,/,\\/,g')$"; then
      echo "  ! $img not found in minikube. Run '$0 --pull' or '$0 --build'."
    fi
  done
  echo
  HELM_IMAGE_OVERRIDES=()
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
  # The Traefik helm chart installs the traefik.io CRDs, so the
  # IngressRoute/Middleware resources in the arena chart can render.
  HELM_TRAEFIK_OVERRIDES=("--set" "traefik.enabled=true")
  echo
else
  echo "[2/4] Skipping Traefik (pass --with-traefik to install it)"
  # Auto-detect: if Traefik is already present from a previous --with-traefik
  # run, keep the IngressRoute/Middleware resources so they don't get torn
  # down on this re-apply. If Traefik is absent, leave traefik.enabled at
  # its values.yaml default (false) and skip the resources.
  if helm -n "$TRAEFIK_NS" list -q 2>/dev/null | grep -q "^traefik$"; then
    echo "  (Traefik is already installed; keeping IngressRoute/Middleware resources)"
    HELM_TRAEFIK_OVERRIDES=("--set" "traefik.enabled=true")
  else
    HELM_TRAEFIK_OVERRIDES=()
  fi
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
  --set mcpServer.publicBaseUrl="${MCP_PUBLIC_BASE_URL:-http://localhost:${MCP_PORT}}" \
  "${HELM_IMAGE_OVERRIDES[@]}" \
  "${HELM_TRAEFIK_OVERRIDES[@]}"
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
==============================================================
  Cluster is up.  Expose to host with kubectl port-forward:
==============================================================
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
  To switch to a published release image:
      $0 --pull                # latest
      $0 --pull v0.2.0         # a specific release

  To tear down:
      ./scripts/dev-tunnel.sh stop   # if started
      helm -n $NS uninstall $RELEASE
==============================================================
EOF
