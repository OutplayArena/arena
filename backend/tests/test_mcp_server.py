import pytest

from nash_arena import mcp_server
from nash_arena_sdk.client import ArenaClient
from nash_arena.auth.session_key import derive_session_key


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

    def get_observation(self, player, variant="neutral"):
        return {"system": f"You are player {player}.", "turn": "Your move.", "player_id": player, "variant": variant}

    def list_games(self):
        return [{"name": "colonelblotto"}]

    def get_game_details(self, game):
        return {"name": game}

    def get_game_metrics(self, game):
        return {"game": game, "metrics": []}

    def get_game_prompts(self, game):
        return {"game": game, "action_format": {"type": "json_array"}}


def test_required_env_returns_value(monkeypatch):
    monkeypatch.setenv("NASH_ARENA_KEY", "nks_testkey")

    assert mcp_server.required_env("NASH_ARENA_KEY") == "nks_testkey"


def test_required_env_rejects_missing_value(monkeypatch):
    monkeypatch.delenv("NASH_ARENA_KEY", raising=False)

    with pytest.raises(RuntimeError, match="NASH_ARENA_KEY is required"):
        mcp_server.required_env("NASH_ARENA_KEY")


def test_arena_client_reads_environment(monkeypatch):
    session_key = derive_session_key("session-1", "A")
    monkeypatch.setenv("NASH_ARENA_BASE_URL", "http://arena.test")
    monkeypatch.setenv("NASH_ARENA_KEY", session_key)

    client = mcp_server.arena_client()

    assert isinstance(client, ArenaClient)
    assert client.base_url == "http://arena.test"
    assert client.session_id == "session-1"
    assert client.token == session_key


def test_arena_client_uses_default_base_url(monkeypatch):
    session_key = derive_session_key("session-1", "A")
    monkeypatch.delenv("NASH_ARENA_BASE_URL", raising=False)
    monkeypatch.delenv("ARENA_BASE_URL", raising=False)
    monkeypatch.setenv("NASH_ARENA_KEY", session_key)

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


def test_get_observation_uses_player_from_session_key(monkeypatch):
    session_key = derive_session_key("session-1", "B")
    monkeypatch.setenv("NASH_ARENA_KEY", session_key)
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    result = mcp_server.get_observation()

    assert result["player_id"] == "B"
    assert result["variant"] == "neutral"
    assert "system" in result
    assert "turn" in result


def test_get_observation_passes_variant(monkeypatch):
    session_key = derive_session_key("session-1", "A")
    monkeypatch.setenv("NASH_ARENA_KEY", session_key)
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    result = mcp_server.get_observation(variant="gain_framed")

    assert result["variant"] == "gain_framed"


def test_game_directory_tools_call_client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(mcp_server, "arena_client", lambda: fake)

    assert mcp_server.list_games() == [{"name": "colonelblotto"}]
    assert mcp_server.get_game_details("colonelblotto") == {"name": "colonelblotto"}
    assert mcp_server.get_game_metrics("colonelblotto") == {"game": "colonelblotto", "metrics": []}
    assert mcp_server.get_game_prompts("colonelblotto") == {
        "game": "colonelblotto",
        "action_format": {"type": "json_array"},
    }


def test_send_message_calls_client(monkeypatch):
    sent = []

    class FakeClientWithComm:
        def send_message(self, content, to_player=None):
            sent.append((content, to_player))
            return {"message": {"from_player": "A", "content": content, "to_player": to_player}}

        def get_messages(self):
            return {"messages": [{"from_player": "A", "content": "test"}]}

        def get_state(self):
            return {"phase": "awaiting_action"}

        def submit_action(self, allocation):
            return {"submitted": allocation}

        def get_results(self):
            return {"winner": "A"}

        def get_observation(self, player, variant="neutral"):
            return {"system": "", "turn": "", "player_id": player, "variant": variant}

        def list_games(self):
            return []

        def get_game_details(self, game):
            return {"name": game}

        def get_game_metrics(self, game):
            return {"game": game, "metrics": []}

        def get_game_prompts(self, game):
            return {"game": game, "action_format": {"type": "json_array"}}

    monkeypatch.setattr(mcp_server, "arena_client", lambda: FakeClientWithComm())

    result = mcp_server.send_message("Hello", to_player=None)
    assert result == {"message": {"from_player": "A", "content": "Hello", "to_player": None}}
    assert sent == [("Hello", None)]

    result = mcp_server.send_message("Hi B", to_player="B")
    assert result == {"message": {"from_player": "A", "content": "Hi B", "to_player": "B"}}
    assert sent == [("Hello", None), ("Hi B", "B")]


def test_get_messages_calls_client(monkeypatch):
    class FakeClientWithMessages:
        def get_messages(self):
            return {"messages": [{"from_player": "A", "content": "Hello"}]}

        def get_state(self):
            return {"phase": "awaiting_action"}

        def submit_action(self, allocation):
            return {"submitted": allocation}

        def get_results(self):
            return {"winner": "A"}

        def get_observation(self, player, variant="neutral"):
            return {"system": "", "turn": "", "player_id": player, "variant": variant}

        def list_games(self):
            return []

        def get_game_details(self, game):
            return {"name": game}

        def get_game_metrics(self, game):
            return {"game": game, "metrics": []}

        def get_game_prompts(self, game):
            return {"game": game, "action_format": {"type": "json_array"}}

    monkeypatch.setattr(mcp_server, "arena_client", lambda: FakeClientWithMessages())

    result = mcp_server.get_messages()
    assert result == {"messages": [{"from_player": "A", "content": "Hello"}]}
