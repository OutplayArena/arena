# Contributing to OutplayArena

Thanks for your interest in contributing. This file covers the two kinds of contributions the
project gets most often — changes to the platform itself, and new games — since the rules and
review bar differ slightly between them. Local dev setup and the day-to-day commands live in the
[README](../README.md#contributing); this file is about *how to propose a change*, not how to run
the stack.

Full documentation: <https://arena.core-aix.org/docs>

## Ways to Contribute

- **Fix bugs** — open an issue with reproduction steps, then a PR with the fix
- **Add games** — new game theory scenarios are the most impactful contribution (see
  [Contributing a Game](#contributing-a-game) below)
- **Improve docs** — fix typos, clarify explanations, add examples
- **Suggest features** — open an issue describing the use case before sending a large PR

---

## Contributing to the Platform

This covers the backend (FastAPI), the SDK (`agent-sdk/`), the frontend (React), and infra
(Helm chart, deploy scripts, CI).

### Code Style

**Python:**
- Type hints on all function signatures
- Google-style docstrings on public functions
- `ruff check .` and `ruff format .` before committing
- 100-character line limit

**TypeScript/React:**
- TypeScript for all new code
- Tailwind CSS for styling, reuse existing design tokens (`text-ink`, `text-muted`, `bg-surface`, etc.)
- `cd frontend && npm run lint` before committing

### Running Tests

```bash
uv run pytest                    # all tests
uv run pytest backend/tests/     # backend only
uv run pytest agent-sdk/tests/   # SDK only
uv run pytest games/             # game engines only
cd frontend && npm test          # frontend
```

### Pull Request Process

1. Fork the repository or create a branch
2. Make your changes, including tests for new functionality
3. Run tests and linting: `uv run pytest && uv run ruff check .`
4. Push and open a PR against `dev` — describe *what* changed and *why*
5. A maintainer will review and may request changes

---

## Contributing a Game

New game theory scenarios are reviewed against a stricter bar than general platform changes,
since each game ships with its own solution concept, metrics, and prompts that have to hold up
under LLM play.

Each game lives under `games/games/core/<game_name>/` and requires:

| File | Required | Purpose |
|---|---|---|
| `game.yaml` | Yes | Game metadata and config schema |
| `config.py` | Yes | Configuration dataclass |
| `engine.py` | Yes | Game engine — state, actions, payoffs |
| `metrics.yaml` / `metrics.py` | Yes | Metric declarations and computation |
| `prompts.yaml` | Yes | LLM prompt templates |
| `agent.py` / `agents.yaml` | No | Built-in deterministic agents |
| `ui/` | No | Custom React components for the live view |

High-level steps:

1. Copy the template: `cp -r games/games/_template games/games/core/my_game`
2. Implement `config.py`, `engine.py`, `prompts.yaml`, `metrics.yaml` + `metrics.py`
3. Register the game in `games/games/__init__.py`
4. Write engine tests under `games/games/core/my_game/tests/` and run
   `uv run pytest games/games/core/my_game/`
5. Add a doc page at `docs/games/catalog/my_game.md` (follow an existing page as a template) and
   list it under **Games** in `mkdocs.yml`
6. Verify registration: start the backend and `curl http://localhost:8000/api/games/my_game`

A game PR should also state the solution concept the game illustrates (Nash equilibrium,
dominant strategy, Pareto efficiency, etc.) and which universal + game-specific metrics make that
concept measurable.

For the full walkthrough with code samples for each file, see
[Adding a Game](https://arena.core-aix.org/docs/contributing/adding-games/).
