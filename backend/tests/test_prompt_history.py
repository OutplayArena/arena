"""Regression coverage for prompt and history contracts (#164–#166)."""

from copy import deepcopy

import pytest
import yaml
from arena.game_registry import CATALOG_ROOT, GameRegistry
from arena.session import GameSession


@pytest.mark.parametrize(
    "game_name", [game["slug"] for game in GameRegistry().list_games()]
)
@pytest.mark.parametrize("variant", ["neutral", "gain_framed", "loss_framed"])
def test_catalog_observations_render_after_layout_migration(game_name, variant):
    registry = GameRegistry()
    config = registry.config_from_request(
        registry.get_game(game_name)["example_config"]
    )
    session = GameSession.create(config)
    player = session.public_state()["awaiting"][0]
    observation = registry.render_observation(
        game_name,
        session.public_state(),
        config.to_dict(),
        player,
        variant,
    )
    assert observation["system"]
    assert observation["turn"]
    assert "{{" not in observation["system"] + observation["turn"]
    if variant != "neutral":
        neutral = registry.render_observation(
            game_name,
            session.public_state(),
            config.to_dict(),
            player,
        )
        assert observation["system"].endswith(neutral["system"])
        assert observation["system"] != neutral["system"]


@pytest.mark.parametrize(
    "path",
    sorted(CATALOG_ROOT.glob("*/*/prompts.yaml"))
    + [CATALOG_ROOT / "_template" / "prompts.yaml"],
    ids=lambda path: path.parent.name,
)
def test_prompt_files_preserve_lines_and_use_canonical_keys(path):
    nodes = dict(yaml.compose(path.read_text()).value)
    fields = {key.value: value for key, value in nodes.items()}
    assert "turn" not in fields
    assert "action_format" in fields
    turn_keys = (
        ("proposer_state", "responder_state")
        if path.parent.name == "ultimatum"
        else ("state",)
    )
    for key in ("system", *turn_keys):
        assert fields[key].style == "|"
    variants = {key.value: value for key, value in fields["variants"].value}
    assert set(variants) == {"neutral", "gain_framed", "loss_framed"}
    assert all(value.style == "|" for value in variants.values())


@pytest.fixture(
    params=["colonelblotto", "prisonersdilemma", "rock_paper_scissors", "public_goods"]
)
def played_session(request):
    registry = GameRegistry()
    payload = {"game": request.param, "rounds": 5}
    if request.param == "colonelblotto":
        payload.update(
            variant="classic",
            players=2,
            budget=[10, 10],
            battlefields=[{"id": str(i), "value": 1.0} for i in range(3)],
        )
        actions = {"A": [10, 0, 0], "B": [0, 5, 5]}
    elif request.param == "prisonersdilemma":
        actions = {"A": "cooperate", "B": "defect"}
    elif request.param == "rock_paper_scissors":
        actions = {"A": "rock", "B": "scissors"}
    else:
        payload["players"] = 3
        actions = {"A": 0.0, "B": 0.0, "C": 0.0}
    session = GameSession.create(registry.config_from_request(payload))
    for player, action in actions.items():
        session.submit_action(player, action)
    return session


@pytest.mark.parametrize("player", ["A", "B"])
def test_round_outcomes_render_from_each_players_perspective(played_session, player):
    session = played_session
    entry = session.state.history[0]
    assert "payoffs" in entry
    assert "scores" not in entry
    assert "round_payoffs" not in entry
    observation = GameRegistry().render_observation(
        session.config.game,
        session.public_state(),
        session.config.to_dict(),
        player,
    )
    text = observation["turn"]
    opponent = "B" if player == "A" else "A"
    if "allocations" in entry:
        expected = (
            f"You allocated {entry['allocations'][player]}, "
            f"opponent allocated {entry['allocations'][opponent]} → you scored {entry['payoffs'][player]}"
        )
    elif "actions" in entry:
        verb = "earned" if session.config.game == "prisonersdilemma" else "scored"
        expected = (
            f"You played {entry['actions'][player]}, opponent played {entry['actions'][opponent]} "
            f"→ you {verb} {entry['payoffs'][player]}"
        )
    else:
        expected = f"Your payoff: {entry['payoffs'][player]}"
    assert expected in text
    assert len([line for line in text.splitlines() if line.startswith("Round 1:")]) == 1
    assert "'total_scores':" not in text
    assert "'winner':" not in text
    payload, step = session.build_wandb_round_payloads()[0]
    assert step == 1
    assert payload[f"scores/{player}"] == entry["payoffs"][player]


