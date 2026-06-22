"""Tests for the MCPAgent backward-compat shim."""
import os


from outplaylabs_arena_sdk._compat import MCPAgent


def _make_session_token(player: str = "A", secret: str | None = None) -> str:
    """Build a valid nks_... session key the SDK can decode."""
    import base64
    import hashlib
    import hmac

    if secret is None:
        secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    session_id = "test-session-1"
    secret_hash = hashlib.sha256(secret.encode("utf-8")).digest()
    payload = f"{session_id}:{player}"
    sig = hmac.new(secret_hash, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{session_id}:{player}:{sig}"
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"nks_{encoded}"


class _FakeMCPAgent(MCPAgent):
    """MCPAgent that stubs out the network layer for unit testing."""

    def __init__(self, tool_response, player: str = "A"):
        super().__init__("http://fake-mcp:9999", _make_session_token(player=player))
        self._connected = True
        self._session = object()
        self._loop = None
        self._tool_response = tool_response

    def _call_tool(self, name, arguments=None):
        if isinstance(self._tool_response, dict) and name in self._tool_response:
            return self._tool_response[name]
        return self._tool_response


class TestPlayerProperty:
    def test_player_extracted_from_session_key(self):
        agent = MCPAgent.__new__(MCPAgent)
        agent.session_key = _make_session_token(player="A")
        assert agent.player == "A"

    def test_player_b_extracted(self):
        agent = MCPAgent.__new__(MCPAgent)
        agent.session_key = _make_session_token(player="B")
        assert agent.player == "B"

    def test_invalid_session_key_returns_empty(self):
        agent = MCPAgent.__new__(MCPAgent)
        agent.session_key = "not-a-valid-key"
        assert agent.player == ""


class TestGetObservation:
    def test_returns_dict_unchanged(self):
        agent = _FakeMCPAgent({"get_observation": {"system": "s", "turn": "t"}})
        result = agent.get_observation()
        assert result == {"system": "s", "turn": "t"}

    def test_passes_variant_argument(self):
        captured = {}

        class _CapturingAgent(MCPAgent):
            def __init__(self):
                super().__init__("http://fake", _make_session_token())
                self._connected = True
                self._session = object()
                self._loop = None

            def _call_tool(self, name, arguments=None):
                captured["name"] = name
                captured["arguments"] = arguments
                return {"system": "s", "turn": "t"}

        agent = _CapturingAgent()
        agent.get_observation(variant="loss_framed")
        assert captured["name"] == "get_observation"
        assert captured["arguments"] == {"variant": "loss_framed"}

    def test_non_dict_response_returns_fallback(self):
        agent = _FakeMCPAgent({"get_observation": "not a dict"})
        result = agent.get_observation()
        assert result == {"system": "", "turn": ""}


class TestGetGameState:
    def test_returns_state_dict(self):
        state = {"phase": "playing", "round": 1}
        agent = _FakeMCPAgent({"get_game_state": state})
        assert agent.get_game_state() == state


class TestSubmitAction:
    def test_passes_allocation(self):
        captured = {}

        class _CapturingAgent(MCPAgent):
            def __init__(self):
                super().__init__("http://fake", _make_session_token())
                self._connected = True
                self._session = object()
                self._loop = None

            def _call_tool(self, name, arguments=None):
                captured["name"] = name
                captured["arguments"] = arguments
                return {"status": "ok"}

        agent = _CapturingAgent()
        agent.submit_action([10, 0, 0])
        assert captured["name"] == "submit_action"
        assert captured["arguments"] == {"allocation": [10, 0, 0]}


class TestGetResults:
    def test_returns_results(self):
        results = {"winner": "A", "score_a": 100, "score_b": 0}
        agent = _FakeMCPAgent({"get_results": results})
        assert agent.get_results() == results
