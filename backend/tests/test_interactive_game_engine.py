"""Tests for the InteractiveGameEngine base class."""
import pytest

from arena.interactive_game_engine import InteractiveGameEngine


class _StubGame(InteractiveGameEngine):
    """Minimal concrete subclass for testing the base class defaults."""

    def initial_state(self):
        return {}

    def validate_action(self, action):
        return action is not None

    def validate_player_action(self, state, player, action):
        return True

    def apply_action(self, state, player, action):
        return state

    def is_terminal(self, state):
        return False

    def compute_results(self, state, session_id=None, config_hash=None):
        return {}

    def human_action_schema(self, config):
        return {"type": "object", "properties": {}}

    def format_human_action(self, raw_action, config):
        return raw_action

    def public_state(self, state, config, session_id, config_hash):
        return {"session_id": session_id}


class _PartialGame(InteractiveGameEngine):
    """Subclass that doesn't override the optional InteractiveGameEngine methods."""

    def initial_state(self):
        return {}

    def validate_action(self, action):
        return True

    def validate_player_action(self, state, player, action):
        return True

    def apply_action(self, state, player, action):
        return state

    def is_terminal(self, state):
        return False

    def compute_results(self, state, session_id=None, config_hash=None):
        return {}

    def public_state(self, state, config, session_id, config_hash):
        return {}


class TestAbstractBehavior:
    def test_human_action_schema_must_be_implemented(self):
        game = _PartialGame()
        with pytest.raises(NotImplementedError, match="human_action_schema"):
            game.human_action_schema(None)

    def test_format_human_action_must_be_implemented(self):
        game = _PartialGame()
        with pytest.raises(NotImplementedError, match="format_human_action"):
            game.format_human_action({}, None)


class TestDefaultImplementations:
    def test_validate_human_action_delegates_to_validate_action(self):
        game = _StubGame()
        assert game.validate_human_action(None, "A", "valid", None) is True
        assert game.validate_human_action(None, "A", None, None) is False

    def test_ui_metadata_default(self):
        game = _StubGame()
        meta = game.ui_metadata(None)
        assert meta == {"input_type": "text", "layout": "default"}

    def test_interactive_public_state_delegates_to_public_state(self):
        game = _StubGame()
        state = game.interactive_public_state(
            None, None, "session-123", "hash-456", player="A"
        )
        assert state == {"session_id": "session-123"}

    def test_get_available_agents_default_empty(self):
        game = _StubGame()
        assert game.get_available_agents(None) == []
