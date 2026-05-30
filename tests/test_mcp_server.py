import pytest

from nash_arena import mcp_server
from nash_arena.client import ArenaClient


class FakeClient:
    def __init__(self):
        self.submitted = []

    def get_state(self):
        return {"phase": "awaiting_action"}

    def submit_action(self, allocation):
        self.submitted.append(allocation)
        return {"submitted": allocation}

    def get_results(self):
        return {"winner": "A"}

    def list_games(self):
        return [{"name": "blotto"}]

    def get_game_details(self, game):
        return {"name": game}

    def get_game_metrics(self, game):
        return {"game": game, "metrics": []}

    def get_game_prompts(self, game):
        return {"game": game, "action_format": {"type": "json_array"}}


def test_required_env_returns_value(monkeypatch):
    monkeypatch.setenv("ARENA_SESSION_ID", "session-1")

    assert mcp_server.required_env("ARENA_SESSION_ID") == "session-1"


def test_required_env_rejects_missing_value(monkeypatch):
    monkeypatch.delenv("ARENA_SESSION_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="ARENA_SESSION_TOKEN is required"):
        mcp_server.required_env("ARENA_SESSION_TOKEN")


def test_arena_client_reads_environment(monkeypatch):
    monkeypatch.setenv("ARENA_BASE_URL", "http://arena.test")
    monkeypatch.setenv("ARENA_SESSION_ID", "session-1")
    monkeypatch.setenv("ARENA_SESSION_TOKEN", "tok-a")

    client = mcp_server.arena_client()

    assert isinstance(client, ArenaClient)
    assert client.base_url == "http://arena.test"
    assert client.session_id == "session-1"
    assert client.token == "tok-a"


def test_arena_client_uses_default_base_url(monkeypatch):
    monkeypatch.delenv("ARENA_BASE_URL", raising=False)
    monkeypatch.setenv("ARENA_SESSION_ID", "session-1")
    monkeypatch.setenv("ARENA_SESSION_TOKEN", "tok-a")

    client = mcp_server.arena_client()

    assert client.base_url == "http://127.0.0.1:8000/api"


def test_get_game_state_calls_client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.get_game_state() == {"phase": "awaiting_action"}


def test_submit_action_calls_client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.submit_action([10, 0, 0]) == {"submitted": [10, 0, 0]}
    assert fake.submitted == [[10, 0, 0]]


def test_get_results_calls_client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.get_results() == {"winner": "A"}


def test_game_directory_tools_call_client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.list_games() == [{"name": "blotto"}]
    assert mcp_server.get_game_details("blotto") == {"name": "blotto"}
    assert mcp_server.get_game_metrics("blotto") == {"game": "blotto", "metrics": []}
    assert mcp_server.get_game_prompts("blotto") == {
        "game": "blotto",
        "action_format": {"type": "json_array"},
    }
