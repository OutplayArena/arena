"""Tests for the global exception handler (arena.error_handler).

The handler is the last line of defence: every unhandled exception
that reaches FastAPI is tagged with a UUID, the full traceback is
persisted to ``error_logs``, and the response shows the UUID plus a
link to a prefilled GitHub issue. We never echo the traceback to
the user.

These tests use a ``TestClient`` with a route that deliberately
raises, plus a tiny in-memory stand-in for the DB session so we can
assert the row that was persisted.
"""
from __future__ import annotations

import importlib
import os
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Make sure the env is set the way main.py expects before any
# arena.* import runs. Mirrors the other backend test modules.
os.environ.setdefault("API_PREFIX", "")
os.environ.setdefault("ENABLE_AGENT_REST_API", "true")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GITHUB_CLIENT_ID", "")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")


class _FakeSession:
    """Stand-in for :class:`AsyncSession` that captures added rows.

    Implements just enough of the async-session surface for
    ``_persist_error_log``: ``add()`` records the row, ``commit()``
    resolves a coroutine.
    """

    def __init__(self):
        self.added: list = []
        self.committed = 0

    def add(self, row):
        self.added.append(row)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def commit(self):
        self.committed += 1


def _build_app_with_boom_route() -> tuple[FastAPI, _FakeSession]:
    """Build a tiny FastAPI app with one route that always raises.

    Returns the app and a fresh fake session that the patched
    ``_persist_error_log`` will write to.
    """
    fake = _FakeSession()

    from arena.error_handler import register_error_handlers

    app = FastAPI(title="error-handler-test")
    register_error_handlers(app)

    @app.get("/boom")
    async def boom():  # pragma: no cover - exercised via TestClient
        raise RuntimeError("kaboom")

    @app.get("/api/boom")
    async def api_boom():  # pragma: no cover
        raise ValueError("api boom")

    @app.get("/ok")
    async def ok():  # pragma: no cover
        return {"ok": True}

    @asynccontextmanager
    async def _lifespan(_):
        yield

    # Replace the lifespan with a no-op so we don't try to run
    # Alembic migrations or connect to Redis during the test.
    app.router.lifespan_context = _lifespan

    return app, fake


