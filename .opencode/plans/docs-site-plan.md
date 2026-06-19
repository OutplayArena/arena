# OutplayLabs Arena Documentation Site - Execution Plan

## Overview
Build a beautiful documentation website using MkDocs Material that matches the frontend design system, with auto-generated API reference from Python docstrings and OpenAPI spec, auto-generated game catalog from YAML files, versioning via mike, and a blog for changelog/research updates.

## Tech Stack
- **Framework**: MkDocs Material 9.7.6
- **SDK API docs**: mkdocstrings-python (auto-generates from docstrings)
- **REST API docs**: Redoc embedded via HTML web component
- **Game catalog**: Custom build script (`scripts/build_game_docs.py`)
- **Versioning**: mike 2.2.0
- **Blog**: MkDocs Material built-in blog plugin
- **Deployment**: GitHub Pages + Docker self-hosted option

## Theme Configuration
Matches the frontend design system:
- **Primary accent**: Teal `#12a594` (light) / `#2dd4bf` (dark)
- **Background**: Warm off-white `#f6f5ef` (light) / Dark blue-black `#0b1014` (dark)
- **Surface**: `#ffffff` (light) / GitHub dark `#161b22` (dark)
- **Text**: `#263238` (light) / `#e6edf3` (dark)
- **Font**: Inter (text), JetBrains Mono (code)
- **Features**: Dark/light mode toggle, instant navigation, search, tabs

## Site Structure
```
docs/
├── index.md                          # Landing page
├── getting-started/
│   ├── installation.md
│   ├── quickstart.md
│   └── concepts.md
├── sdk/
│   ├── overview.md
│   ├── arena-client.md
│   ├── mcp-agent.md
│   ├── llm-agent.md
│   ├── orchestrator.md
│   ├── reasoning.md
│   └── api-reference.md             # Auto-generated via mkdocstrings
├── api/
│   ├── overview.md
│   ├── authentication.md
│   └── reference.md                 # Embedded Redoc from OpenAPI
├── games/
│   ├── overview.md
│   ├── catalog/                     # Auto-generated per-game pages
│   │   ├── colonelblotto.md
│   │   ├── prisonersdilemma.md
│   │   ├── ultimatum.md
│   │   ├── rockpaperscissors.md
│   │   ├── publicgoods.md
│   │   ├── centipede.md
│   │   ├── cournotduopoly.md
│   │   ├── staghunt.md
│   │   ├── battleofthesexes.md
│   │   └── texasholdem.md
│   ├── metrics.md                   # Auto-generated
│   ├── creating-games.md
│   └── prompts.md
├── mcp/
│   ├── overview.md
│   ├── gateway.md                   # Migrated from docs/MCP_GATEWAY.md
│   └── setup.md
├── deployment/
│   ├── docker.md
│   ├── kubernetes.md
│   └── configuration.md
├── examples/
│   ├── quickstart-mcp.md
│   ├── quickstart-rest.md
│   └── scenarios.md
├── blog/
│   └── posts/
│       └── alpha-release.md
├── contributing.md
└── stylesheets/
    └── extra.css                    # Custom theme colors
```

## Execution Phases

### Phase A: Foundation (parallel)

#### A1: Scaffold MkDocs
- Create `mkdocs.yml` with full configuration
- Create `docs/stylesheets/extra.css` with custom theme colors
- Create directory structure with placeholder files
- Copy brand assets from `frontend/public/img/` to `docs/img/`
- Verify `mkdocs serve` works locally

#### A2: Improve SDK Docstrings
Priority order:
1. **P0 - `client.py`** (`ArenaClient`): Add docstrings to class and all 12 methods
2. **P1 - `orchestrator.py`**: Add class docstrings, field docs on `AgentSpec` and `OrchestratorConfig`
3. **P1 - `llm_agent.py`**: Add class docstrings to `LLMConfig` and `LLMAgentConfig` dataclasses
4. **P2 - `reasoning.py`**: Add docstrings to enums (`ReasoningEffort`, `ReasoningStrategy`), helper functions
5. **P2 - `results.py`**: Expand one-liners with Args/Returns sections
6. **P2 - `agent.py`**: Add docstrings to `RESTAgent` methods

#### A3: Backend API Docstrings
Add `summary` and `description` to all 32 route handlers in `backend/outplaylabs_arena/main.py`:
- Health & catalog (7 endpoints)
- Experiment & session lifecycle (6 endpoints)
- Session history & dashboard (4 endpoints)
- API key management (5 endpoints)
- OAuth/authentication (7 endpoints)
- Benchmark/leaderboard (2 endpoints - already have docstrings)
- Site config (1 endpoint)

