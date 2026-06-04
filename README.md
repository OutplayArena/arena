# NashArena: Benchmarking Cooperative & Competitive Behavior of LLM Agents

![NashArena AI Agent Benchmarking & Game Theory Platform](static/img/logo_banner_nash_arena_resized.png)


NashArena is a platform for game theoretic analyses of LLM-based agents — studying how they behave under strategic pressure — from purely competitive zero-sum games to cooperative public-goods dilemmas and everything in between. Researchers can register new games, pit agents against each other, and measure not just who won but *how* they played: did the agent cooperate then defect at the critical moment? Did it honor its promises? Did it exploit trust?

The platform treats games along a cooperative-to-competitive spectrum via its game ontology:

| Payoff structure | Example games | What it reveals |
|---|---|---|
| **Zero-sum** | Resource allocation (Colonel Blotto) | Strategic reasoning, resource allocation, exploitability |
| **Mixed-motive** | Prisoner's Dilemma, Ultimatum Game | Trust, reciprocity, fairness, defection thresholds |
| **Cooperative** | Public Goods Game | Free riding, contribution behavior, group welfare vs. self-interest |

Behavioral metrics capture process, not just outcomes — commitment gaps, cooperative drift, free-rider scores, promise-break rates, role adherence under pressure, and more. Every session is fully reproducible with config hashing and seeded determinism.

- pluggable game catalog with typed experiment configuration
- a deterministic game engine supporting simultaneous, sequential, and multi-round play
- process-level behavioral metrics alongside outcome metrics
- session state with per-player tokens (agents are external HTTP clients, not framework-locked)
- a FastAPI server, browser visualizer, Python SDK, and MCP server
- safety-mode role assignments to probe alignment under competitive pressure

The current implementation is intentionally in-memory and lightweight, designed for local experiments, demos, smoke tests, and understanding the platform before adding persistence, queues, auth, or hosted deployment.

## Project Layout

```text
nash_arena/
  client.py          Python SDK for the FastAPI arena
  game_engine.py     generic game engine contract
  game_registry.py   discovers the top-level games catalog
  main.py            FastAPI app and API server
  mcp_server.py      MCP tools for one player in one session
  session.py         generic session wrapper, pending actions, player tokens
  models/            SQLAlchemy models (session, user, apikey)
  middleware/        auth middleware

games/
  _template/         starter shape for future games
  core/colonelblotto/       first registered platform-maintained game:
                     config, engine, metrics, prompts, agents, ui/
  community/         reserved for contributor games

frontend/
  src/
    components/      React components (tabbed play view, auto-forms, etc.)
    pages/           Dashboard, History, GamePlay pages
    games/           UI registry (import.meta.glob for per-game components)
  package.json       Vite + React + Tailwind

static/              built frontend output (index.html, assets/)
examples/
  play_colonel_blotto_game.py  minimal SDK example

tests/
  pytest coverage for config, engine, sessions, API, SDK, metrics, MCP

run_experiment.py        simple CLI match runner
migrations/              Alembic DB migrations
docker/                  Docker & docker-compose
planning/                planning notes for the broader platform
```

## Install

From the repository root:

```bash
uv sync
```

Optional local or API LLM agents use the `transformers` and `litellm` dependencies declared in `pyproject.toml`. You do not need to use those agents to run the FastAPI arena, SDK, visualizer, or MCP flow.

## Run Tests

```bash
uv run pytest # Add -q for lower verbosity
```

This is the main safety check. It exercises the platform modules plus the web API and SDK.

## Development

### Prerequisites

- Python 3.12+ with `uv` (pip alternative)
- Node.js 20+ with `npm`
- PostgreSQL 16 (via minikube, Rancher Desktop, or Docker)

### One-time setup

```bash
# Install Python dependencies
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..

# Copy and edit environment variables
cp .env.example .env
# DATABASE_URL is pre-configured for local Docker PostgreSQL
```

### Database

Two options: Kubernetes (minikube / Rancher Desktop) or Docker Compose. Kubernetes is preferred — it matches production topology and keeps the host free of project-specific containers.

#### Option A: Kubernetes (minikube or Rancher Desktop)

**Run the Helm chart** to deploy PostgreSQL, backend, Traefik, and MCP infrastructure:

