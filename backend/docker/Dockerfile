# ──── Stage 1: build docs ────────────────────────────────────────────────────
# Mirrors docs/Dockerfile builder stage. The mkdocs output is copied into
# backend/static/docs/ so /docs/* is served by FastAPI's StaticFiles — no
# separate docs container or Traefik route needed.
FROM python:3.12-slim AS docs-builder

# Install stable mkdocs tooling first — this layer is cache-stable across
# version bumps because it doesn't depend on SDK_VERSION at all.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
      mkdocs-material \
      mkdocstrings[python] \
      pymdown-extensions \
      pyyaml

WORKDIR /docs

COPY agent-sdk/ /tmp/agent-sdk/
COPY games/     /tmp/games/

# ARG/ENV placed here (after stable tooling install and COPY) so the pip
# install above remains cache-stable across version bumps. hatch-vcs needs
# SETUPTOOLS_SCM_PRETEND_VERSION set before `pip install ./agent-sdk` because
# the .git history is not shipped in the build context.
ARG SDK_VERSION=0.0.0+unknown
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$SDK_VERSION

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
# ARG/ENV placed here (after all COPYs) so that COPY layers above remain
# cache-stable across version bumps. hatch-vcs needs this env var set
# before pip install so the correct version string is baked into the wheel.
ARG SDK_VERSION=0.0.0+unknown
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$SDK_VERSION
RUN pip install --no-cache-dir ./agent-sdk && pip install --no-cache-dir ./games && pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "arena.main:app", "--host", "0.0.0.0", "--port", "8000"]
