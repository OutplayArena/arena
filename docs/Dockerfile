# ──── Stage 1: build ─────────────────────────────────────────────────────────
FROM squidfunk/mkdocs-material:9 AS builder

RUN pip install --no-cache-dir \
    mkdocstrings-python \
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
RUN mkdocs build

# ──── Stage 2: serve ─────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=builder /docs/site      /usr/share/nginx/html
COPY docs/nginx.conf                /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost/health || exit 1
