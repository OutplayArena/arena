FROM squidfunk/mkdocs-material:latest

RUN pip install --no-cache-dir \
    mkdocstrings-python \
    mike \
    pyyaml

WORKDIR /docs

COPY agent-sdk/ /tmp/agent-sdk/
COPY games/ /tmp/games/
RUN pip install --no-cache-dir /tmp/agent-sdk/ /tmp/games/ && \
    rm -rf /tmp/agent-sdk /tmp/games

COPY mkdocs.yml /docs/mkdocs.yml
COPY docs/ /docs/docs/
COPY scripts/build_game_docs.py /docs/scripts/build_game_docs.py
COPY agent-sdk/src/ /docs/agent-sdk/src/
COPY games/games/ /docs/games/games/

RUN python /docs/scripts/build_game_docs.py

EXPOSE 8000

CMD ["mkdocs", "serve", "--dev-addr=0.0.0.0:8000"]
