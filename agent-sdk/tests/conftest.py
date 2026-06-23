"""Conftest for the agent-sdk tests.

Mirrors the auto-tagging in the root conftest so the `backend` and `sdk`
markers work regardless of which directory pytest is invoked from.
"""
import os


def pytest_collection_modifyitems(config, items):
    root = str(config.rootdir)
    sdk_root = os.path.normpath(os.path.join(root, "tests"))
    backend_root = os.path.normpath(os.path.join(root, "..", "backend", "tests"))
    games_root = os.path.normpath(os.path.join(root, "..", "games"))

    for item in items:
        path = os.path.normpath(str(item.fspath))
        if path.startswith(sdk_root):
            item.add_marker("sdk")
        elif path.startswith(backend_root):
            item.add_marker("backend")
        elif path.startswith(games_root):
            item.add_marker("games")
            item.add_marker("backend")
