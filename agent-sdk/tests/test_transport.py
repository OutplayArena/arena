"""Tests for :mod:`outplayarena_sdk.transport`."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from outplayarena_sdk.client import ArenaClient
from outplayarena_sdk.mcp_client import MCPClient
from outplayarena_sdk.transport import AsyncBackend


@pytest.fixture
def rest():
    client = ArenaClient("http://localhost:8000/api")
    return client


class TestAsyncBackendRest:
    @pytest.mark.asyncio
    async def test_get_state(self, rest):
        rest.get_state = MagicMock(return_value={"phase": "playing", "awaiting": ["A"]})
        backend = AsyncBackend(rest)
        result = await backend.get_state()
        assert result == {"phase": "playing", "awaiting": ["A"]}
        rest.get_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_observation(self, rest):
        rest.get_observation = MagicMock(return_value={"system": "s", "turn": "t"})
        backend = AsyncBackend(rest, player_id="A")
        result = await backend.get_observation("neutral")
        assert result == {"system": "s", "turn": "t"}
        rest.get_observation.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_action(self, rest):
        rest.submit_action = MagicMock(return_value={"status": "ok"})
        backend = AsyncBackend(rest)
        result = await backend.submit_action([1, 2, 3])
        assert result == {"status": "ok"}
        rest.submit_action.assert_called_once_with([1, 2, 3])

    @pytest.mark.asyncio
    async def test_get_results(self, rest):
        rest.get_results = MagicMock(return_value={"winner": "A"})
        backend = AsyncBackend(rest)
        result = await backend.get_results()
        assert result["winner"] == "A"

    @pytest.mark.asyncio
    async def test_get_mailbox(self, rest):
        rest.get_mailbox = MagicMock(return_value=[{"id": "1", "content": "hi"}])
        backend = AsyncBackend(rest, player_id="A")
        result = await backend.get_mailbox()
        assert result == [{"id": "1", "content": "hi"}]

    @pytest.mark.asyncio
    async def test_send_message(self, rest):
        rest.send_message = MagicMock(return_value={"id": "1"})
        backend = AsyncBackend(rest, player_id="A")
        result = await backend.send_message("hello", recipient="B")
        assert result == {"id": "1"}


class TestAsyncBackendTransportSelection:
    def test_transport_is_rest_when_no_mcp(self, rest):
        backend = AsyncBackend(rest)
        assert backend.transport == "rest"

    def test_transport_is_mcp_when_mcp_provided(self, rest):
        mcp = MagicMock(spec=MCPClient)
        backend = AsyncBackend(rest, mcp)
        assert backend.transport == "mcp"


class TestAsyncBackendProperties:
    def test_rest_property_returns_rest_client(self, rest):
        backend = AsyncBackend(rest)
        assert backend.rest is rest

    def test_mcp_property_returns_none_when_no_mcp(self, rest):
        backend = AsyncBackend(rest)
        assert backend.mcp is None

    def test_mcp_property_returns_mcp_client_when_set(self, rest):
        mcp = MagicMock(spec=MCPClient)
        backend = AsyncBackend(rest, mcp)
        assert backend.mcp is mcp


class TestAsyncBackendPlayerId:
    def test_set_player_id_stores_value(self, rest):
        backend = AsyncBackend(rest)
        backend.set_player_id("A")
        assert backend._player_id == "A"

    @pytest.mark.asyncio
    async def test_get_observation_requires_player_id(self, rest):
        backend = AsyncBackend(rest)
        with pytest.raises(RuntimeError, match="no player_id"):
            await backend.get_observation()

    @pytest.mark.asyncio
    async def test_get_mailbox_requires_player_id(self, rest):
        backend = AsyncBackend(rest)
        with pytest.raises(RuntimeError, match="no player_id"):
            await backend.get_mailbox()

    def test_constructor_with_player_id_works(self, rest):
        backend = AsyncBackend(rest, player_id="A")
        assert backend._player_id == "A"


class TestAsyncBackendMCPSelection:
    """When mcp is provided, methods should prefer MCP over REST."""

    @pytest.mark.asyncio
    async def test_get_state_prefers_mcp(self, rest):
        mcp = MagicMock(spec=MCPClient)
        mcp.get_game_state = MagicMock(return_value={"phase": "mcp"})
        backend = AsyncBackend(rest, mcp)
        result = await backend.get_state()
        assert result == {"phase": "mcp"}
        mcp.get_game_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_observation_prefers_mcp(self, rest):
        mcp = MagicMock(spec=MCPClient)
        mcp.get_observation = MagicMock(return_value={"system": "mcp"})
        backend = AsyncBackend(rest, mcp)
        result = await backend.get_observation("gain_framed")
        assert result == {"system": "mcp"}
        mcp.get_observation.assert_called_once_with(variant="gain_framed")

    @pytest.mark.asyncio
    async def test_submit_action_prefers_mcp(self, rest):
        mcp = MagicMock(spec=MCPClient)
        mcp.submit_action = MagicMock(return_value={"status": "mcp"})
        backend = AsyncBackend(rest, mcp)
        result = await backend.submit_action([5, 5])
        assert result == {"status": "mcp"}
        mcp.submit_action.assert_called_once_with([5, 5])

    @pytest.mark.asyncio
    async def test_get_results_prefers_mcp(self, rest):
        mcp = MagicMock(spec=MCPClient)
        mcp.get_results = MagicMock(return_value={"winner": "MCP"})
        backend = AsyncBackend(rest, mcp)
        result = await backend.get_results()
        assert result["winner"] == "MCP"

    @pytest.mark.asyncio
    async def test_get_mailbox_prefers_mcp(self, rest):
        mcp = MagicMock(spec=MCPClient)
        mcp.get_mailbox = MagicMock(return_value=[{"id": "m1"}])
        backend = AsyncBackend(rest, mcp)
        result = await backend.get_mailbox()
        assert result == [{"id": "m1"}]

    @pytest.mark.asyncio
    async def test_send_message_prefers_mcp(self, rest):
        mcp = MagicMock(spec=MCPClient)
        mcp.send_message = MagicMock(return_value={"id": "sent"})
        backend = AsyncBackend(rest, mcp)
        result = await backend.send_message("hi", recipient="B")
        assert result == {"id": "sent"}
        mcp.send_message.assert_called_once_with("hi", "B")


class TestAsyncBackendDiscovery:
    @pytest.mark.asyncio
    async def test_list_games_uses_rest(self, rest):
        rest.list_games = MagicMock(return_value=[{"slug": "ultimatum"}])
        backend = AsyncBackend(rest)
        result = await backend.list_games()
        assert result == [{"slug": "ultimatum"}]

    @pytest.mark.asyncio
    async def test_get_game_details_uses_rest(self, rest):
        rest.get_game_details = MagicMock(return_value={"name": "Ultimatum"})
        backend = AsyncBackend(rest)
        result = await backend.get_game_details("ultimatum")
        assert result == {"name": "Ultimatum"}


class TestAsyncBackendRestRequiresRestClient:
    def test_none_rest_client_raises(self):
        with pytest.raises(ValueError, match="rest_client is required"):
            AsyncBackend(None)
