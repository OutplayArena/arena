"""Regression tests for the SPA fallback on frontend reloads.

Reloading a client-side route (e.g. /dashboard) must serve index.html so
React Router can resolve it, while genuine unmatched /api routes must keep
returning a JSON 404. See main.py's `spa_fallback` exception handler.
"""
import importlib
import os

import pytest
from fastapi.testclient import TestClient

import arena.main


@pytest.fixture()
def app():
    """Reload arena.main with a real "/api" prefix for this test module.

    arena.main's ``app`` is a process-wide singleton, and its routes are
    baked in at import/reload time from the API_PREFIX env var. Flipping
    the prefix and reloading without restoring it afterward would leak
    into every other test file collected in the same session (they all
    assume the "" prefix set by the root conftest.py). Doing it in a
    fixture confines the mutation to this module's own test run.
    """
    original_prefix = os.environ.get("API_PREFIX")
    os.environ["API_PREFIX"] = "/api"
    importlib.reload(arena.main)
    try:
        yield arena.main.app
    finally:
        if original_prefix is None:
            os.environ.pop("API_PREFIX", None)
        else:
            os.environ["API_PREFIX"] = original_prefix
        importlib.reload(arena.main)


def test_unmatched_frontend_route_serves_index_html(app):
    client = TestClient(app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "OutplayArena" in response.text


def test_unmatched_api_route_still_returns_json_404(app):
    client = TestClient(app)

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
