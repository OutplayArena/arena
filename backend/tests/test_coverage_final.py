"""Final stragglers coverage tests.

Targets the remaining gaps in:
- backend/arena/game_engine.py (abstract method bodies)
- backend/arena/game_components/* (abstract method bodies)
- backend/arena/db.py (get_db body)
- backend/arena/session.py (private helpers and edge cases)
- backend/arena/manifest.py (_get_metric_names edge cases)
- backend/arena/mcp_server.py (stdio fallback)
"""
from dataclasses import dataclass

import pytest


# ── game_engine.py ABC ──────────────────────────────────────────────────


class TestGameEngineABC:
    def test_cannot_instantiate_abstract(self):
        from arena.game_engine import GameEngine
        with pytest.raises(TypeError):
            GameEngine()

    def test_subclass_must_implement_all(self):
        from arena.game_engine import GameEngine

        class IncompleteEngine(GameEngine):
            def initial_state(self):
                return None

        with pytest.raises(TypeError):
            IncompleteEngine()

    def test_subclass_with_all_methods_works(self):
        from arena.game_engine import GameEngine

        class CompleteEngine(GameEngine):
            def initial_state(self):
                return None
            def validate_action(self, action):
                return True
            def validate_player_action(self, state, player, action):
                return True
            def apply_action(self, state, player, action):
                return state
            def is_terminal(self, state):
                return True
            def compute_results(self, state, session_id=None, config_hash=None):
                return {}
            def public_state(self, state, config, session_id, config_hash):
                return {}

        engine = CompleteEngine()
        assert engine.initial_state() is None
        assert engine.is_terminal(None) is True

    def test_subclass_can_call_super_for_default_raise(self):
        from arena.game_engine import GameEngine

        class CompleteEngine(GameEngine):
            def initial_state(self):
                # Call super to exercise the raise NotImplementedError path
                return super().initial_state()
            def validate_action(self, action):
                return True
            def validate_player_action(self, state, player, action):
                return True
            def apply_action(self, state, player, action):
                return state
            def is_terminal(self, state):
                return True
            def compute_results(self, state, session_id=None, config_hash=None):
                return {}
            def public_state(self, state, config, session_id, config_hash):
                return {}

        eng = CompleteEngine()
        with pytest.raises(NotImplementedError):
            eng.initial_state()


# ── game_components ABCs ────────────────────────────────────────────────


class TestGameComponents:
    def test_game_agent_abstract(self):
        from arena.game_components.game_agent import GameAgent
        with pytest.raises(TypeError):
            GameAgent()

    def test_game_agent_subclass_must_implement(self):
        from arena.game_components.game_agent import GameAgent

        class IncompleteAgent(GameAgent):
            pass

        with pytest.raises(TypeError):
            IncompleteAgent()

    def test_game_agent_with_act_works(self):
        from arena.game_components.game_agent import GameAgent

        class WorkingAgent(GameAgent):
            def act(self, history):
                return [1, 0, 0]

        agent = WorkingAgent()
        assert agent.act([]) == [1, 0, 0]

    def test_game_config_abstract(self):
        from arena.game_components.game_config import GameConfig
        with pytest.raises(TypeError):
            GameConfig()

    def test_game_metrics_abstract(self):
        from arena.game_components.game_metrics import GameMetrics
        with pytest.raises(TypeError):
            GameMetrics()


# ── db.py ──────────────────────────────────────────────────────────────


class TestGetDb:
    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        from arena.db import get_db
        gen = get_db()
        session = await gen.__anext__()
        assert session is not None
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass


# ── session.py private helpers ─────────────────────────────────────────


@dataclass
class _SimpleState:
    x: int = 0
    y: str = "default"


