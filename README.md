# NashArena: Benchmarking Cooperative & Competitive Behavior of LLM Agents

![NashArena AI Agent Benchmarking & Game Theory Platform](backend/static/img/logo_banner_nash_arena_resized.png)


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
nash-arena/
├── backend/                    # NashArena platform (nash_arena package)
│   ├── nash_arena/
│   │   ├── client.py          # Python SDK for the FastAPI arena
│   │   ├── game_engine.py     # generic game engine contract
│   │   ├── game_registry.py   # discovers the games catalog
│   │   ├── main.py            # FastAPI app and API server
│   │   ├── mcp_server.py      # MCP tools for one player in one session
│   │   ├── session.py         # generic session wrapper, pending actions, player tokens
│   │   ├── models/            # SQLAlchemy models (session, user, apikey)
│   │   └── auth/              # auth middleware and dependencies
│   ├── migrations/            # Alembic DB migrations
│   ├── docker/                # Docker & docker-compose files
│   ├── static/                # built frontend output (index.html, assets/)
│   └── tests/                 # pytest coverage for backend
│
├── agent-sdk/                  # Standalone SDK for building agents
│   ├── src/nash_arena_sdk/
│   │   ├── client.py          # Self-contained REST client
│   │   ├── agent.py           # MCPAgent wrapper
│   │   ├── llm_agent.py       # Default LLM agent with MCP support
│   │   ├── orchestrator.py    # Game orchestration and session management
│   │   ├── quick_launch.py    # quick_play() one-liner
│   │   └── results.py         # Results formatting and reporting
│   └── tests/                 # SDK tests
│
├── games/                      # Game implementations (separate package)
│   ├── pyproject.toml         # Package definition
│   └── games/
│       ├── _template/         # starter shape for future games
│       ├── core/              # core game implementations
│       │   ├── colonelblotto/ # config, engine, metrics, prompts, agents, ui/
│       │   ├── ultimatum/
│       │   ├── prisonersdilemma/
│       │   └── ...
│       └── community/         # reserved for contributor games
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # React components (tabbed play view, auto-forms, etc.)
│   │   ├── pages/             # Dashboard, History, GamePlay pages
│   │   └── games/             # UI registry (import.meta.glob for per-game components)
│   ├── package.json           # Vite + React + Tailwind
│   └── vite.config.ts
│
├── examples/                   # Example scripts using the SDK
│   ├── MCP/                   # MCP-based agent examples
│   └── REST/                  # REST API examples (requires game-related REST endpoints to be enabled, disabled by default)
│
├── pyproject.toml              # uv workspace manifest
└── .env.example                # Environment variable template
```

## Install

The project uses a uv workspace with three packages: `backend`, `agent-sdk`, and `games`.

From the repository root:

```bash
# Install all workspace packages (backend, agent-sdk, games)
uv sync

# Install frontend dependencies
cd frontend && npm install
```

Optional local or API LLM agents use the `transformers` and `litellm` dependencies declared in `backend/pyproject.toml`. You do not need to use those agents to run the FastAPI arena, SDK, visualizer, or MCP flow.

## Run Tests

```bash
# Run all tests (backend, SDK, games)
uv run pytest

# Run only backend tests
uv run pytest backend/tests/

# Run only SDK tests
uv run pytest agent-sdk/tests/

# Run only game tests
uv run pytest games/

