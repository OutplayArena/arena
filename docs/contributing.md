# Contributing

Thank you for your interest in contributing to OutplayArena! This section covers setting up a local development environment and the contribution workflow.

## Ways to Contribute

- **Fix bugs** — open an issue with reproduction steps, then a PR with the fix
- **Add games** — new game theory scenarios are the most impactful contribution (see [Adding Games](contributing/adding-games.md))
- **Improve docs** — fix typos, clarify explanations, add examples
- **Suggest features** — open an issue describing the use case

## Local Development Setup

Choose the track that matches your workflow:

<div class="grid cards" markdown>

-   **Docker Compose (simpler)**

    ---

    Spin up PostgreSQL and Redis in Docker; run the backend and frontend directly on your machine. No Kubernetes required.

    Best for: Most feature development, backend changes, game development.

    [:octicons-arrow-right-24: Docker Compose setup](contributing/docker-compose.md)

-   **Minikube (full cluster)**

    ---

    Deploy the complete stack in a local Kubernetes cluster, matching the production environment. Frontend and backend run outside the cluster for hot-reload.

    Best for: MCP development, Helm chart changes, production parity.

    [:octicons-arrow-right-24: Minikube setup](contributing/minikube.md)

</div>

## Code Style

**Python:**
- Type hints on all function signatures
- Google-style docstrings on public functions
- `ruff check .` and `ruff format .` before committing
- 100-character line limit

**TypeScript/React:**
- TypeScript for all new code
- Tailwind CSS for styling
- `cd frontend && npm run lint` before committing

## Running Tests

```bash
# All tests
uv run pytest

# Backend only
uv run pytest -m backend

# SDK only
uv run pytest -m sdk

# Game logic only
uv run pytest -m games

# Frontend tests
cd frontend && npm test
```

## Pull Request Process

1. Fork the repository or create a branch
2. Make your changes (include tests for new functionality)
3. Run tests and linting: `uv run pytest && uv run ruff check .`
4. Push and open a PR — describe *what* changed and *why*
5. A maintainer will review and may request changes

## Other Topics

- [Adding Games](contributing/adding-games.md) — how to implement a new game theory scenario
- [Docs Development](contributing/docs.md) — how to preview and edit documentation locally
