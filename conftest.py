import os

os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")
# arena.main's lifespan refuses to start with the default JWT_SECRET. Use a
# non-default value for the test process; production must override this.
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-the-insecure-default")
os.environ.setdefault("ALLOW_INSECURE_JWT_SECRET", "1")


def pytest_collection_modifyitems(config, items):
    """Auto-tag collected tests with a category marker based on file path.

    Categories:
      - backend: tests under backend/tests/ (the FastAPI backend)
      - sdk:     tests under agent-sdk/tests/ (the Python SDK)
      - games:   tests under games/ (the game engines; also tagged backend)

    The "games" category is a sub-category of "backend" — games tests are
    exercised by the backend's game registry, so they count toward backend
    coverage but can also be run/filtered independently.

    Run a single category with `uv run pytest -m backend` or `-m sdk`.
    Combine with `-m "backend and not games"` to skip games, etc.
    """
    # Use config.rootdir so the tagging works regardless of CWD.
    root = str(config.rootdir)

    def _subdir(name: str) -> str:
        return os.path.normpath(os.path.join(root, name))

    backend_root = _subdir(os.path.join("backend", "tests"))
    sdk_root = _subdir(os.path.join("agent-sdk", "tests"))
    games_root = _subdir("games")

    for item in items:
        path = os.path.normpath(str(item.fspath))
        if path.startswith(backend_root):
            item.add_marker("backend")
        elif path.startswith(sdk_root):
            item.add_marker("sdk")
        elif path.startswith(games_root):
            item.add_marker("games")
            item.add_marker("backend")  # games are part of the backend