def test_unhandled_exception_returns_uuid_in_html_response():
    app, fake = _build_app_with_boom_route()
    client = TestClient(app, raise_server_exceptions=False)

    with patch("arena.db.async_session") as session_factory:
        session_factory.return_value = fake
        response = client.get("/boom")

    assert response.status_code == 500
    assert "text/html" in response.headers["content-type"]
    body = response.text
    # UUID appears as a 36-char string with dashes; assert the page
    # embeds both a stable label and the link.
    assert "Error ID" in body
    assert "Report this on GitHub" in body
    # The UUID format is 8-4-4-4-12 hex with dashes; 36 chars total.
    import re

    m = re.search(r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b", body)
    assert m is not None, f"expected a UUID in the HTML body, got: {body!r}"


def test_unhandled_exception_returns_uuid_in_json_response_for_api():
    app, fake = _build_app_with_boom_route()
    client = TestClient(app, raise_server_exceptions=False)

    with patch("arena.db.async_session") as session_factory:
        session_factory.return_value = fake
        response = client.get(
            "/api/boom", headers={"Accept": "application/json"}
        )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["error"] == "internal_server_error"
    assert payload["request"] == {"method": "GET", "path": "/api/boom"}
    # UUID string in the response.
    import uuid

    parsed = uuid.UUID(payload["error_id"])
    assert parsed.version == 4
    # GitHub issue link points at the right repo with the UUID
    # prefilled in the title.
    assert "github.com/OutplayArena/arena/issues/new" in payload["report_url"]
    assert str(parsed) in payload["report_url"]


def test_handler_persists_error_log_row():
    app, fake = _build_app_with_boom_route()
    client = TestClient(app, raise_server_exceptions=False)

    with patch("arena.db.async_session") as session_factory:
        session_factory.return_value = fake
        client.get("/boom")

    assert len(fake.added) == 1, "expected exactly one error row"
    row = fake.added[0]
    # Surface the UUID to the user *and* to the DB row, so the
    # maintainer can grep the table by the ID in the issue title.
    import uuid

    assert isinstance(row.id, uuid.UUID)
    assert row.method == "GET"
    assert row.path == "/boom"
    assert row.exception_type == "RuntimeError"
    # The traceback was formatted into a string (no newlines collapsed).
    assert "RuntimeError: kaboom" in row.traceback
    assert "Traceback" in row.traceback
    # The DB write was committed.
    assert fake.committed == 1


def test_handler_swallows_persist_failures():
    """If the error_logs write itself fails, the user still gets a UUID.

    Defensive: a missing table, broken DB, or any other persistence
    failure shouldn't take the user-facing 500 with it. The error
    falls back to a log line (the operator still gets the traceback
    in container logs).
    """
    app, _ = _build_app_with_boom_route()
    client = TestClient(app, raise_server_exceptions=False)

    with patch("arena.db.async_session") as session_factory:
        # Make ``async with async_session() as session`` blow up.
        session_factory.side_effect = RuntimeError("db down")
        response = client.get("/boom")

    assert response.status_code == 500
    assert "Error ID" in response.text


def test_handler_distinguishes_html_vs_json():
    app, fake = _build_app_with_boom_route()
    client = TestClient(app, raise_server_exceptions=False)

    with patch("arena.db.async_session") as session_factory:
        session_factory.return_value = fake

        # Browser-like Accept header: text/html wins → HTML page.
        r_html = client.get("/boom", headers={"Accept": "text/html,application/xhtml+xml"})
        assert r_html.status_code == 500
        assert "text/html" in r_html.headers["content-type"]

        # API client: explicit JSON → JSON body.
        r_json = client.get(
            "/boom", headers={"Accept": "application/json"}
        )
        assert r_json.status_code == 500
        assert r_json.headers["content-type"].startswith("application/json")

        # /api/* prefix is treated as API-shaped regardless of Accept.
        r_api = client.get("/api/boom", headers={"Accept": "text/html"})
        assert r_api.status_code == 500
        assert r_api.headers["content-type"].startswith("application/json")


def test_github_issue_link_encodes_uuid():
    """The prefilled issue title and body must contain the UUID."""
    from urllib.parse import parse_qs, urlparse

    from arena.error_handler import _github_issue_link
    import uuid

    error_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
    url = _github_issue_link(error_id, "GET", "/api/foo?x=1")
    assert url.startswith("https://github.com/OutplayArena/arena/issues/new?")
    # Decode the query string so we can assert on the human-readable
    # form rather than the URL-encoded form.
    qs = parse_qs(urlparse(url).query)
    assert qs["title"] == [f"Server error: {error_id}"]
    assert f"**{error_id}**" in qs["body"][0]
    # The method+path shows up in the body too so the maintainer can
    # correlate the issue with the request that failed.
    assert "GET /api/foo" in qs["body"][0]


def test_client_ip_xff_first_hop():
    from arena.error_handler import _client_ip

    class _Req:
        def __init__(self, headers, client_host="10.0.0.1"):
            self.headers = headers
            self.client = type("C", (), {"host": client_host})()

    r1 = _Req({"x-forwarded-for": "203.0.113.7, 10.0.0.1"})
    assert _client_ip(r1) == "203.0.113.7"

    r2 = _Req({"x-forwarded-for": "[2001:db8::1]:443"})
    assert _client_ip(r2) == "2001:db8::1"

    r3 = _Req({}, client_host="10.0.0.1")
    assert _client_ip(r3) == "10.0.0.1"

    r4 = _Req({}, client_host=None)
    assert _client_ip(r4) is None


def test_known_routes_still_200():
    """Sanity: registering the handler does not break happy paths."""
    app, _ = _build_app_with_boom_route()
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/ok").json() == {"ok": True}


@pytest.fixture(autouse=True)
def _reset_main_module():
    """Each test reloads arena.main so module-level state is fresh.

    Several other backend tests mutate ``arena.main`` globals; we don't
    want one test's reload to leak into the next.
    """
    yield
    # Reload after so a subsequent test that imports arena.main gets
    # the original module object, not a half-mutated copy.
    if "arena.main" in globals():
        importlib.reload(globals()["arena.main"])
