#!/usr/bin/env bash
# Usage: ./scripts/helm-upgrade.sh
# Reads .env and deploys to minikube with OAuth secrets.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in your secrets."
  exit 1
fi

set -a
source .env
set +a

NS="${NAMESPACE:-nasharena}"
RELEASE="${RELEASE:-nasharena}"

echo "Deploying $RELEASE to namespace $NS ..."

helm upgrade "$RELEASE" helm/nash_arena \
  --install \
  --create-namespace \
  --namespace "$NS" \
  --set oauth.githubClientId="${GITHUB_CLIENT_ID}" \
  --set oauth.githubClientSecret="${GITHUB_CLIENT_SECRET}" \
  --set oauth.googleClientId="${GOOGLE_CLIENT_ID}" \
  --set oauth.googleClientSecret="${GOOGLE_CLIENT_SECRET}" \
  --set oauth.jwtSecret="${JWT_SECRET}" \
  --set oauth.callbackBaseUrl="${OAUTH_CALLBACK_BASE_URL}"

echo "Done. Check with: kubectl get pods -n $NS"
