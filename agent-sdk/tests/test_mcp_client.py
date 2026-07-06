"""Tests for :mod:`outplayarena_sdk.mcp_client`."""
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import TextContent

from outplayarena_sdk.mcp_client import MCPClient, _extract_tool_result


# ── _extract_tool_result (pure function, easy to cover) ─────────────────────


class _FakeCallToolResult:
    """Mimics mcp.ClientSession.call_tool return value."""

    def __init__(self, content):
        self.content = content


class TestExtractToolResult:
    def test_empty_content_returns_empty_list(self):
        result = _FakeCallToolResult(content=[])
        assert _extract_tool_result(result) == []

    def test_single_text_content_returns_parsed_value(self):
        result = _FakeCallToolResult(content=[TextContent(type="text", text='{"x": 1}')])
        assert _extract_tool_result(result) == {"x": 1}

    def test_multiple_text_contents_returns_list(self):
        result = _FakeCallToolResult(content=[
            TextContent(type="text", text='{"x": 1}'),
            TextContent(type="text", text='{"y": 2}'),
        ])
        assert _extract_tool_result(result) == [{"x": 1}, {"y": 2}]

    def test_non_json_text_returns_raw_wrapper(self):
        result = _FakeCallToolResult(content=[TextContent(type="text", text="not json")])
        # Single item returns the item unwrapped, not a list.
        assert _extract_tool_result(result) == {"raw": "not json"}


# ── MCPClient methods (mocking _call_tool) ──────────────────────────────────


class _StubMCPClient(MCPClient):
    """MCPClient with the network layer stubbed out."""

    def __init__(self):
        # Skip the real __init__ to avoid setting up threading/loop.
        self.mcp_url = "http://fake-mcp:9999"
        self.session_key = "nks_fake"
        self.timeout = 30.0
        self._session = object()
        self._exit_stack = object()
        self._connected = True
        self._loop = None
        self._thread = None
        self._tool_response = None

    def _call_tool(self, name, arguments=None):
        if isinstance(self._tool_response, dict) and name in self._tool_response:
            return self._tool_response[name]
        return self._tool_response


class TestMCPClientMethods:
    def test_get_observation_passes_variant(self):
        client = _StubMCPClient()
        client._tool_response = {"get_observation": {"system": "s", "turn": "t"}}
        result = client.get_observation(variant="loss_framed")
        assert result == {"system": "s", "turn": "t"}

    def test_get_observation_default_variant(self):
        client = _StubMCPClient()
        client._tool_response = {"get_observation": {"system": "s", "turn": "t"}}
        result = client.get_observation()
        assert result["system"] == "s"

    def test_get_game_state(self):
        client = _StubMCPClient()
        client._tool_response = {"get_game_state": {"phase": "playing"}}
        assert client.get_game_state() == {"phase": "playing"}

    def test_submit_action(self):
        client = _StubMCPClient()
        client._tool_response = {"submit_action": {"status": "ok"}}
        result = client.submit_action([1, 2, 3])
        assert result == {"status": "ok"}

    def test_get_results(self):
        client = _StubMCPClient()
        client._tool_response = {"get_results": {"winner": "A"}}
        assert client.get_results() == {"winner": "A"}

    def test_list_games(self):
        client = _StubMCPClient()
        client._tool_response = {"list_games": [{"slug": "ultimatum"}]}
        assert client.list_games() == [{"slug": "ultimatum"}]

    def test_get_game_details(self):
        client = _StubMCPClient()
        client._tool_response = {"get_game_details": {"name": "Ultimatum"}}
        assert client.get_game_details("ultimatum") == {"name": "Ultimatum"}

    def test_get_game_metrics(self):
        client = _StubMCPClient()
        client._tool_response = {"get_game_metrics": {"metrics": []}}
        assert client.get_game_metrics("ultimatum") == {"metrics": []}

    def test_get_game_prompts(self):
        client = _StubMCPClient()
        client._tool_response = {"get_game_prompts": {"prompts": {}}}
        assert client.get_game_prompts("ultimatum") == {"prompts": {}}

    def test_get_game_skill(self):
        client = _StubMCPClient()
        client._tool_response = {"get_game_skill": {"sections": []}}
        assert client.get_game_skill("ultimatum") == {"sections": []}

    def test_get_agent_manifest(self):
        client = _StubMCPClient()
        client._tool_response = {"get_agent_manifest": {"tools": []}}
        assert client.get_agent_manifest("ultimatum") == {"tools": []}

    def test_send_message(self):
        client = _StubMCPClient()
        client._tool_response = {"send_message": {"id": "msg-1"}}
        assert client.send_message("hi", recipient="B") == {"id": "msg-1"}


