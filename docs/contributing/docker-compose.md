# Local Dev with Docker Compose

This track runs PostgreSQL and Redis in Docker containers while the backend and frontend run directly on your machine. It's the fastest way to get started with development.

!!! note
    This uses `backend/docker/docker-compose.yml` with plain `docker compose` — separate from the production stack at `deploy/docker-compose.yml`, which runs as a Docker Swarm service for zero-downtime releases (see [Single VPS](../deployment/single-vps.md)). Local dev doesn't need Swarm; `docker compose` is all you need here.

!!! note
    MCP container spawning is not available in this mode (it requires a Docker-in-Docker or Kubernetes setup). Use REST transport for local agent development. For full MCP development, use the [Minikube track](minikube.md).

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker and Docker Compose v2
- [uv](https://docs.astral.sh/uv/) Python package manager

## Setup

### 1. Clone and Configure

```bash
git clone https://github.com/OutplayArena/arena.git
cd arena

cp .env.example .env
# The defaults in .env.example work for local development — no changes needed
```

### 2. Install Dependencies

```bash
# Install Python packages (backend, SDK, games)
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 3. Start the Database and Redis

```bash
cd backend/docker
docker compose up db redis -d --wait
cd ../..
```

This starts:
- PostgreSQL 16 on `localhost:5432`
- Redis 7 on `localhost:6379`

### 4. Run Migrations

```bash
uv run alembic -c backend/alembic.ini upgrade head
```

### 5. Start the Backend

In one terminal:

```bash
uv run uvicorn arena.main:app --reload --host 0.0.0.0 --port 8000
```

The backend is now at `http://localhost:8000`. The Swagger UI is at `http://localhost:8000/docs`.

### 6. Start the Frontend

In a second terminal:

```bash
cd frontend
npm run dev
```

The frontend is at `http://localhost:5173`. Vite proxies `/api/*` to `localhost:8000` automatically.

## Development Workflow

### Backend Changes

The backend runs with `--reload`, so changes to Python files in `backend/arena/` take effect immediately.

### Frontend Changes

Vite's HMR updates the browser automatically on file saves.

### Adding a Database Migration

After changing SQLAlchemy models:

```bash
uv run alembic -c backend/alembic.ini revision \
  --autogenerate -m "describe_your_change"

# Review the generated file in backend/migrations/versions/
# Then apply it:
uv run alembic -c backend/alembic.ini upgrade head
```

### Running Tests

```bash
# All tests (requires DB to be running)
uv run pytest

# Backend tests only
uv run pytest -m backend

# SDK tests (no DB required)
uv run pytest -m sdk

# Frontend tests
cd frontend && npm test
```

## Stopping

```bash
# Stop the Docker services
cd backend/docker && docker compose down

# Or stop everything including volumes (reset DB)
docker compose down -v
```

## Troubleshooting

**Port 5432 already in use:** Another PostgreSQL instance is running locally. Stop it or change the port in `docker-compose.yml` and `DATABASE_URL` in `.env`.

**Backend can't connect to DB:** Make sure the Docker containers are running (`docker compose ps`) and migrations have been applied.

**Frontend can't reach the API:** Ensure the backend is running on port 8000. The Vite proxy config in `frontend/vite.config.ts` points to `localhost:8000` by default.
