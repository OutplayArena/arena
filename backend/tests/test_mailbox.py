import pytest

from games.core.colonelblotto.config import BattlefieldConfig, ColonelBlottoExperimentConfig
from nash_arena.models.session import SessionModel
from nash_arena.session import GameSession


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


def test_send_and_receive_communication():
    session = GameSession.create(make_config(rounds=2))

    result = session.send_communication(session.player_tokens["A"], None, "Hello from A")
    assert result["from_player"] == "A"
    assert result["to_player"] is None
    assert result["status"] == "sent"

    log = session.get_communication_log()
    assert len(log) == 1
    assert log[0]["from_player"] == "A"
    assert log[0]["content"] == "Hello from A"


def test_player_filtered_communication_log():
    session = GameSession.create(make_config(rounds=2))
    session.send_communication(session.player_tokens["A"], None, "Hello")
    session.send_communication(session.player_tokens["B"], "A", "Hi A!")

    log_a = session.get_communication_log(token=session.player_tokens["A"])
    log_b = session.get_communication_log(token=session.player_tokens["B"])

    assert len(log_a) == 2
    assert len(log_b) == 2


def test_communication_with_specific_recipient():
    session = GameSession.create(make_config(rounds=2))

    result = session.send_communication(session.player_tokens["A"], "B", "Secret for B")
    assert result["to_player"] == "B"

    log = session.get_communication_log()
    assert log[0]["to_player"] == "B"


def test_communication_rejects_invalid_token():
    session = GameSession.create(make_config(rounds=2))

    with pytest.raises(ValueError, match="invalid player token"):
        session.send_communication("bad-token", None, "Hello")


def test_communication_enabled_for_blotto():
    from games.core.colonelblotto.engine import ColonelBlottoGame
    game = ColonelBlottoGame()
    comm = game.communication_config()
    assert comm.enabled is True
    assert comm.mode == "both"
    assert comm.max_messages_per_round > 0
    assert comm.max_message_length > 0


def test_communication_log_returns_empty_on_start():
    session = GameSession.create(make_config(rounds=2))
    assert session.get_communication_log() == []


def test_mailbox_methods():
    session = GameSession.create(make_config(rounds=2))
    session.send_communication(session.player_tokens["A"], None, "Hello")

    msgs = session.get_mailbox()
    assert len(msgs) == 1

    msgs_player = session.get_mailbox(player="A")
    assert len(msgs_player) >= 1


def test_get_mailbox_shows_messages_for_player():
    session = GameSession.create(make_config(rounds=2))
    session.send_communication(session.player_tokens["B"], "A", "Private for A")

    msgs_a = session.get_mailbox(player="A")
    assert len(msgs_a) == 1

    msgs_b = session.get_mailbox(player="B")
    assert len(msgs_b) == 1


def test_serialized_messages_match_state():
    session = GameSession.create(make_config(rounds=2))
    session.send_communication(session.player_tokens["A"], None, "Hello")
    session.send_communication(session.player_tokens["B"], "A", "Reply")

    serialized = session._get_serialized_messages()
    assert len(serialized) == 2
    assert serialized[0]["content"] == "Hello"
    assert serialized[1]["content"] == "Reply"


def test_communication_config_in_public_state():
    session = GameSession.create(make_config(rounds=2))
    state = session.public_state()
    assert "messages" in state
    assert "communication_config" in state
    assert state["communication_config"]["enabled"] is True


def test_session_model_has_messages_json_column():
    import sqlalchemy as sa
    col = SessionModel.__table__.c.get("messages_json")
    assert col is not None
    assert isinstance(col.type, sa.JSON)


def test_serialized_messages_empty_on_fresh_session():
    session = GameSession.create(make_config(rounds=2))
    assert session._get_serialized_messages() == []


def test_from_db_row_without_messages():
    session = GameSession.create(make_config(rounds=2))
    assert session.messages is None or session.messages == []