#### A4: Game Docs Build Script
Create `scripts/build_game_docs.py`:
- Reads all `games/games/core/*/game.yaml`
- Reads `metrics.yaml`, `agents.yaml`, `prompts.yaml` per game
- Generates:
  - `docs/games/catalog/<game>.md` - per-game reference pages
  - `docs/games/overview.md` - ontology taxonomy, comparison matrix
  - `docs/games/metrics.md` - cross-game metrics reference
- Run as pre-build step before `mkdocs build`

### Phase B: Content (after A, parallel)

#### B1: Write Manual Content
- **Getting Started**: installation, quickstart (quick_play example), concepts (ontology, sessions, tokens)
- **SDK Guides**: overview architecture, per-component guides with code examples
- **API**: overview, authentication model, access control
- **MCP**: overview, setup guide (migrate existing MCP_GATEWAY.md)
- **Deployment**: Docker Compose, Kubernetes/Helm, configuration reference
- **Examples**: curated MCP and REST examples with explanations
- **Contributing**: how to add games, code style, PR process

#### B2: Wire Up Auto-Generated Docs
- Configure mkdocstrings in `mkdocs.yml` for SDK API reference
- Create `docs/sdk/api-reference.md` with `::: outplaylabs_arena_sdk` directives
- Create `docs/api/reference.md` with embedded Redoc web component loading OpenAPI spec
- Test that auto-generated pages render correctly

#### B3: Blog Setup
- Configure blog plugin in `mkdocs.yml`
- Create `docs/blog/index.md`
- Write alpha release post in `docs/blog/posts/alpha-release.md`

### Phase C: Deployment & Polish

#### C1: GitHub Actions Workflow
Create `.github/workflows/docs.yml`:
- Trigger on push to `main` (docs/ or mkdocs.yml changes)
- Run `scripts/build_game_docs.py`
- Build docs with `mkdocs build`
- Deploy to `gh-pages` branch with `mike deploy`

#### C2: Docker Self-Hosted
Create `docs/Dockerfile`:
- Based on `squidfunk/mkdocs-material`
- Copy docs/, mkdocs.yml, scripts/
- Run build script, serve on port 8000

#### C3: Versioning
- Initialize mike: `mike deploy 0.1.0-alpha latest --push`
- Set default: `mike set-default latest --push`
- Document versioning workflow in contributing guide

## Content Strategy: Auto vs Manual

| Section | Auto-generated? | Source |
|---------|----------------|--------|
| SDK API reference | **Yes** (mkdocstrings) | Python docstrings in `agent-sdk/src/` |
| REST API reference | **Yes** (Redoc embed) | FastAPI's `/openapi.json` |
| Game catalog pages | **Yes** (build script) | `games/games/core/*/game.yaml` + related YAML |
| Game ontology overview | **Yes** (build script) | All `game.yaml` ontology fields |
| Metrics reference | **Yes** (build script) | All `metrics.yaml` files |
| Everything else | **Manual** | Hand-written Markdown |

## Dependencies

Add to root `pyproject.toml` or create `docs/requirements.txt`:
```
mkdocs-material>=9.7.0
mkdocstrings-python>=1.0.0
mike>=2.0.0
```

## Verification Checklist

- [ ] `mkdocs serve` runs without errors
- [ ] All auto-generated pages render correctly
- [ ] Dark/light mode toggle works
- [ ] Search indexes all content
- [ ] SDK API reference shows all classes/methods
- [ ] REST API reference loads OpenAPI spec
- [ ] Game catalog shows all 10 games
- [ ] Code examples have syntax highlighting and copy buttons
- [ ] Blog renders posts
- [ ] `mike deploy` creates versioned site
- [ ] GitHub Actions workflow deploys successfully
- [ ] Docker container serves docs correctly

## Estimated Effort

| Phase | Tasks | Est. Time |
|-------|-------|-----------|
| A1 | Scaffold | 30 min |
| A2 | SDK docstrings | 2-3 hours |
| A3 | Backend docstrings | 1-2 hours |
| A4 | Game docs script | 1-2 hours |
| B1 | Manual content | 4-6 hours |
| B2 | Wire up auto-docs | 30 min |
| B3 | Blog setup | 30 min |
| C1 | CI/CD | 30 min |
| C2 | Docker | 30 min |
| C3 | Versioning | 15 min |
| **Total** | | **10-15 hours** |

## Next Steps

1. Exit plan mode
2. Execute Phase A (parallel: A1, A2, A3, A4)
3. Execute Phase B (parallel: B1, B2, B3)
4. Execute Phase C (sequential: C1, C2, C3)
5. Verify all checklist items
6. Commit and push