@pytest.mark.parametrize("variant", ["gain_framed", "loss_framed"])
def test_migrated_prompts_apply_variants_without_dropping_rules(
    played_session, variant
):
    session = played_session
    registry = GameRegistry()
    prompts = registry.get_game_prompts(session.config.game)
    observation = registry.render_observation(
        session.config.game,
        session.public_state(),
        session.config.to_dict(),
        "A",
        variant,
    )
    framing = prompts["variants"][variant].strip()
    assert observation["system"].startswith(framing + "\n\n")
    assert "COMMUNICATION:" in observation["system"]


@pytest.mark.parametrize("legacy_key", ["scores", "round_payoffs"])
def test_saved_history_still_renders_and_logs_without_mutation(
    played_session, legacy_key
):
    session = played_session
    entry = session.state.history[0]
    payoffs = entry.pop("payoffs")
    entry[legacy_key] = payoffs
    original = deepcopy(session.state.history)
    observation = GameRegistry().render_observation(
        session.config.game,
        session.public_state(),
        session.config.to_dict(),
        "A",
    )
    assert str(payoffs["A"]) in observation["turn"]
    assert session.build_wandb_round_payloads()[0][0]["scores/A"] == payoffs["A"]
    assert session.state.history == original


@pytest.mark.parametrize("game_name", ["colonelblotto", "rock_paper_scissors"])
def test_forfeited_round_uses_payoffs_and_renders(game_name):
    registry = GameRegistry()
    payload = {"game": game_name, "rounds": 2}
    if game_name == "colonelblotto":
        payload.update(
            variant="classic",
            players=2,
            budget=[10, 10],
            battlefields=[{"id": "field", "value": 1.0}],
        )
    session = GameSession.create(registry.config_from_request(payload))
    session.state = session.game.forfeit_round(session.state, "A")
    assert session.state.history[0]["payoffs"] == {"A": 0.0, "B": 1.0}
    for player in ("A", "B"):
        observation = registry.render_observation(
            game_name,
            session.public_state(),
            session.config.to_dict(),
            player,
        )
        assert (
            f"you scored {session.state.history[0]['payoffs'][player]}"
            in observation["turn"]
        )


def test_blotto_history_keeps_inbox_and_exploitability_warning():
    registry = GameRegistry()
    config = registry.config_from_request(
        {
            "game": "colonelblotto",
            "variant": "classic",
            "players": 2,
            "rounds": 5,
            "budget": [10, 10],
            "battlefields": [{"id": str(i), "value": 1.0} for i in range(3)],
        }
    )
    session = GameSession.create(config)
    for _ in range(3):
        session.submit_action("A", [10, 0, 0])
        session.submit_action("B", [0, 5, 5])
    state = session.public_state()
    state["messages"] = [{"sender": "B", "recipient": "A", "content": "hello"}]
    observation = registry.render_observation(
        "colonelblotto", state, config.to_dict(), "A"
    )
    assert "Inbox:" in observation["turn"]
    assert "hello" in observation["turn"]
    warning = registry._build_observation_context(
        "colonelblotto", state, config.to_dict(), "A"
    )["exploitability_warning"]
    assert warning in observation["turn"]
    assert (
        len(
            [
                line
                for line in observation["turn"].splitlines()
                if "You allocated" in line
            ]
        )
        == 3
    )
