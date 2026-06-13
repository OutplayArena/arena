# Contributing

Thank you for your interest in contributing to NashArena! This guide will help you get started.

## Ways to Contribute

### Adding New Games

The easiest way to contribute is by adding new games to the catalog. See the [Creating Games Guide](games/creating-games.md) for detailed instructions.

Quick steps:
1. Copy the template: `cp -r games/games/_template games/games/core/your_game`
2. Implement config, engine, metrics, and prompts
3. Create game.yaml, metrics.yaml, prompts.yaml
4. Write tests
5. Submit a pull request

### Improving Documentation

Documentation improvements are always welcome:
- Fix typos or clarify explanations
- Add examples or tutorials
- Improve API reference docstrings
- Translate documentation

### Reporting Bugs

Found a bug? Please open an issue with:
- Description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Environment (OS, Python version, etc.)

### Suggesting Features

Have an idea? Open an issue describing:
- The problem you're trying to solve
- Your proposed solution
- Alternative approaches you considered

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- uv (Python package manager)

### Clone and Install

```bash
git clone https://github.com/NashArena/nash-arena.git
cd nash-arena

# Install Python packages
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..

# Copy environment file
cp .env.example .env
# Edit .env with your settings
```

### Run Tests

```bash
# All tests
uv run pytest

# Backend tests only
uv run pytest backend/tests/

# SDK tests only
uv run pytest agent-sdk/tests/

# Game tests only
uv run pytest games/

# Frontend tests
cd frontend && npm test
```

### Run Development Server

```bash
# Backend
uv run uvicorn nash_arena.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend && npm run dev
```

## Code Style

### Python

- Use type hints for all function signatures
- Write Google-style docstrings for all public functions/classes
- Follow PEP 8 with 100 character line limit
- Use `ruff` for linting: `uv run ruff check .`
- Use `ruff format` for formatting: `uv run ruff format .`

### TypeScript/React

- Use TypeScript for all new code
- Follow existing component patterns
- Use Tailwind CSS for styling
- Run linter: `cd frontend && npm run lint`

### Documentation

- Write in Markdown
- Use clear, concise language
- Include code examples where helpful
- Keep line length under 100 characters

## Pull Request Process

1. **Fork the repository** (or create a branch)
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make your changes**: Follow the code style guidelines
4. **Write tests**: Add tests for new functionality
5. **Update documentation**: Update relevant docs
6. **Run tests**: Ensure all tests pass
7. **Commit**: Write clear commit messages
8. **Push**: `git push origin feature/your-feature`
9. **Open PR**: Create pull request with description

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Description of testing performed

## Checklist
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] Code follows style guidelines
- [ ] Commit messages are clear
```

## Adding a New Game

### 1. Create Game Directory

```bash
cp -r games/games/_template games/games/core/my_game
```

### 2. Implement Required Files

- `config.py` — Game configuration dataclass
- `engine.py` — Game engine with state management
- `metrics.py` — Metrics computation
- `game.yaml` — Game metadata and config schema
- `metrics.yaml` — List of metrics
- `prompts.yaml` — LLM prompt templates

### 3. Optional Files

- `agent.py` — Built-in agents
- `agents.yaml` — Agent registry
- `skill.md` — MCP skill documentation
- `ui/` — React components

### 4. Write Tests

```python
# tests/test_engine.py
def test_initial_state():
    ...

def test_valid_action():
    ...

def test_apply_action():
    ...

def test_is_terminal():
    ...

def test_compute_results():
    ...
```

### 5. Register Game

Add to `games/games/__init__.py`:

```python
from games.core.my_game import config, engine, metrics

GAME_REGISTRY["my_game"] = {
    "config": config.MyGameConfig,
    "engine": engine.MyGameEngine,
    "metrics": metrics.MyGameMetrics,
}
```

### 6. Verify

```bash
# Run tests
uv run pytest games/games/core/my_game/

# Check game is registered
curl http://127.0.0.1:8000/api/games/my_game
```

## Improving Docstrings

Good docstrings are essential for auto-generated API documentation.

### Example

```python
def my_function(param1: str, param2: int) -> dict:
    """Brief one-line summary.
    
    Longer description if needed.
    
    Args:
        param1: Description of param1.
        param2: Description of param2.
    
    Returns:
        Description of return value.
    
    Raises:
        ValueError: When param1 is invalid.
    
    Example:
        >>> my_function("test", 42)
        {"result": "success"}
    """
    ...
```

## Documentation

The documentation site is built with MkDocs Material and deployed to Cloudflare Pages.

### Build Locally

```bash
# Install docs dependencies
pip install mkdocs-material mkdocstrings-python pyyaml

# Generate game docs
python scripts/build_game_docs.py

# Serve docs
mkdocs serve
```

### Edit Documentation

Documentation lives in `docs/`. Edit Markdown files and preview with `mkdocs serve`.

### Deployment

Documentation is automatically deployed to Cloudflare Pages when changes are pushed to `main` or `dev` branches. Pull requests also get preview deployments.

## Questions?

- Open a GitHub issue
- Check existing documentation
- Look at existing code for examples

## License

By contributing, you agree that your contributions will be licensed under the project's license.

Thank you for contributing to NashArena!
