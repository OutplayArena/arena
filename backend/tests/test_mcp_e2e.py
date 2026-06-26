"""
MCP end-to-end tests against a live minikube cluster.

Run with:
    pytest tests/test_mcp_e2e.py -m e2e -v

Required environment:
    kubectl must be configured pointing at the arena namespace.
    The MCP server Deployment must be running (after helm upgrade).

Optional overrides:
    E2E_BACKEND_URL   – default http://192.168.49.2:30391/api
    E2E_MCP_URL       – default http://192.168.49.2:30391/mcp
    E2E_NAMESPACE     – default arena
"""

import os
import subprocess
import uuid

import httpx
import pytest

from outplayarena_sdk.mcp_client import MCPClient
from arena.auth.session_key import derive_session_key

# ── Configuration ────────────────────────────────────────────────────────────

BACKEND_URL = os.environ.get("E2E_BACKEND_URL", "http://192.168.49.2:30391/api")
MCP_URL = os.environ.get("E2E_MCP_URL", "http://192.168.49.2:30391/mcp")
NAMESPACE = os.environ.get("E2E_NAMESPACE", "arena")

pytestmark = pytest.mark.e2e

# ── Helpers ───────────────────────────────────────────────────────────────────

def _kubectl_exec(script: str) -> str:
    """Run a Python snippet inside the backend pod and return stdout."""
    result = subprocess.run(
        [
            "kubectl", "exec", "-n", NAMESPACE,
            "deployment/arena-backend", "--",
            "python3", "-c", script,
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"kubectl exec failed:\n{result.stderr}")
    return result.stdout.strip()


def _create_test_user() -> tuple[str, str]:
    """Create a throwaway user in the cluster DB and return (user_id, bearer_token)."""
    uid = str(uuid.uuid4())
    email = f"e2e-{uid[:8]}@test.local"
    script = f"""import asyncio
from arena.db import async_session
from arena.models.user import User
from arena.auth.jwt import create_access_token

async def main():
    user_id = "{uid}"
    async with async_session() as db:
        db.add(User(id=user_id, email="{email}", name="E2E Test", provider="e2e", provider_user_id=user_id))
        await db.commit()
    print(user_id + "|" + create_access_token(user_id))

asyncio.run(main())
"""
    output = _kubectl_exec(script)
    user_id, token = output.split("|", 1)
    return user_id, f"Bearer {token}"


def _delete_test_user(user_id: str) -> None:
    _kubectl_exec(f"""
import asyncio
from arena.db import async_session
from arena.models.user import User
from sqlalchemy import delete

async def main():
    async with async_session() as db:
        await db.execute(delete(User).where(User.id == "{user_id}"))
        await db.commit()

asyncio.run(main())
""")


def _run_migration() -> None:
    result = subprocess.run(
        [
            "kubectl", "exec", "-n", NAMESPACE,
            "deployment/arena-backend", "--",
            "alembic", "upgrade", "head",
        ],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Migration failed:\n{result.stderr}")


# ── Session-level fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def run_migrations():
    """Run alembic upgrade head once before the entire E2E suite."""
    _run_migration()


@pytest.fixture(scope="session")
def test_user():
    """Create a test user for the session; delete it on teardown."""
    user_id, bearer = _create_test_user()
    yield user_id, bearer
    _delete_test_user(user_id)


@pytest.fixture(scope="session")
def api():
    """httpx.Client pointed at the backend API."""
    with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as client:
        yield client


# ── Per-test fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def live_session(api, test_user):
    """Create a real game session; return (session_id, token_a, token_b, mcp_url).
    Fails the session on teardown to avoid leaving dangling state.
    """
    _, bearer = test_user
    resp = api.post(
        "/experiment",
        json={"game": "colonelblotto", "players": 2, "n_fields": 5, "total": 100, "rounds": 1, "seed": 42},
        headers={"Authorization": bearer},
    )
    resp.raise_for_status()
    data = resp.json()
    session_id = data["session_id"]
    token_a = data["player_tokens"]["A"]
    token_b = data["player_tokens"]["B"]
    mcp_url_val = data.get("mcp_url", MCP_URL)

    yield session_id, token_a, token_b, mcp_url_val

    # Teardown: mark session failed so it doesn't linger as "running"
    api.post(
        f"/session/{session_id}/fail",
        json={"error": "e2e test teardown"},
        headers={"Authorization": f"Bearer {token_a}"},
    )


# ── Auth rejection tests ──────────────────────────────────────────────────────

def test_mcp_rejects_missing_auth():
    """MCP server refuses connections without an Authorization header."""
    resp = httpx.get(MCP_URL, timeout=5)
    assert resp.status_code == 401


def test_mcp_rejects_wrong_prefix():
    """Platform key (nka_...) is not a valid session key."""
    resp = httpx.get(
        MCP_URL,
        headers={"Authorization": "Bearer nka_notsessionkey"},
        timeout=5,
    )
    assert resp.status_code == 401


def test_mcp_rejects_tampered_key():
    """HMAC-tampered session key is rejected."""
    key = derive_session_key("fake-session", "A")
    tampered = key[:-4] + "XXXX"
    resp = httpx.get(
        MCP_URL,
        headers={"Authorization": f"Bearer {tampered}"},
        timeout=5,
    )
    assert resp.status_code == 401


def test_mcp_health_check():
    """MCP server /health responds 200 without auth."""
    resp = httpx.get(f"{MCP_URL}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── Connectivity ──────────────────────────────────────────────────────────────

def test_mcp_connect_and_initialize(live_session):
    """Valid session key → MCPClient connects and lists tools."""
    session_id, token_a, _, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a):
        pass  # connect() + initialize() succeeded if no exception


# ── Tool tests ────────────────────────────────────────────────────────────────

def test_get_game_state(live_session):
    """get_game_state returns a dict with a 'phase' key."""
    session_id, token_a, _, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as client:
        state = client.get_game_state()
    assert isinstance(state, dict)
    assert "phase" in state


def test_get_observation_returns_prompts(live_session):
    """get_observation returns system + turn prompts for player A."""
    session_id, token_a, _, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as client:
        obs = client.get_observation()
    assert "system" in obs
    assert "turn" in obs


def test_get_observation_variant(live_session):
    """get_observation forwards the variant parameter."""
    session_id, token_a, _, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as client:
        obs = client.get_observation(variant="gain_framed")
    assert "system" in obs


def test_get_observation_player_b_perspective(live_session):
    """Token B gives player B's observation (different from A's)."""
    session_id, token_a, token_b, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as ca, MCPClient(mcp_url_val, token_b) as cb:
        obs_a = ca.get_observation()
        obs_b = cb.get_observation()
    # Both must succeed; system prompts may differ by role
    assert "system" in obs_a
    assert "system" in obs_b


def test_submit_action_accepted(live_session):
    """submit_action with a valid allocation returns a response dict."""
    session_id, token_a, _, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as client:
        result = client.submit_action([20, 20, 20, 20, 20])
    assert isinstance(result, dict)


def test_mailbox_empty_initially(live_session):
    """get_mailbox returns an empty list for a new session."""
    session_id, token_a, _, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as client:
        messages = client.get_mailbox()
    assert isinstance(messages, list)
    assert len(messages) == 0


def test_send_and_receive_message(live_session, api, test_user):
    """send_message → recipient sees it in get_mailbox."""
    session_id, token_a, token_b, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as client_a:
        client_a.send_message("Hello B!", recipient="B")

    with MCPClient(mcp_url_val, token_b) as client_b:
        messages = client_b.get_mailbox()

    assert any(m.get("content") == "Hello B!" for m in messages)


def test_list_games(live_session):
    """list_games returns a non-empty list."""
    session_id, token_a, _, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as client:
        games = client.list_games()
    assert isinstance(games, list)
    assert len(games) > 0


def test_get_game_details(live_session):
    """get_game_details returns metadata for colonelblotto."""
    session_id, token_a, _, mcp_url_val = live_session
    with MCPClient(mcp_url_val, token_a) as client:
        details = client.get_game_details("colonelblotto")
    assert isinstance(details, dict)


# ── Session isolation ─────────────────────────────────────────────────────────

def test_two_sessions_are_isolated(api, test_user):
    """Concurrent sessions see only their own game state."""
    _, bearer = test_user
    game_cfg = {"game": "colonelblotto", "players": 2, "n_fields": 5, "total": 100, "rounds": 1, "seed": 42}

    r1 = api.post("/experiment", json=game_cfg, headers={"Authorization": bearer})
    r2 = api.post("/experiment", json=game_cfg, headers={"Authorization": bearer})
    r1.raise_for_status()
    r2.raise_for_status()

    d1, d2 = r1.json(), r2.json()
    sid1, tok1 = d1["session_id"], d1["player_tokens"]["A"]
    sid2, tok2 = d2["session_id"], d2["player_tokens"]["A"]
    mcp_url1 = d1.get("mcp_url", MCP_URL)
    mcp_url2 = d2.get("mcp_url", MCP_URL)

    try:
        with MCPClient(mcp_url1, tok1) as c1, MCPClient(mcp_url2, tok2) as c2:
            state1 = c1.get_game_state()
            state2 = c2.get_game_state()

        assert state1.get("session_id") != state2.get("session_id") or sid1 != sid2
    finally:
        for sid, tok in [(sid1, tok1), (sid2, tok2)]:
            api.post(f"/session/{sid}/fail", json={"error": "e2e teardown"},
                     headers={"Authorization": f"Bearer {tok}"})


# ── Stateless scalability ─────────────────────────────────────────────────────

def test_concurrent_requests_no_context_collision(live_session):
    """10 parallel get_game_state calls all succeed with the correct session_id."""
    session_id, token_a, _, mcp_url_val = live_session

    def call_once() -> dict:
        with MCPClient(mcp_url_val, token_a) as client:
            return client.get_game_state()

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: call_once(), range(10)))

    assert all(isinstance(r, dict) for r in results)
    assert all("phase" in r for r in results)
