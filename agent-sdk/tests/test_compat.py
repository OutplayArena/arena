"""Tests for the MCPAgent backward-compat shim."""


from outplayarena_sdk._compat import MCPAgent


def _make_session_token(player: str = "A") -> str:
    """Return an opaque session-key string for tests.

    As of v0.2.0 the SDK does not decode session tokens; tests can pass
    any opaque ``nks_``-prefixed string.
    """
    return f"nks_test_token_for_{player}"


class _FakeMCPAgent(MCPAgent):
    """MCPAgent that stubs out the network layer for unit testing."""

    def __init__(self, tool_response, player: str = "A"):
        super().__init__("http://fake-mcp:9999", _make_session_token(player=player), player=player)
        self._connected = True
        self._session = object()
        self._loop = None
        self._tool_response = tool_response

    def _call_tool(self, name, arguments=None):
        if isinstance(self._tool_response, dict) and name in self._tool_response:
            return self._tool_response[name]
        return self._tool_response


class TestPlayerProperty:
    def test_player_set_via_constructor(self):
        # As of v0.2.0 the player is passed explicitly, not decoded from
        # the token.
        agent = MCPAgent("http://x", "nks_test_token_for_A", player="A")
        assert agent.player == "A"

    def test_player_b_via_constructor(self):
        agent = MCPAgent("http://x", "nks_test_token_for_B", player="B")
        assert agent.player == "B"

    def test_player_default_is_empty(self):
        # Backward-compat: omitting the player leaves it empty (the
        # backend identifies the player from the token's HMAC, so the
        # SDK doesn't need to know).
        agent = MCPAgent("http://x", "nks_test_token_for_X")
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
                super().__init__("http://fake", _make_session_token(), player="A")
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
                super().__init__("http://fake", _make_session_token(), player="A")
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
