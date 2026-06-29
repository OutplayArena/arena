"""Tests for the one-call quick_play helper."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from outplayarena_sdk.quick_play import quick_play


def _fake_create_experiment(mcp_url=None):
    """Build a fake create_experiment response."""
    return {
        "session_id": "sess-1",
        "player_tokens": {"A": "nks_A", "B": "nks_B"},
        "config": {"game": "ultimatum", "seed": 42},
        **({"mcp_url": mcp_url} if mcp_url else {}),
    }


class TestQuickPlayAsync:
    @pytest.mark.asyncio
    async def test_runs_single_agent(self):
        """Single-agent case: just runs that one agent."""
        from outplayarena_sdk.quick_play import _quick_play_async

        with patch("outplayarena_sdk.quick_play.ArenaClient") as MockClient, \
             patch("outplayarena_sdk.quick_play.get_agent_class") as mock_get:
            mock_rest = MagicMock()
            mock_rest.create_experiment.return_value = _fake_create_experiment()
            MockClient.return_value = mock_rest

            mock_agent_cls = MagicMock()
            mock_agent_instance = MagicMock()
            mock_agent_instance.run = AsyncMock(return_value={"winner": "A"})
            mock_agent_cls.return_value = mock_agent_instance
            mock_get.return_value = mock_agent_cls

            result = await _quick_play_async(
                game="ultimatum",
                agents={"A": {"model": "gpt-4", "api_key": "sk-test"}},
            )

            assert result == {"winner": "A"}
            mock_rest.create_experiment.assert_called_once()
            mock_agent_instance.run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_runs_two_agents_via_gather(self):
        from outplayarena_sdk.quick_play import _quick_play_async

        with patch("outplayarena_sdk.quick_play.ArenaClient") as MockClient, \
             patch("outplayarena_sdk.quick_play.get_agent_class") as mock_get:
            mock_rest = MagicMock()
            mock_rest.create_experiment.return_value = _fake_create_experiment()
            MockClient.return_value = mock_rest

            agent_a = MagicMock()
            agent_a.run = AsyncMock(return_value={"winner": "A"})
            agent_b = MagicMock()
            agent_b.run = AsyncMock(return_value={"winner": "A"})
            mock_agent_cls = MagicMock(side_effect=[agent_a, agent_b])
            mock_get.return_value = mock_agent_cls

            result = await _quick_play_async(
                game="ultimatum",
                agents={
                    "A": {"model": "gpt-4", "api_key": "sk-test"},
                    "B": {"model": "claude", "api_key": "sk-ant-test"},
                },
            )

            assert result == {"winner": "A"}
            assert mock_agent_cls.call_count == 2

    @pytest.mark.asyncio
    async def test_uses_mcp_url_from_response(self):
        from outplayarena_sdk.quick_play import _quick_play_async

        with patch("outplayarena_sdk.quick_play.ArenaClient") as MockClient, \
             patch("outplayarena_sdk.quick_play.get_agent_class") as mock_get:
            mock_rest = MagicMock()
            mock_rest.create_experiment.return_value = _fake_create_experiment(
                mcp_url="http://mcp:9999"
            )
            MockClient.return_value = mock_rest

            agent = MagicMock()
            agent.run = AsyncMock(return_value={"winner": "A"})
            mock_agent_cls = MagicMock(return_value=agent)
            mock_get.return_value = mock_agent_cls

            await _quick_play_async(
                game="ultimatum",
                agents={"A": {"model": "gpt-4", "api_key": "sk-test"}},
            )

            # Agent was constructed with mcp_url from the response
            call_kwargs = mock_agent_cls.call_args.kwargs
            assert call_kwargs["mcp_url"] == "http://mcp:9999"

    @pytest.mark.asyncio
    async def test_explicit_mcp_url_overrides_response(self):
        from outplayarena_sdk.quick_play import _quick_play_async

        with patch("outplayarena_sdk.quick_play.ArenaClient") as MockClient, \
             patch("outplayarena_sdk.quick_play.get_agent_class") as mock_get:
            mock_rest = MagicMock()
            mock_rest.create_experiment.return_value = _fake_create_experiment(
                mcp_url="http://mcp-from-response:9999"
            )
            MockClient.return_value = mock_rest

            agent = MagicMock()
            agent.run = AsyncMock(return_value={})
            mock_agent_cls = MagicMock(return_value=agent)
            mock_get.return_value = mock_agent_cls

            await _quick_play_async(
                game="ultimatum",
                agents={"A": {"model": "gpt-4", "api_key": "sk-test"}},
                mcp_url="http://explicit-mcp:9998",
            )

            call_kwargs = mock_agent_cls.call_args.kwargs
            assert call_kwargs["mcp_url"] == "http://explicit-mcp:9998"

    @pytest.mark.asyncio
    async def test_session_id_passed_from_create_response(self):
        """As of v0.2.0 the agent must receive the session_id from the
        create_experiment response (the SDK no longer derives it from
        the token)."""
        from outplayarena_sdk.quick_play import _quick_play_async

        with patch("outplayarena_sdk.quick_play.ArenaClient") as MockClient, \
             patch("outplayarena_sdk.quick_play.get_agent_class") as mock_get:
            mock_rest = MagicMock()
            mock_rest.create_experiment.return_value = _fake_create_experiment()
            MockClient.return_value = mock_rest

            agent = MagicMock()
            agent.run = AsyncMock(return_value={"winner": "A"})
            mock_agent_cls = MagicMock(return_value=agent)
            mock_get.return_value = mock_agent_cls

            await _quick_play_async(
                game="ultimatum",
                agents={
                    "A": {"model": "gpt-4", "api_key": "sk-test"},
                    "B": {"model": "claude", "api_key": "sk-ant-test"},
                },
            )

            assert mock_agent_cls.call_count == 2
            for call in mock_agent_cls.call_args_list:
                assert call.kwargs["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_no_jwt_secret_kwarg_on_agent_or_helper(self):
        """Regression guard: the SDK must not accept a jwt_secret kwarg
        (it was a shared HMAC secret in v0.1.x; the server keeps it, the
        client does not)."""
        import inspect
        from outplayarena_sdk.quick_play import _quick_play_async

        with patch("outplayarena_sdk.quick_play.ArenaClient") as MockClient, \
             patch("outplayarena_sdk.quick_play.get_agent_class") as mock_get:
            mock_rest = MagicMock()
            mock_rest.create_experiment.return_value = _fake_create_experiment()
            MockClient.return_value = mock_rest

            agent = MagicMock()
            agent.run = AsyncMock(return_value={"winner": "A"})
            mock_agent_cls = MagicMock(return_value=agent)
            mock_get.return_value = mock_agent_cls

            await _quick_play_async(
                game="ultimatum",
                agents={"A": {"model": "gpt-4", "api_key": "sk-test"}},
            )

            call_kwargs = mock_agent_cls.call_args.kwargs
            assert "jwt_secret" not in call_kwargs
            assert "jwt_secret" not in inspect.signature(_quick_play_async).parameters


class TestSyncWrapper:
    def test_quick_play_calls_asyncio_run(self):
        with patch("outplayarena_sdk.quick_play._quick_play_async") as mock_async:
            mock_async.return_value = {"winner": "A"}

            # Patch asyncio.run to capture the coroutine
            with patch("outplayarena_sdk.quick_play.asyncio.run") as mock_run:
                mock_run.return_value = {"winner": "A"}

                result = quick_play(
                    game="ultimatum",
                    agents={"A": {"model": "gpt-4", "api_key": "sk-test"}},
                )

                assert result == {"winner": "A"}
                mock_run.assert_called_once()
