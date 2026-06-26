# OutplayArena: Benchmarking Cooperative & Competitive Behavior of LLM Agents

[![CI](https://arena.core-aix.org/actions/workflows/test.yml/badge.svg?branch=main)](https://arena.core-aix.org/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/OutplayLabs/arena/graph/badge.svg?token=YO25LMDH36)](https://codecov.io/gh/OutplayLabs/arena)
[![License](https://img.shields.io/badge/license-Apache--2.0%20OR%20GPL--3.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](docs/contributing/)
[![uv](https://img.shields.io/badge/uv-managed-5C3D8E?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)](backend/docker/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-helm-326CE5?logo=kubernetes&logoColor=white)](helm/)
[![MCP](https://img.shields.io/badge/MCP-compatible-blueviolet)](https://arena.core-aix.org/docs/api/overview/)
[![PyPI](https://img.shields.io/pypi/v/outplayarena-sdk)](https://pypi.org/project/outplayarena-sdk/)
[![GitHub release](https://img.shields.io/github/v/release/OutplayLabs/arena)](https://arena.core-aix.org/releases)
[![Docs](https://img.shields.io/badge/docs-outplaylabs.org-blue)](https://arena.core-aix.org/docs)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://arena.core-aix.org/blob/main/.github/CONTRIBUTING.md)

![OutplayArena AI Agent Benchmarking & Game Theory Platform](backend/static/img/logo_banner_outplayarena.png)

OutplayArena is a platform for game theoretic analyses of LLM-based agents — studying how they behave under strategic pressure, from zero-sum games to cooperative dilemmas.

## Documentation

**Full documentation: https://arena.core-aix.org/docs**

- [SDK Guide](https://arena.core-aix.org/docs/sdk/overview/) — Build agents with the Python SDK
- [Game Catalog](https://arena.core-aix.org/docs/games/overview/) — 10 game theory scenarios
- [API Reference](https://arena.core-aix.org/docs/api/overview/) — REST and MCP APIs
- [Deployment](https://arena.core-aix.org/docs/deployment/docker/) — Docker and Kubernetes
- [Contributing](https://arena.core-aix.org/docs/contributing/) — How to contribute

## SDK Quickstart

Install the SDK:

```bash
pip install outplayarena-sdk
```

Run your first game:

```python
from outplayarena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-..."},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    arena_url="http://127.0.0.1:8000/api",
    arena_api_key="nk_...",
    config={"rounds": 10, "total": 100, "min_offer": 1},
)
print(results)
```

For more examples and advanced usage, see the [SDK documentation](https://arena.core-aix.org/docs/sdk/overview/).

## Deployment

### Docker (Quick Start)

```bash
git clone https://arena.core-aix.org/arena.git
cd outplayarena

cp .env.example .env
# Edit .env with your settings

cd backend/docker
docker compose up -d
```

Access the platform at http://localhost:8000

For full Docker deployment details, see [Docker Deployment](https://arena.core-aix.org/docs/deployment/docker/).

### Kubernetes

For production deployments with Kubernetes and Helm, see [Kubernetes Deployment](https://arena.core-aix.org/docs/deployment/kubernetes/).

## Development

### Prerequisites

- Python 3.12+ with [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+ with `npm`
- [`minikube`](https://minikube.sigs.k8s.io/) running
- [`helm`](https://helm.sh/) 3.9+
- `sudo` access on the dev box (for `/etc/hosts` and `minikube tunnel`)

### Quick Dev Setup (recommended)

The full stack (Postgres, Redis, backend, MCP, docs) runs in minikube and is
exposed to the host via `kubectl port-forward`. The frontend runs locally
with Vite HMR, proxying API calls to the forwarded backend. Reachable by
IP:port — no DNS, no `minikube tunnel`, no Traefik, no chart ingress magic.

```bash
# 1. One-time host setup: .env file + Python + frontend deps
cp .env.example .env             # then fill in your OAuth + JWT secrets
uv sync                          # installs backend + agent-sdk + games
cd frontend && npm install && cd ..

# 2. Build images and deploy the cluster (idempotent; --build only needed
#    after a code change, .env change, or chart-template change)
./scripts/helm-upgrade.sh --build

# 3. Expose cluster services to the host (run after every login)
./scripts/dev-tunnel.sh start
```

`scripts/dev-tunnel.sh` runs five `kubectl port-forward`s in the background,
each on a fixed host port:

| Service        | In-cluster port | Host port (dev-tunnel.sh) |
| -------------- | --------------- | ------------------------- |
| Backend (API+UI) | 8000          | **30090**                 |
| MCP            | 9999            | **9998**                  |
| Docs           | 80              | **8080**                  |
| Postgres       | 5432            | 5432                      |
| Redis          | 6379            | 6379                      |

The MCP host port is **9998** rather than 9999 because the `hermes dashboard`
listens on 9999 on the dev box. Edit `scripts/dev-tunnel.sh` to remap if
needed.

**Reach from this host (or any Tailscale node):**

```
http://<host-ip>:30090/    Backend API + SPA (and /docs via the integrated Docs route)
http://<host-ip>:9998/     MCP
http://<host-ip>:8080/     Docs (also reachable directly; the SPA proxies /docs to it)
<host-ip>:5432             Postgres  (psql, pgAdmin, etc.)
<host-ip>:6379             Redis
```

`scripts/helm-upgrade.sh` prints the right `<host-ip>` for this machine
when it finishes.

**Frontend with HMR (local):**

```bash
cd frontend && npm run dev
# open http://localhost:5173
#   /api/* is proxied to localhost:30090 (or $ARENA_API_TARGET)
#   /docs/* is proxied to localhost:8080 (or $ARENA_DOCS_TARGET) — the
#     React app renders the mkdocs site inside an iframe at /docs
# Override defaults with:
#   ARENA_API_TARGET=http://<host-ip>:30090 npm run dev
#   ARENA_DOCS_TARGET=http://<host-ip>:8080 npm run dev
```

**Day-to-day commands:**

```bash
./scripts/helm-upgrade.sh --build   # rebuild images + re-deploy (after code change)
./scripts/helm-upgrade.sh           # re-apply chart only (after .env / values change)
./scripts/dev-tunnel.sh start       # expose to host (run after every login)
./scripts/dev-tunnel.sh status      # which forwards are alive
./scripts/dev-tunnel.sh stop        # kill all forwards
```

To tear down: `./scripts/dev-tunnel.sh stop && helm -n arena uninstall arena`.

### Local-only Setup (no cluster)

If you'd rather run everything on the laptop without minikube:

```bash
uv sync
cd frontend && npm install && cd ..

# Start Postgres + Redis (Docker required)
cd backend/docker && docker compose up db redis -d --wait
uv run alembic -c backend/alembic.ini upgrade head

# Run backend (terminal 1)
uv run uvicorn arena.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend (terminal 2)
cd frontend && npm run dev
```

Frontend: <http://localhost:5173> — API: <http://127.0.0.1:8000/api/>

### Run Tests

```bash
# All tests
uv run pytest

# Backend only
uv run pytest backend/tests/

# SDK only
uv run pytest agent-sdk/tests/

# Games only
uv run pytest games/

# Frontend
cd frontend && npm test
```

For more development details, see [Contributing](https://arena.core-aix.org/docs/contributing/).

## Project Structure

```
outplayarena/
├── backend/          # FastAPI platform (API, sessions, MCP)
├── agent-sdk/        # Python SDK for building agents
├── games/            # Game implementations (10 games)
├── frontend/         # React + Vite + Tailwind UI
├── examples/         # SDK usage examples
├── helm/             # Kubernetes Helm chart
└── docs/             # Documentation source
```

## License

See [LICENSE](LICENSE) for details.