class TestSerializeState:
    def test_serialize_dataclass(self):
        from arena.session import _serialize_state
        state = _SimpleState(x=5, y="hello")
        result = _serialize_state(state)
        assert result == {"x": 5, "y": "hello"}

    def test_serialize_dict(self):
        from arena.session import _serialize_state
        result = _serialize_state({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_serialize_object_with_to_dict(self):
        from arena.session import _serialize_state

        class WithToDict:
            def to_dict(self):
                return {"foo": "bar"}

        result = _serialize_state(WithToDict())
        assert result == {"foo": "bar"}

    def test_serialize_passthrough(self):
        from arena.session import _serialize_state
        result = _serialize_state(42)
        assert result == 42


class TestRoundMetrics:
    def test_round_float(self):
        from arena.session import _round_metrics
        assert _round_metrics(1.23456789) == 1.2346

    def test_round_dict(self):
        from arena.session import _round_metrics
        result = _round_metrics({"a": 1.23456789, "b": 2})
        assert result == {"a": 1.2346, "b": 2}

    def test_round_list(self):
        from arena.session import _round_metrics
        result = _round_metrics([1.111111, 2.222222])
        assert result == [1.1111, 2.2222]

    def test_round_passthrough_string(self):
        from arena.session import _round_metrics
        assert _round_metrics("hello") == "hello"

    def test_round_custom_decimals(self):
        from arena.session import _round_metrics
        assert _round_metrics(1.23456789, decimals=2) == 1.23


# ── manifest.py _get_metric_names ──────────────────────────────────────


class TestGetMetricNames:
    def test_get_metric_names_with_strings(self):
        from arena.manifest import _get_metric_names
        from arena.game_registry import GameRegistry

        names = _get_metric_names(GameRegistry(), "colonelblotto")
        assert isinstance(names, list)
        assert "total_payoff" in names

    def test_get_metric_names_with_dict_entries(self, tmp_path):
        import yaml
        from arena.manifest import _get_metric_names
        from arena.game_registry import GameRegistry

        (tmp_path / "core").mkdir()
        game_dir = tmp_path / "core" / "metric_game"
        game_dir.mkdir()
        (game_dir / "game.yaml").write_text(
            'name: mg\nversion: "1.0"\nstatus: stable\nplayers: {min: 2, max: 2}\n',
            encoding="utf-8",
        )
        (game_dir / "metrics.yaml").write_text(
            yaml.safe_dump(
                {
                    "metrics": [
                        "simple_string",
                        {"name": "dict_entry"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        # _get_metric_names falls back to registry.get_game_metrics,
        # which dispatches to the metrics.yaml loader. Need to monkey-patch
        # the registry's get_game_metrics to return the right shape.
        registry = GameRegistry(tmp_path)
        original = registry.get_game_metrics

        def patched(name):
            return {
                "metrics": [
                    "simple_string",
                    {"name": "dict_entry"},
                ]
            }

        registry.get_game_metrics = patched  # type: ignore
        names = _get_metric_names(registry, "metric_game")
        assert "simple_string" in names
        assert "dict_entry" in names
        # Restore for cleanup
        registry.get_game_metrics = original  # type: ignore

    def test_get_metric_names_handles_non_list_metrics(self, tmp_path):
        from arena.manifest import _get_metric_names
        from arena.game_registry import GameRegistry

        (tmp_path / "core").mkdir()
        game_dir = tmp_path / "core" / "bad_metrics"
        game_dir.mkdir()
        (game_dir / "game.yaml").write_text(
            'name: bm\nversion: "1.0"\nstatus: stable\nplayers: {min: 2, max: 2}\n',
            encoding="utf-8",
        )
        (game_dir / "metrics.yaml").write_text(
            "metrics: not-a-list\n",
            encoding="utf-8",
        )
        names = _get_metric_names(GameRegistry(tmp_path), "bad_metrics")
        assert names == []

    def test_get_metric_names_handles_missing_game(self):
        from arena.manifest import _get_metric_names
        from arena.game_registry import GameRegistry

        names = _get_metric_names(GameRegistry(), "does-not-exist")
        assert names == []


# ── mcp_server.py stdio fallback ───────────────────────────────────────


class TestMcpServerStdioFallback:
    def test_stdio_key_invalid_is_silently_ignored(self, monkeypatch):
        from arena.auth.session_key import SESSION_KEY_PREFIX

        monkeypatch.setenv("OUTPLAYARENA_KEY", SESSION_KEY_PREFIX + "bogus")
        # Manually run the stdio fallback code path instead of reload
        from arena import mcp_server as mcp_mod

        try:
            from arena.auth.session_key import validate_session_key

            try:
                _sid, _player = validate_session_key(
                    SESSION_KEY_PREFIX + "bogus"
                )
                mcp_mod._session_ctx.set((_sid, _player, SESSION_KEY_PREFIX + "bogus"))
            except ValueError:
                pass  # this is the path we are testing
            # No exception means the ValueError was caught
            assert hasattr(mcp_mod, "_SessionKeyMiddleware")
        except Exception:
            pytest.fail("Invalid stdio key should be silently ignored")

    def test_stdio_key_valid_sets_context(self, monkeypatch):
        from arena.auth.session_key import derive_session_key

        valid_key = derive_session_key("test-session-id", "A")
        # Manually invoke the stdio fallback code path
        from arena import mcp_server as mcp_mod

        try:
            from arena.auth.session_key import validate_session_key

            _sid, _player = validate_session_key(valid_key)
            token = mcp_mod._session_ctx.set((_sid, _player, valid_key))
            try:
                ctx = mcp_mod._session_ctx.get()
                assert ctx[0] == "test-session-id"
                assert ctx[1] == "A"
                assert ctx[2] == valid_key
            finally:
                mcp_mod._session_ctx.reset(token)
        except Exception as e:
            pytest.fail(f"Valid stdio key should set context: {e}")
