"""Tests for mailbox functionality."""
from games.core.colonelblotto.config import BattlefieldConfig, ColonelBlottoExperimentConfig
from outplaylabs_arena.session import GameSession


def make_config(rounds=2):
    return ColonelBlottoExperimentConfig(
        game="colonelblotto",
        variant="classic",
        players=2,
        budget=[10, 10],
        battlefields=[
            BattlefieldConfig(id="A", value=1.0),
            BattlefieldConfig(id="B", value=1.0),
            BattlefieldConfig(id="C", value=1.0),
        ],
        rounds=rounds,
        seed=42,
    )


def test_add_message_to_session():
    """Test adding a message to a game session."""
    config = make_config()
    session = GameSession.create(config)
    
    # Initially no messages (None or empty list)
    assert session.messages is None or session.messages == []
    
    # Add a message
    msg = session.add_message(sender="A", content="Hello!", recipient="all")
    
    # Check message was added
    assert len(session.messages) == 1
    assert msg["sender"] == "A"
    assert msg["content"] == "Hello!"
    assert msg["recipient"] == "all"
    assert msg["round"] == 1
    assert "id" in msg


def test_multiple_messages():
    """Test adding multiple messages."""
    config = make_config()
    session = GameSession.create(config)
    
    session.add_message(sender="A", content="First", recipient="all")
    session.add_message(sender="B", content="Second", recipient="A")
    session.add_message(sender="A", content="Third", recipient="all")
    
    assert len(session.messages) == 3
    assert session.messages[0]["content"] == "First"
    assert session.messages[1]["content"] == "Second"
    assert session.messages[1]["recipient"] == "A"
    assert session.messages[2]["content"] == "Third"


def test_messages_in_public_state():
    """Test that messages are included in public state."""
    config = make_config()
    session = GameSession.create(config)
    
    session.add_message(sender="A", content="Test message", recipient="all")
    
    state = session.public_state()
    
    assert "messages" in state
    assert len(state["messages"]) == 1
    assert state["messages"][0]["content"] == "Test message"


def test_messages_persist_after_action():
    """Test that messages persist after game actions."""
    config = make_config()
    session = GameSession.create(config)
    
    # Add a message
    session.add_message(sender="A", content="Before action", recipient="all")
    
    # Submit an action
    session.submit_action("A", [5, 3, 2])
    
    # Add another message
    session.add_message(sender="B", content="After action", recipient="all")
    
    # Both messages should be present
    assert len(session.messages) == 2
    assert session.messages[0]["content"] == "Before action"
    assert session.messages[1]["content"] == "After action"
    
    # Messages should be in public state
    state = session.public_state()
    assert len(state["messages"]) == 2