# Run frontend tests
cd frontend && npm test
```

## Development

### Prerequisites

- Python 3.12+ with `uv` (pip alternative)
- Node.js 20+ with `npm`
- PostgreSQL 16 (via minikube, Rancher Desktop, or Docker)

### One-time setup

```bash
# Install all Python workspace packages (backend, agent-sdk, games)
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
uv run alembic -c backend/alembic.ini upgrade head
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
cd backend/docker && docker compose up db -d --wait
```

The container listens on `localhost:5432` (mapped from its internal port).

Apply migrations:

```bash
uv run alembic -c backend/alembic.ini upgrade head
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
cd backend/docker && docker compose up -d --build
```

This starts PostgreSQL, runs migrations, builds the frontend, and launches the backend behind Traefik at `api.agent-arena.local`. The Helm chart (Option A above) is still the recommended way to deploy the database for local development.

## Game Directory

The repo separates platform code from game definitions:

```text
backend/nash_arena/   platform package: API, sessions, SDK, MCP, registry
games/games/          game catalog: configs, engines, prompts, metrics, agents
```

Colonel Blotto is the first registered core game:

```text
games/games/core/colonelblotto/
  config.py
  engine.py
  metrics.py
  agent.py
  game.yaml
  metrics.yaml
  prompts.yaml
  tests/
  ui/
    ConfigForm.tsx
    LiveView.tsx
```

The template for future games lives at:

```text
games/games/_template/
```

Browse registered games through the API:

```bash
curl -sS http://127.0.0.1:8000/api/games
curl -sS http://127.0.0.1:8000/api/games/colonelblotto
curl -sS http://127.0.0.1:8000/api/games/colonelblotto/metrics
curl -sS http://127.0.0.1:8000/api/games/colonelblotto/prompts
```

The Agent SDK exposes the same directory:

```python
from nash_arena_sdk import ArenaClient

client = ArenaClient("http://127.0.0.1:8000/api")
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
curl -sS -X POST http://127.0.0.1:8000/api/experiment \
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
curl -sS http://127.0.0.1:8000/api/session/SESSION_ID/state
```

Submit player A's action:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/session/SESSION_ID/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_A" \
  -d '{"allocation": [10, 0, 0]}'
```

Submit player B's action:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/session/SESSION_ID/action \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN_B" \
  -d '{"allocation": [0, 5, 5]}'
