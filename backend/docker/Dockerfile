# ──── Stage 1: build docs ────────────────────────────────────────────────────
# Mirrors docs/Dockerfile builder stage. The mkdocs output is copied into
# backend/static/docs/ so /docs/* is served by FastAPI's StaticFiles — no
# separate docs container or Traefik route needed.
FROM python:3.12-slim AS docs-builder

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
      mkdocs-material \
      mkdocstrings[python] \
      pymdown-extensions \
      pyyaml

WORKDIR /docs

COPY agent-sdk/ /tmp/agent-sdk/
COPY games/     /tmp/games/
RUN pip install --no-cache-dir /tmp/agent-sdk/ /tmp/games/ && \
    rm -rf /tmp/agent-sdk /tmp/games

COPY mkdocs.yml                     /docs/mkdocs.yml
COPY docs/                          /docs/docs/
COPY scripts/build_game_docs.py     /docs/scripts/build_game_docs.py
COPY agent-sdk/src/                 /docs/agent-sdk/src/
COPY games/games/                   /docs/games/games/

RUN python /docs/scripts/build_game_docs.py
RUN mkdocs build --strict

# ──── Stage 2: build frontend ────────────────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY games/ ../games/
RUN npm run build

# ──── Stage 3: final image ───────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app
COPY agent-sdk/pyproject.toml agent-sdk/pyproject.toml
COPY agent-sdk/README.md agent-sdk/README.md
COPY agent-sdk/src/ agent-sdk/src/
COPY backend/pyproject.toml pyproject.toml
COPY README.md ../README.md
COPY backend/arena/ arena/
COPY games/ games/
COPY backend/migrations/ migrations/
COPY backend/alembic.ini ./
COPY frontend/site.yaml site.yaml
# React SPA (built to backend/static/ by vite)
COPY --from=frontend /backend/static/ static/
# mkdocs static site served at /docs/ by FastAPI StaticFiles
COPY --from=docs-builder /docs/site/ static/docs/
RUN pip install --no-cache-dir ./agent-sdk && pip install --no-cache-dir ./games && pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "arena.main:app", "--host", "0.0.0.0", "--port", "8000"]
