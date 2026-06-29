# Local Dev with Minikube

This track deploys the full stack in a local Kubernetes cluster using the production Helm chart. The frontend and backend run outside the cluster for hot-reload. This gives you production parity including MCP container spawning.

## Prerequisites

- Python 3.12+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) Python package manager
- [minikube](https://minikube.sigs.k8s.io/docs/start/)
- [Helm 3.9+](https://helm.sh/docs/intro/install/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- Docker (used by minikube)

## One-Time Setup

### 1. Clone and Configure

```bash
git clone https://github.com/OutplayArena/arena.git
cd arena

cp .env.example .env
# Defaults in .env.example work for minikube — no changes required
```

### 2. Install Dependencies

```bash
uv sync
cd frontend && npm install && cd ..
```

### 3. Start Minikube

```bash
minikube start
```

### 4. Build and Deploy

This command builds the Docker images locally and deploys them to the minikube cluster via Helm:

```bash
./scripts/helm-upgrade.sh --build
```

The first run takes a few minutes. Subsequent runs without `--build` (just `./scripts/helm-upgrade.sh`) re-apply the Helm chart without rebuilding images.

### 5. Start Port Forwarding

Run the dev tunnel in a terminal you keep open (re-run after each login):

```bash
./scripts/dev-tunnel.sh start
```

This sets up `kubectl port-forward` for all services:

| Service | Cluster Port | Local Port |
|---|---|---|
| Backend (API + SPA) | 8000 | 30090 |
| MCP server | 9999 | 9998 |
| Documentation | 80 | 8080 |
| PostgreSQL | 5432 | 5432 |
| Redis | 6379 | 6379 |

## Running Frontend and Backend Outside the Cluster

For hot-reload during development, run the frontend and backend locally (not in the cluster) while using the cluster's PostgreSQL, Redis, and MCP services via the tunnel.

### Backend (hot-reload)

```bash
uv run uvicorn arena.main:app --reload --host 0.0.0.0 --port 8000
```

The backend connects to `localhost:5432` (PostgreSQL) and `localhost:6379` (Redis) via the tunnel.

### Frontend (HMR)

```bash
cd frontend
npm run dev
```

Vite proxies `/api/*` to the backend on `localhost:8000`. Set `ARENA_API_TARGET` to override the API proxy target if needed.

## Development Workflow

### Backend Changes

The backend runs with `--reload` — file saves take effect immediately without cluster interaction.

### Frontend Changes

Vite HMR updates instantly.

### Helm Chart or Deployment Changes

```bash
# Re-deploy without rebuilding images
./scripts/helm-upgrade.sh

# Re-build images and re-deploy
./scripts/helm-upgrade.sh --build
```

### Checking Cluster Status

```bash
# All pods
kubectl -n arena get pods

# Backend logs from the cluster deployment
kubectl -n arena logs deployment/arena-backend -f

# MCP jobs created by game sessions
kubectl -n arena get jobs -l app=mcp-server
```

## MCP Development

The minikube track is required for MCP development because the backend spawns MCP Kubernetes Jobs. With the tunnel running:

- MCP endpoint: `http://localhost:9998/mcp`
- Configure `MCP_ENDPOINT=http://localhost:9998` in `.env` for local backend

## Port Forwarding After Restart

The dev tunnel does not survive reboots or `minikube stop`. Re-run it after each restart:

```bash
./scripts/dev-tunnel.sh start
```

## Troubleshooting

**Images not updating after code change:** Run `./scripts/helm-upgrade.sh --build` to rebuild and re-deploy.

**Port-forward drops:** Restart the tunnel: `./scripts/dev-tunnel.sh start`. This is normal — `kubectl port-forward` connections are not persistent.

**Minikube runs out of resources:** Increase resources: `minikube start --cpus=4 --memory=8192`.

**Helm deploy fails:** Check Helm status and pod logs:
```bash
helm -n arena status arena
kubectl -n arena describe pod <failing-pod>
```
