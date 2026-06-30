# Self-Hosting

Run OutplayArena on your own infrastructure. Choose the deployment method that matches your scale and complexity needs.

## Deployment Options

=== "Docker Compose (recommended for most)"

    The simplest way to run OutplayArena. One command brings up the full stack: backend, PostgreSQL, Redis, and Traefik reverse proxy with automatic TLS. Production runs it as a single-node Docker Swarm stack so releases roll out with zero downtime — see [Continuous deployment](single-vps.md#continuous-deployment).

    **Best for:** Small teams, single-server deployments, quick setup.

    **Docker images:** Pre-built and published on Docker Hub:
    - `her3ert/outplayarena-backend:TAG` — FastAPI backend + React frontend
    - `her3ert/outplayarena-mcp:TAG` — MCP server

    [Docker Compose setup →](docker.md)

=== "Kubernetes / Helm"

    A Helm chart is included for production Kubernetes deployments. Supports horizontal autoscaling for the backend, StatefulSets for PostgreSQL and Redis, and per-session MCP pod management.

    **Best for:** Production deployments needing autoscaling, rolling updates, and managed infrastructure.

    [Kubernetes & Helm setup →](kubernetes.md)

=== "Single VPS"

    Step-by-step guide for a single server deployment with Traefik handling TLS and routing. Suitable for self-hosted instances that don't need Kubernetes.

    [Single VPS setup →](single-vps.md)

## What Gets Deployed

All deployment methods run the same components:

| Component | Description |
|---|---|
| **Backend** | FastAPI server — API, game engine, session management, serves frontend |
| **Frontend** | React SPA — embedded in the backend Docker image |
| **PostgreSQL 16** | Sessions, users, API keys, game history |
| **Redis 7** | Pub/Sub for real-time game state updates |
| **Traefik** | Reverse proxy with Let's Encrypt TLS |
| **MCP Server** | Always-on MCP server process (Kubernetes runs it as a multi-replica Deployment) |

## Before You Start

1. **[Environment Configuration](configuration.md)** — review all required and optional variables before deploying
2. **[Database Migrations](migrations.md)** — understand how migrations work; run them before starting the backend
3. **Choose your OAuth provider** — GitHub or Google OAuth is required for user login (or local dev mode without OAuth)

## Image Tags

Find available release tags at [hub.docker.com/r/her3ert/outplayarena-backend](https://hub.docker.com/r/her3ert/outplayarena-backend/tags).

Pin to a specific release (e.g. `v0.1.0`) for stability. Use `latest` to track the rolling release.
