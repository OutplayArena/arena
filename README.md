# NashArena: Benchmarking Cooperative & Competitive Behavior of LLM Agents

NashArena is a platform for game theoretic analyses of LLM-based agents — studying how they behave under strategic pressure, from zero-sum games to cooperative dilemmas.

## Documentation

**Full documentation: https://nash-arena-docs.pages.dev**

- [SDK Guide](https://nash-arena-docs.pages.dev/sdk/overview/) — Build agents with the Python SDK
- [Game Catalog](https://nash-arena-docs.pages.dev/games/overview/) — 10 game theory scenarios
- [API Reference](https://nash-arena-docs.pages.dev/api/overview/) — REST and MCP APIs
- [Deployment](https://nash-arena-docs.pages.dev/deployment/docker/) — Docker and Kubernetes
- [Contributing](https://nash-arena-docs.pages.dev/contributing/) — How to contribute

## SDK Quickstart

Install the SDK:

```bash
pip install nash-arena-sdk
```

Run your first game:

```python
from nash_arena_sdk import quick_play

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

For more examples and advanced usage, see the [SDK documentation](https://nash-arena-docs.pages.dev/sdk/overview/).

## Deployment

### Docker (Quick Start)

```bash
git clone https://github.com/NashArena/nash-arena.git
cd nash-arena

cp .env.example .env
# Edit .env with your settings

cd backend/docker
docker compose up -d
```

Access the platform at http://localhost:8000

For full Docker deployment details, see [Docker Deployment](https://nash-arena-docs.pages.dev/deployment/docker/).

### Kubernetes

For production deployments with Kubernetes and Helm, see [Kubernetes Deployment](https://nash-arena-docs.pages.dev/deployment/kubernetes/).

## Development

### Prerequisites

- Python 3.12+ with `uv`
- Node.js 20+ with `npm`
- PostgreSQL 16 (Docker or Kubernetes)

### Setup

```bash
# Install Python packages
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..

# Copy environment file
cp .env.example .env
```

### Database

**Option A: Docker** (recommended for local dev)

```bash
cd backend/docker && docker compose up db -d --wait
uv run alembic -c backend/alembic.ini upgrade head
```

**Option B: Kubernetes**

See [Kubernetes Deployment](https://nash-arena-docs.pages.dev/deployment/kubernetes/) for Helm chart instructions.

### Run Backend

```bash
uv run uvicorn nash_arena.main:app --reload --host 0.0.0.0 --port 8000
```

Backend serves:
- API: http://127.0.0.1:8000/api/
- Swagger UI: http://127.0.0.1:8000/docs
- Frontend: http://127.0.0.1:8000/

### Run Frontend (Dev Mode)

```bash
cd frontend && npm run dev
```

Vite dev server runs on http://localhost:5173 with hot reload.

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

For more development details, see [Contributing](https://nash-arena-docs.pages.dev/contributing/).

## Project Structure

```
nash-arena/
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