class TestGetMailbox:
    def test_returns_messages_list_from_dict(self):
        client = _StubMCPClient()
        client._tool_response = {"get_mailbox": {"messages": [{"id": "1"}, {"id": "2"}]}}
        assert client.get_mailbox() == [{"id": "1"}, {"id": "2"}]

    def test_returns_list_directly(self):
        client = _StubMCPClient()
        client._tool_response = {"get_mailbox": [{"id": "1"}]}
        assert client.get_mailbox() == [{"id": "1"}]

    def test_empty_dict_returns_empty_list(self):
        client = _StubMCPClient()
        client._tool_response = {"get_mailbox": {}}
        assert client.get_mailbox() == []

    def test_none_returns_empty_list(self):
        client = _StubMCPClient()
        client._tool_response = {"get_mailbox": None}
        assert client.get_mailbox() == []


class TestContextManager:
    def test_enter_calls_connect(self):
        client = _bare_client()
        with patch.object(MCPClient, "connect") as mock_connect, \
             patch.object(MCPClient, "disconnect") as mock_disconnect:
            with client as c:
                assert c is client
            mock_connect.assert_called_once()
            mock_disconnect.assert_called_once()

    def test_exit_calls_disconnect(self):
        client = _bare_client()
        with patch.object(MCPClient, "connect"), \
             patch.object(MCPClient, "disconnect") as mock_disconnect:
            client.__exit__(None, None, None)
            mock_disconnect.assert_called_once()


def _bare_client():
    """Build a bare MCPClient without running __init__."""
    client = MCPClient.__new__(MCPClient)
    client.mcp_url = "http://fake"
    client.session_key = "nks_fake"
    client.timeout = 30.0
    client._connected = False
    client._session = None
    client._exit_stack = None
    client._loop = None
    client._thread = None
    return client


class TestAuthHeaders:
    def test_auth_headers_property(self):
        client = MCPClient.__new__(MCPClient)
        client.session_key = "nks_test_token"
        assert client._auth_headers == {"Authorization": "Bearer nks_test_token"}

    def test_url_strips_trailing_slash(self):
        client = MCPClient("http://example.com/", "nks_x")
        assert client.mcp_url == "http://example.com"

        client2 = MCPClient("http://example.com", "nks_x")
        assert client2.mcp_url == "http://example.com"

    def test_del_safe_on_partially_initialized_instance(self):
        client = MCPClient.__new__(MCPClient)
        client.__del__()
        client.disconnect()


class TestMCPURLHandling:
    def test_constructor_stores_args(self):
        client = MCPClient("http://mcp:9999", "nks_abc", timeout=15.0)
        assert client.mcp_url == "http://mcp:9999"
        assert client.session_key == "nks_abc"
        assert client.timeout == 15.0
        assert client._connected is False
        assert client._session is None


class TestCallTool:
    def test_call_tool_requires_connection(self):
        client = _bare_client()
        client._connected = False
        client._session = None
        with pytest.raises(RuntimeError, match="Not connected"):
            client._call_tool("anything")

    def test_call_tool_requires_session(self):
        client = _bare_client()
        client._connected = True
        client._session = None
        with pytest.raises(RuntimeError, match="Not connected"):
            client._call_tool("anything")

    def test_call_tool_requires_loop(self):
        client = _bare_client()
        client._connected = True
        client._session = object()
        client._loop = None
        with pytest.raises(RuntimeError, match="Not connected"):
            client._call_tool("anything")

    def test_call_tool_dispatches_via_loop(self):
        import asyncio
        client = _bare_client()
        client._connected = True
        client._session = MagicMock()

        async def fake_call_tool(name, arguments):
            return _FakeCallToolResult(content=[
                TextContent(type="text", text='{"result": "ok"}')
            ])

        client._session.call_tool = fake_call_tool

        # Run the loop in a background thread for the duration of the call.
        loop = asyncio.new_event_loop()
        client._loop = loop

        import threading
        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

        try:
            result = client._call_tool("test_tool", {"x": 1})
            assert result == {"result": "ok"}
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2)
            loop.close()