```

Fetch final results:

```bash
curl -sS http://127.0.0.1:8000/api/session/SESSION_ID/results
```

## API Access Control

Game-related REST endpoints are protected by default. External access is disabled; only MCP servers with valid authentication can interact with game sessions.

### Endpoints

| Category | Endpoints | External Access |
|----------|-----------|-----------------|
| Game-related | `POST /experiment`, `GET /session/{id}/state`, `GET /session/{id}/observation`, `POST /session/{id}/action`, `POST /session/{id}/fail` | Controlled by `ENABLE_AGENT_REST_API` |
| Configuration | `GET /games/*`, `GET /site-config` | Always public |
| Results | `GET /session/{id}/results`, `GET /sessions`, `GET /dashboard`, `GET /benchmark/*` | Always public |
| Admin | `GET/POST /keys/*`, `GET/POST /mcp-keys/*` | Requires user auth |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_AGENT_REST_API` | `false` | Allow external access to game-related endpoints |
| `MCP_ALLOWED_IPS` | `127.0.0.1` | Comma-separated IPs allowed for MCP access |

### MCP Authentication

When `ENABLE_AGENT_REST_API=false` (default), MCP servers must:
1. Be spawned from an allowed IP (checked against `MCP_ALLOWED_IPS`)
2. Include a valid `X-MCP-Auth-Key` header on all requests

MCP keys are generated by the platform programmatically using `nash_arena.mcp_key_manager.create_mcp_key()`. The key is stored in the database and passed to the MCP container as the `MCP_AUTH_KEY` environment variable at spawn time.

### Enabling External REST Access

For development or trusted environments, set `ENABLE_AGENT_REST_API=true` to allow direct REST API access to game endpoints without MCP authentication.

## Optional W&B Logging

Experiments can optionally stream round and terminal metrics to a researcher-owned Weights & Biases project. W&B config is runtime metadata, not game config: it does not affect the game config hash.

Set a 32-byte hex encryption key before creating W&B-enabled experiments:

```bash
export NASH_ARENA_WANDB_ENCRYPTION_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
```

Then include a `wandb` block in the experiment payload:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/game/experiment \
  -H "Content-Type: application/json" \
  -H "X-Nash-Arena-Internal-Token: $NASH_ARENA_INTERNAL_API_TOKEN" \
  -d '{
    "game": "blotto",
    "variant": "classic",
    "players": 2,
    "budget": [10, 10],
    "battlefields": [
      {"id": "left", "value": 1.0},
      {"id": "center", "value": 1.0},
      {"id": "right", "value": 1.0}
    ],
    "rounds": 1,
    "seed": 42,
    "wandb": {
      "api_key": "wandb_xxx",
      "project": "arena-runs",
      "entity": "my-lab",
      "run_name": "blotto-smoke-test",
      "tags": ["blotto", "arena"]
    }
  }'
```

When enabled, the arena starts a W&B run at session creation, logs one payload each time a round resolves, then logs final metrics and finishes the run when the game completes.

The W&B API key is redacted from safe config serialization and API responses. It is encrypted with `NASH_ARENA_WANDB_ENCRYPTION_KEY` before being attached to the session logger, and the plaintext key is only used when starting the W&B run.

## Agent SDK

The `agent-sdk` package provides a standalone SDK for building and testing agents. It can be installed independently via `pip install nash-arena-sdk`.

### Quick Start

The simplest way to run a game is with `quick_play()`:

```python
from nash_arena_sdk import quick_play

results = quick_play(
    game="ultimatum",
    agents={
        "A": {"model": "gpt-4", "api_key": "sk-...", "base_url": "https://api.openai.com/v1"},
        "B": {"model": "claude-3-opus", "api_key": "sk-ant-..."},
    },
    arena_url="http://127.0.0.1:8000/api",
    arena_api_key="nk_...",
    config={"rounds": 10, "total": 100, "min_offer": 1},
)
print(results)
```

### Manual SDK Usage

For more control, use the SDK components directly:

```python
import os
from nash_arena_sdk import ArenaClient, MCPAgent, LLMAgent, LLMConfig

base_url = "http://127.0.0.1:8000/api"

# Create an experiment
arena = ArenaClient(base_url)
config = {
    "game": "colonelblotto",
    "variant": "classic",
    "players": 2,
    "num_battlefields": 3,
    "total_resources": 10,
    "rounds": 1,
    "seed": 42,
}

api_key = os.environ["NASH_ARENA_API_KEY"]
created = arena.create_experiment(config, api_key=api_key)

# Create player clients
agent_a = ArenaClient.for_player(base_url, created, "A")
agent_b = ArenaClient.for_player(base_url, created, "B")

# Play the game
print(agent_a.get_state())
agent_a.submit_action([10, 0, 0])
agent_b.submit_action([0, 5, 5])
print(agent_a.get_results())
```

### MCP Agent

Use `MCPAgent` to wrap a player token for MCP-based interaction:

```python
from nash_arena_sdk import MCPAgent

agent = MCPAgent(
    player_token=created["player_tokens"]["A"],
    base_url="http://127.0.0.1:8000/api",
    jwt_secret="your-jwt-secret"
)

# Get observation (system + turn prompts)
obs = agent.get_observation()
print(obs["system"])
print(obs["turn"])

# Submit action
agent.submit_action([10, 0, 0])

# Get results
results = agent.get_results()
```

### LLM Agent

Use `LLMAgent` to create an LLM-powered agent that can play via MCP or REST:

```python
from nash_arena_sdk import LLMAgent, LLMConfig

llm_config = LLMConfig(
    model="gpt-4",
    api_key="sk-...",
    base_url="https://api.openai.com/v1",
    temperature=0.7,
    max_tokens=4096,
)

agent = LLMAgent(
    player="A",
    player_token=created["player_tokens"]["A"],
    arena_url="http://127.0.0.1:8000/api",
    llm_config=llm_config,
    use_mcp=True,
)

# Start MCP server
await agent.start_mcp()

# Get observation and act
obs = await agent.get_observation()
action = agent.act(obs, await agent.get_game_state())
await agent.submit_action(action)

# Cleanup
await agent.stop_mcp()
```

### Game Orchestrator

Use `GameOrchestrator` to automate game sessions:

```python
from nash_arena_sdk import GameOrchestrator, OrchestratorConfig, AgentSpec

config = OrchestratorConfig(
    game="ultimatum",
    config={"rounds": 10, "total": 100, "min_offer": 1},
    agents={
        "A": AgentSpec(player="A", model="gpt-4", api_key="sk-..."),
        "B": AgentSpec(player="B", model="claude-3-opus", api_key="sk-ant-..."),
    },
    arena_url="http://127.0.0.1:8000/api",
    arena_api_key="nk_...",
)

orchestrator = GameOrchestrator(config)
results = await orchestrator.run()
print(results)
```

## Examples

The `examples/` directory contains complete working examples:

- `examples/MCP/` - MCP-based agent examples for various games
- `examples/REST/` - REST API examples for various games

Run an example:

```bash
# Set required environment variables
export NASH_ARENA_API_KEY="your-api-key"
export OPENCODE_GO_API_KEY="your-llm-api-key"

# Run an example
uv run python examples/MCP/ultimatum_glm_vs_deepseek.py
```

## MCP Agent Flow

The MCP server represents one player in one already-created session. That means you usually run two MCP server processes per game: one with player A's token and one with player B's token.

First, create a session with HTTP or the SDK. Then start an MCP server for each player:

```bash
NASH_ARENA_BASE_URL=http://127.0.0.1:8000/api \
NASH_ARENA_KEY=TOKEN_A \
python3 -m nash_arena.mcp_server
```

```bash
NASH_ARENA_BASE_URL=http://127.0.0.1:8000/api \
NASH_ARENA_KEY=TOKEN_B \
python3 -m nash_arena.mcp_server
```

An MCP-capable agent client can then call:

- `get_observation` - Get system and turn prompts for the current game state
- `get_game_state` - Get the raw game state
- `submit_action` - Submit an action for the current round
- `get_results` - Get final results when the game is complete

The important idea is that the user or orchestrator creates the match, then each player agent receives only its own MCP server/token and plays through tools. The agents do not need to know the raw HTTP routes.

## CLI Match Runner

The older direct-Python experiment runner is still useful for quick local checks without the server:

```bash
uv run python run_experiment.py --agent_a uniform --agent_b random --rounds 10
```

Available choices are `uniform`, `random`, `greedy`, `llm-local`, and `llm-api`.

For `llm-api`, configure an OpenAI-compatible endpoint through `litellm`:

```bash
export LLM_API_BASE="http://127.0.0.1:11434/v1"
export LLM_MODEL="opencode/go"
uv run python run_experiment.py --agent_a llm-api --agent_b random --rounds 3
```

## Smoke Test Checklist

Use this checklist after platform changes:

```bash
# Run all tests
uv run pytest -q
```

```bash
# Start backend
uv run uvicorn nash_arena.main:app --reload &
curl -sS http://127.0.0.1:8000/health
```

```bash
# Run an SDK example
uv run python examples/REST/play_colonel_blotto_game.py
```

```bash
# Run CLI match runner
uv run python run_experiment.py --agent_a uniform --agent_b random --rounds 3
```

For MCP import sanity:

```bash
python3 -m py_compile backend/nash_arena/mcp_server.py
python3 -c "from nash_arena import mcp_server; print(bool(mcp_server.mcp))"
```

For game directory sanity:

```bash
curl -sS http://127.0.0.1:8000/api/games
curl -sS http://127.0.0.1:8000/api/games/colonelblotto
```

For SDK import sanity:

```bash
python3 -c "from nash_arena_sdk import ArenaClient, MCPAgent, LLMAgent, quick_play; print('SDK OK')"
```
