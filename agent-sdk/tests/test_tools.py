"""Tests for :mod:`outplayarena_sdk.tools`."""
from __future__ import annotations

from outplayarena_sdk.tools import (
    build_backend_tools,
    get_game_state_tool,
    get_observation_tool,
    send_message_tool,
    submit_action_tool,
)


class TestToolSchemas:
    """All tools must be valid OpenAI function-calling definitions."""

    def test_get_observation(self):
        tool = get_observation_tool()
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "get_observation"
        assert "variant" in tool["function"]["parameters"]["properties"]
        assert "neutral" in tool["function"]["parameters"]["properties"]["variant"]["enum"]

    def test_get_game_state(self):
        tool = get_game_state_tool()
        assert tool["function"]["name"] == "get_game_state"
        assert tool["function"]["parameters"]["properties"] == {}

    def test_send_message(self):
        tool = send_message_tool()
        assert tool["function"]["name"] == "send_message"
        params = tool["function"]["parameters"]
        assert "content" in params["required"]
        assert params["properties"]["content"]["maxLength"] == 200

    def test_submit_action_includes_hint(self):
        tool = submit_action_tool("a list of N integers summing to TOTAL")
        assert tool["function"]["name"] == "submit_action"
        assert "list of N integers summing to TOTAL" in tool["function"]["description"]
        assert "allocation" in tool["function"]["parameters"]["required"]

    def test_build_backend_tools_returns_four(self):
        tools = build_backend_tools("anything")
        names = [t["function"]["name"] for t in tools]
        assert names == [
            "get_observation",
            "get_game_state",
            "send_message",
            "submit_action",
        ]

    def test_additional_properties_false(self):
        """OpenAI strict mode requires additionalProperties: False on every object."""
        tools = build_backend_tools("hint")
        for tool in tools:
            params = tool["function"].get("parameters", {})
            assert params.get("additionalProperties") is False, tool["function"]["name"]
