# Blotto Agent Arena

Blotto Agent Arena is a small research platform for running Colonel Blotto games between agents. The project started as a single game simulator and now has the pieces you need for a reusable game arena:

- typed experiment configuration
- a deterministic game engine
- session state with per-player tokens
- metrics and final results
- a FastAPI server
- a browser visualizer
- a Python SDK
- an MCP server so LLM agents can play through tools

The current implementation is intentionally in-memory and lightweight. It is good for local experiments, demos, smoke tests, and learning the platform shape before adding persistence, queues, auth, or hosted deployment.

## Project Layout

```text
arena/
  client.py      Python SDK for the FastAPI arena
  game_engine.py generic game engine contract
  game_registry.py discovers the top-level games catalog
  main.py        FastAPI app and static visualizer server
  mcp_server.py  MCP tools for one player in one session
  session.py     generic session wrapper, pending actions, player tokens

legacy_blotto/
  legacy/reference package kept during the transition to arena/

games/
  _template/     starter shape for future games
  core/blotto/   first registered platform-maintained game:
                 config, engine, metrics, prompts, agents, tests
  community/     reserved for contributor games

static/
  index.html     browser visualizer shell
  app.js         visualizer client and demo agents
  style.css      visualizer styling

examples/
  play_blotto_game.py  minimal SDK example

tests/
  pytest coverage for config, engine, sessions, API, SDK, metrics, MCP

run_experiment.py      simple CLI match runner
planning/             planning notes for the broader platform
```

## Install

From the repository root:

```bash
cd ~/SciRes/blotto
python3 -m pip install -e .
```

Optional local or API LLM agents use the `transformers` and `litellm` dependencies declared in `pyproject.toml`. You do not need to use those agents to run the FastAPI arena, SDK, visualizer, or MCP flow.

## Run Tests

```bash
python3 -m pytest -q
```

This is the main safety check. It exercises the platform modules plus the web API and SDK.

## Run the FastAPI Arena

Start the server:

```bash
uvicorn arena.main:app --reload
```

Then open:

- visualizer: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- health check: http://127.0.0.1:8000/health
- game directory: http://127.0.0.1:8000/games

The browser visualizer currently runs simple client-side demo agents: `uniform`, `random`, and `greedy`. More serious LLM agents should connect through HTTP, the Python SDK, or MCP so each player can act as an independent client.

## Game Directory

The repo now separates platform code from game definitions:

```text
arena/   platform package: API, sessions, SDK, MCP, registry
games/   game catalog: configs, engines, prompts, metrics, agents
legacy_blotto/  legacy/reference package kept for comparison during the transition
```

Blotto is the first registered core game:

```text
games/core/blotto/
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
curl -sS http://127.0.0.1:8000/games/blotto
curl -sS http://127.0.0.1:8000/games/blotto/metrics
curl -sS http://127.0.0.1:8000/games/blotto/prompts
```

The Python SDK exposes the same directory:

```python
from arena.client import ArenaClient

client = ArenaClient("http://127.0.0.1:8000")
print(client.list_games())
print(client.get_game_details("blotto"))
print(client.get_game_metrics("blotto"))
print(client.get_game_prompts("blotto"))
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
python3 examples/play_blotto_game.py
```

Minimal SDK usage:

```python
from arena.client import ArenaClient
from games.core.blotto.config import BlottoExperimentConfig

base_url = "http://127.0.0.1:8000"

arena = ArenaClient(base_url)
config = BlottoExperimentConfig.classic(
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
python3 -m arena.mcp_server
```

```bash
ARENA_BASE_URL=http://127.0.0.1:8000 \
ARENA_SESSION_ID=SESSION_ID \
ARENA_SESSION_TOKEN=TOKEN_B \
python3 -m arena.mcp_server
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
python3 -m pytest -q
```

```bash
uvicorn arena.main:app --reload
curl -sS http://127.0.0.1:8000/health
```

```bash
python3 examples/play_blotto_game.py
```

```bash
python3 run_experiment.py --agent_a uniform --agent_b random --rounds 3
```

For MCP import sanity:

```bash
python3 -m py_compile arena/mcp_server.py
python3 -c "from arena import mcp_server; print(bool(mcp_server.mcp))"
```

For game directory sanity:

```bash
curl -sS http://127.0.0.1:8000/games
curl -sS http://127.0.0.1:8000/games/blotto
```