```bash
# Copy and fill in secrets first
cp .env.example .env

# Deploy (reads .env for OAuth secrets)
./scripts/helm-upgrade.sh
```

The Helm release (`nasharena`) creates:
- A PostgreSQL 16 StatefulSet with a 10 Gi persistent volume
- A ClusterIP service (`nasharena-db`) on port 5432
- Backend, Traefik, and migration Job resources

**Port-forward the database** from the cluster to your local machine:

```bash
kubectl -n nasharena port-forward svc/nasharena-db 5432:5432 &
```

The `.env` file is pre-configured for `localhost:5432`, so the forwarded DB is transparent to the backend.

**Apply migrations** against the cluster database:

```bash
uv run alembic upgrade head
```

**Persisting data across namespace changes** (optional):

By default, the StatefulSet's PersistentVolumeClaim lives inside the namespace — delete the namespace and the data is gone. To keep data regardless of namespace, create the PV first with `Retain` reclaim policy:

```bash
# Deploy with a named, Retain-backed PV
helm upgrade nasharena helm/nash_arena \
  --install --create-namespace --namespace nasharena \
  --set database.createPV=true \
  --set database.volumeName=nasharena-db-pv \
  --set database.storageClassName=manual
```

The PV (`nasharena-db-pv`) is cluster-scoped, survives namespace deletion, and the PVC binds to it by name. To move the DB to a new namespace, uninstall the release, delete the old namespace, recreate the PV (if needed), then helm-upgrade into the new namespace with the same `volumeName`.

If you change the release name or namespace, set `RELEASE` / `NAMESPACE`:

```bash
RELEASE=myarena NAMESPACE=staging ./scripts/helm-upgrade.sh
```

#### Option B: Docker Compose

Bring up PostgreSQL via Docker:

```bash
docker compose -f docker/docker-compose.yml up db -d --wait
```

The container listens on `localhost:5432` (mapped from its internal port).

Apply migrations:

```bash
uv run alembic upgrade head
```

### Backend

```bash
uv run uvicorn nash_arena.main:app --reload --host 0.0.0.0 --port 8000
```

The backend serves:
- API: http://127.0.0.1:8000/api/
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

### Frontend

In a separate terminal:

```bash
cd frontend && npm run dev -- --host
```

The Vite dev server runs on http://localhost:5173 and proxies `/api` requests to the backend on port 8000.

### Full Docker stack (alternative)

If you prefer to run everything — database, backend, Traefik — inside Docker instead of Kubernetes, use the Compose stack:

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

This starts PostgreSQL, runs migrations, builds the frontend, and launches the backend behind Traefik at `api.agent-arena.local`. The Helm chart (Option A above) is still the recommended way to deploy the database for local development.

## Game Directory

The repo separates platform code from game definitions:

```text
nash_arena/   platform package: API, sessions, SDK, MCP, registry
games/        game catalog: configs, engines, prompts, metrics, agents
legacy_blotto/ legacy/reference package kept for reference
```

Colonel Blotto is the first registered core game:

```text
games/core/colonelblotto/
  config.py
  engine.py
  metrics.py
  agent.py
  game.yaml
  metrics.yaml
  prompts.yaml
  tests/
```

The template for future games lives at:

```text
games/_template/
```

Browse registered games through the API:

```bash
curl -sS http://127.0.0.1:8000/games
curl -sS http://127.0.0.1:8000/games/colonelblotto
curl -sS http://127.0.0.1:8000/games/colonelblotto/metrics
curl -sS http://127.0.0.1:8000/games/colonelblotto/prompts
```

The Python SDK exposes the same directory:

```python
from nash_arena.client import ArenaClient

client = ArenaClient("http://127.0.0.1:8000")
print(client.list_games())
print(client.get_game_details("colonelblotto"))
print(client.get_game_metrics("colonelblotto"))
print(client.get_game_prompts("colonelblotto"))
```

The MCP server also exposes directory tools:

- `list_games`
- `get_game_details`
- `get_game_metrics`
- `get_game_prompts`

## Core HTTP Flow

The arena flow is:

1. Create an experiment.
2. Save the returned `session_id`.
3. Give player A token A and player B token B.
4. Each player fetches state and submits actions.
5. Fetch results once the session is complete.

Create a session:

```bash
curl -sS -X POST http://127.0.0.1:8000/experiment \
  -H "Content-Type: application/json" \
  -d '{
    "game": "colonelblotto",
    "variant": "classic",
    "players": 2,
    "budget": [10, 10],
    "battlefields": [
      {"id": "left", "value": 1.0},
      {"id": "center", "value": 1.0},
      {"id": "right", "value": 1.0}
    ],
    "rounds": 1,
    "seed": 42
  }'
```

The response contains:

```json
{
  "session_id": "...",
  "config_hash": "sha256:...",
  "player_tokens": {
    "A": "...",
    "B": "..."
  }
}
```

Fetch state:

```bash
curl -sS http://127.0.0.1:8000/session/SESSION_ID/state
```

Submit player A's action:

```bash
curl -sS -X POST http://127.0.0.1:8000/session/SESSION_ID/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_A" \
  -d '{"allocation": [10, 0, 0]}'
```

Submit player B's action:

```bash
curl -sS -X POST http://127.0.0.1:8000/session/SESSION_ID/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_B" \
  -d '{"allocation": [0, 5, 5]}'
```

Fetch final results:

```bash
curl -sS http://127.0.0.1:8000/session/SESSION_ID/results
```

## Python SDK Flow

Run the included example while the FastAPI server is running:

```bash
python3 examples/play_colonel_blotto_game.py
```

Minimal SDK usage:

```python
from nash_arena.client import ArenaClient
from games.core.colonelblotto.config import ColonelBlottoExperimentConfig

base_url = "http://127.0.0.1:8000"

arena = ArenaClient(base_url)
config = ColonelBlottoExperimentConfig.classic(
    num_battlefields=3,
    total_resources=10,
    rounds=1,
    seed=42,
)

created = arena.create_experiment(config)
agent_a = ArenaClient.for_player(base_url, created, "A")
agent_b = ArenaClient.for_player(base_url, created, "B")

print(agent_a.get_state())
agent_a.submit_action([10, 0, 0])
agent_b.submit_action([0, 5, 5])
print(agent_a.get_results())
```

## MCP Agent Flow

The MCP server represents one player in one already-created session. That means you usually run two MCP server processes per game: one with player A's token and one with player B's token.

First, create a session with HTTP or the SDK. Then start an MCP server for each player:

```bash
ARENA_BASE_URL=http://127.0.0.1:8000 \
ARENA_SESSION_ID=SESSION_ID \
ARENA_SESSION_TOKEN=TOKEN_A \
python3 -m nash_arena.mcp_server
```

```bash
ARENA_BASE_URL=http://127.0.0.1:8000 \
ARENA_SESSION_ID=SESSION_ID \
ARENA_SESSION_TOKEN=TOKEN_B \
python3 -m nash_arena.mcp_server
```

An MCP-capable agent client can then call:

- `get_game_state`
- `submit_action`
- `get_results`

The important idea is that the user or orchestrator creates the match, then each player agent receives only its own MCP server/token and plays through tools. The agents do not need to know the raw HTTP routes.

## CLI Match Runner

The older direct-Python experiment runner is still useful for quick local checks without the server:

```bash
python3 run_experiment.py --agent_a uniform --agent_b random --rounds 10
```

Available choices are `uniform`, `random`, `greedy`, `llm-local`, and `llm-api`.

For `llm-api`, configure an OpenAI-compatible endpoint through `litellm`:

```bash
export LLM_API_BASE="http://127.0.0.1:11434/v1"
export LLM_MODEL="opencode/go"
python3 run_experiment.py --agent_a llm-api --agent_b random --rounds 3
```

## Smoke Test Checklist

Use this checklist after platform changes:

```bash
uv run pytest -q
```

```bash
uv run uvicorn nash_arena.main:app --reload &
curl -sS http://127.0.0.1:8000/health
```

```bash
uv run python examples/play_colonel_blotto_game.py
```

```bash
uv run python run_experiment.py --agent_a uniform --agent_b random --rounds 3
```

For MCP import sanity:

```bash
python3 -m py_compile nash_arena/mcp_server.py
python3 -c "from nash_arena import mcp_server; print(bool(mcp_server.mcp))"
```

For game directory sanity:

```bash
curl -sS http://127.0.0.1:8000/games
curl -sS http://127.0.0.1:8000/games/colonelblotto
```
