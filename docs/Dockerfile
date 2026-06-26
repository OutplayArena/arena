# ──── Stage 1: build ─────────────────────────────────────────────────────────
# Use python:3.12-slim as the base so mkdocstrings can introspect the
# agent-sdk (which requires Python >=3.12). The squidfunk/mkdocs-material
# image ships Python 3.11 and needs the deadsnakes PPA to get 3.12; using
# python:3.12-slim is simpler and smaller.
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
      mkdocs-material \
      mkdocstrings[python] \
      pymdown-extensions \
      pyyaml

WORKDIR /docs

# Install SDK + games so mkdocstrings can introspect them
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

# ──── Stage 2: serve ─────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=builder /docs/site      /usr/share/nginx/html
COPY docs/nginx.conf                /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  # 127.0.0.1 (not localhost) on Alpine: musl's getent returns ::1 first,
  # but nginx only listens on IPv4, so the wget would fail.
  CMD wget -qO- http://127.0.0.1/health || exit 1
