"""Basic tests for the OutplayLabs Arena SDK."""
import hashlib
import hmac
import base64
import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from outplaylabs_arena_sdk import (
    ArenaClient,
    MCPAgent,
    LLMAgent,
    LLMConfig,
    AgentSpec,
    format_results,
    save_results,
    parse_allocation,
    parse_offer,
    parse_accept_reject,
)
from outplaylabs_arena_sdk.client import validate_session_key, SESSION_KEY_PREFIX
from outplaylabs_arena_sdk.llm_agent import _balanced_allocation, _extract_tool_text


def _make_session_key(session_id: str, player: str, secret: str) -> str:
    """Helper to create a valid session key for testing."""
    secret_hash = hashlib.sha256(secret.encode("utf-8")).digest()
    payload = f"{session_id}:{player}"
    sig = hmac.new(secret_hash, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{session_id}:{player}:{sig}"
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{SESSION_KEY_PREFIX}{encoded}"


class TestValidateSessionKey:
    def test_valid_key(self):
        secret = "test-secret"
        session_id = "abc-123"
        player = "A"
        key = _make_session_key(session_id, player, secret)

        result_id, result_player = validate_session_key(key, secret)
        assert result_id == session_id
        assert result_player == player

    def test_invalid_prefix(self):
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key("invalid_key", "secret")

    def test_invalid_signature(self):
        secret = "test-secret"
        key = _make_session_key("abc", "A", secret)
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key(key, "wrong-secret")

    def test_malformed_base64(self):
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key(f"{SESSION_KEY_PREFIX}!!!invalid!!!", "secret")

    def test_wrong_number_of_parts(self):
        token = base64.urlsafe_b64encode(b"only:two").decode("utf-8").rstrip("=")
        with pytest.raises(ValueError, match="invalid session key"):
            validate_session_key(f"{SESSION_KEY_PREFIX}{token}", "secret")


class TestParseAllocation:
    def test_valid(self):
        assert parse_allocation("[10, 20, 30, 40]", 4, 100) == [10, 20, 30, 40]

    def test_invalid_text(self):
        result = parse_allocation("invalid", 3, 100)
        assert len(result) == 3
        assert sum(result) == 100

    def test_wrong_length(self):
        result = parse_allocation("[10, 20]", 3, 100)
        assert len(result) == 3

    def test_wrong_sum(self):
        result = parse_allocation("[10, 20, 30]", 3, 100)
        assert len(result) == 3
        assert sum(result) == 100

    def test_negative_values(self):
        result = parse_allocation("[-10, 50, 60]", 3, 100)
        assert len(result) == 3
        assert sum(result) == 100

    def test_bool_values_rejected(self):
        """Test that boolean values are rejected (bool is subclass of int)."""
        result = parse_allocation("[True, False, True]", 3, 100)
        assert len(result) == 3
        assert sum(result) == 100

    def test_mixed_types_rejected(self):
        result = parse_allocation("[10, '20', 30]", 3, 60)
        assert len(result) == 3
        assert sum(result) == 60


class TestBalancedAllocation:
    def test_even_split(self):
        assert _balanced_allocation(4, 100) == [25, 25, 25, 25]

    def test_uneven_split(self):
        result = _balanced_allocation(3, 10)
        assert result == [4, 3, 3]
        assert sum(result) == 10

    def test_single_field(self):
        assert _balanced_allocation(1, 50) == [50]


class TestParseOffer:
    def test_valid(self):
        assert parse_offer("I offer 42", 100) == 42.0

    def test_invalid(self):
        assert parse_offer("no number here", 100) == 40.0

    def test_clamped_to_total(self):
        assert parse_offer("I offer 200", 100) == 100.0

    def test_clamped_to_min(self):
        assert parse_offer("I offer 0.5", 100, min_offer=1.0) == 1.0


class TestParseAcceptReject:
    def test_accept(self):
        assert parse_accept_reject("I accept this offer") == "accept"

    def test_reject(self):
        assert parse_accept_reject("I reject this") == "reject"

    def test_case_insensitive(self):
        assert parse_accept_reject("ACCEPT") == "accept"
        assert parse_accept_reject("REJECT") == "reject"


class TestFormatResults:
    def test_basic(self):
        results = {
            "winner": "A",
            "total_scores": {"A": 10.0, "B": 5.0},
            "metrics": {"avg_payoff": {"A": 2.5, "B": 1.25}},
        }
        output = format_results(results)
        assert "Winner: A" in output
        assert "A=10.0" in output

    def test_tie(self):
        results = {"winner": "Tie", "total_scores": {"A": 5.0, "B": 5.0}}
        output = format_results(results)
        assert "Tie" in output


class TestSaveResults:
    def test_save_to_file(self):
        results = {"winner": "A", "total_scores": {"A": 10.0}}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_results(results, output_dir=tmpdir, game="test_game")
            assert path.exists()
            with open(path) as f:
                data = json.load(f)
            assert data["game"] == "test_game"
            assert data["results"]["winner"] == "A"

    def test_save_with_session_id(self):
        results = {"winner": "B"}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_results(results, output_dir=tmpdir, session_id="abc123")
            assert "abc123" in path.name


class TestLLMConfig:
    def test_defaults(self):
        config = LLMConfig(model="gpt-4", api_key="test-key")
        assert config.model == "gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.fallback_model is None


class TestAgentSpec:
    def test_to_llm_config(self):
        spec = AgentSpec(player="A", model="gpt-4", api_key="test-key")
        llm_config = spec.to_llm_config()
        assert llm_config.model == "gpt-4"
        assert llm_config.api_key == "test-key"

    def test_default_model(self):
        spec = AgentSpec(player="A")
        llm_config = spec.to_llm_config()
        assert llm_config.model == "gpt-4"


class TestArenaClient:
    def test_init(self):
        client = ArenaClient("http://localhost:8000/api")
        assert client.base_url == "http://localhost:8000/api"

    def test_init_strips_trailing_slash(self):
        client = ArenaClient("http://localhost:8000/api/")
        assert client.base_url == "http://localhost:8000/api"

    def test_for_player(self):
        creation_response = {
            "session_id": "sess-123",
            "player_tokens": {"A": "token_a", "B": "token_b"},
        }
        client = ArenaClient.for_player("http://localhost:8000/api", creation_response, "A")
        assert client.session_id == "sess-123"
        assert client.token == "token_a"

    def test_is_terminal(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"phase": "complete"}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        client = ArenaClient("http://localhost:8000/api", session_id="sess", http_client=mock_client)
        assert client.is_terminal() is True

    def test_is_not_terminal(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"phase": "running"}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        client = ArenaClient("http://localhost:8000/api", session_id="sess", http_client=mock_client)
        assert client.is_terminal() is False


class TestMCPAgent:
    def test_init(self):
        secret = "test-secret"
        session_id = "abc-123"
        player = "A"
        token = _make_session_key(session_id, player, secret)

        agent = MCPAgent(token, base_url="http://localhost:8000/api", jwt_secret=secret)
        assert agent.player == player
        assert agent.base_url == "http://localhost:8000/api"

    def test_init_invalid_token(self):
        with pytest.raises(ValueError, match="invalid session key"):
            MCPAgent("invalid_token", jwt_secret="secret")


class TestLLMAgent:
    def test_init(self):
        config = LLMConfig(model="gpt-4", api_key="test-key")
        agent = LLMAgent(
            player="A",
            player_token="token",
            arena_url="http://localhost:8000/api",
            llm_config=config,
        )
        assert agent.player == "A"
        assert agent.use_mcp is True

    def test_act_with_parser(self):
        config = LLMConfig(model="gpt-4", api_key="test-key")
        parser = MagicMock(return_value=[10, 20, 30])
        agent = LLMAgent(
            player="A",
            player_token="token",
            arena_url="http://localhost:8000/api",
            llm_config=config,
            action_parser=parser,
        )

        with patch.object(agent, "call_llm", return_value="[10, 20, 30]"):
            action = agent.act({"system": "sys", "turn": "turn"}, {})
            parser.assert_called_once_with("[10, 20, 30]", {})
            assert action == [10, 20, 30]

    def test_act_without_parser(self):
        config = LLMConfig(model="gpt-4", api_key="test-key")
        agent = LLMAgent(
            player="A",
            player_token="token",
            arena_url="http://localhost:8000/api",
            llm_config=config,
        )

        with patch.object(agent, "call_llm", return_value="raw response"):
            action = agent.act({"system": "sys", "turn": "turn"}, {})
            assert action == "raw response"


class TestExtractToolText:
    def test_json_content(self):
        from mcp import types
        result = MagicMock()
        result.content = [types.TextContent(type="text", text='{"key": "value"}')]
        assert _extract_tool_text(result) == {"key": "value"}

    def test_non_json_content(self):
        from mcp import types
        result = MagicMock()
        result.content = [types.TextContent(type="text", text="not json")]
        assert _extract_tool_text(result) == {"raw": "not json"}

    def test_empty_content(self):
        result = MagicMock()
        result.content = []
        assert _extract_tool_text(result) == {}
