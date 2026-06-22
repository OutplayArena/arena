"""Tests for all 10 per-game :class:`BaseAgent` subclasses."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os


from outplaylabs_arena_sdk.agents.games import (
    BattleOfTheSexesAgent,
    CentipedeAgent,
    ColonelBlottoAgent,
    CournotDuopolyAgent,
    PrisonersDilemmaAgent,
    PublicGoodsAgent,
    RockPaperScissorsAgent,
    StagHuntAgent,
    TexasHoldEmAgent,
    UltimatumAgent,
)
from outplaylabs_arena_sdk.base import LLMConfig


def _token(player: str = "A") -> str:
    secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    session_id = "test-session-1"
    h = hashlib.sha256(secret.encode("utf-8")).digest()
    payload = f"{session_id}:{player}"
    sig = hmac.new(h, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{session_id}:{player}:{sig}"
    encoded = base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8").rstrip("=")
    return f"nks_{encoded}"


def _agent(cls, **kwargs):
    return cls(
        player="A",
        player_token=_token(),
        arena_url="http://x",
        llm_config=LLMConfig(model="gpt-4o", api_key="k"),
        **kwargs,
    )


class TestColonelBlotto:
    def test_parse_action_valid(self):
        agent = _agent(ColonelBlottoAgent)
        state = {"battlefields": [{}, {}, {}], "budgets": {"A": 100}}
        assert agent.parse_action("[40, 30, 30]", state) == [40, 30, 30]

    def test_parse_action_invalid_falls_back(self):
        agent = _agent(ColonelBlottoAgent)
        state = {"battlefields": [{}, {}, {}], "budgets": {"A": 100}}
        result = agent.parse_action("garbage", state)
        assert sum(result) == 100
        assert len(result) == 3

    def test_hint_mentions_battlefields(self):
        agent = _agent(ColonelBlottoAgent)
        agent._last_state = {"battlefields": [{}, {}, {}], "budgets": {"A": 100}}
        assert "3" in agent.action_format_hint()
        assert "100" in agent.action_format_hint()


class TestUltimatum:
    def test_proposer_parses_offer(self):
        agent = _agent(UltimatumAgent)
        agent._last_state = {
            "phase": "awaiting_proposal",
            "proposer": "A",
            "awaiting": ["A"],
            "total": 100.0,
            "min_offer": 1.0,
        }
        assert agent.parse_action("I offer 40", {}) == 40.0

    def test_responder_parses_accept(self):
        agent = _agent(UltimatumAgent)
        agent._last_state = {
            "phase": "awaiting_response",
            "proposer": "B",
            "responder": "A",
            "awaiting": ["A"],
        }
        assert agent.parse_action("I accept", {}) == "accept"

    def test_responder_parses_reject(self):
        agent = _agent(UltimatumAgent)
        agent._last_state = {
            "phase": "awaiting_response",
            "proposer": "B",
            "responder": "A",
            "awaiting": ["A"],
        }
        assert agent.parse_action("I reject this", {}) == "reject"


class TestPrisonersDilemma:
    def test_cooperate(self):
        agent = _agent(PrisonersDilemmaAgent)
        state = {"scenario": {"cooperate_label": "cooperate", "defect_label": "defect"}}
        assert agent.parse_action("I will cooperate", state) == "cooperate"

    def test_defect(self):
        agent = _agent(PrisonersDilemmaAgent)
        state = {"scenario": {"cooperate_label": "cooperate", "defect_label": "defect"}}
        assert agent.parse_action("defect now", state) == "defect"

    def test_unknown_defaults_to_defect(self):
        agent = _agent(PrisonersDilemmaAgent)
        state = {"scenario": {"cooperate_label": "cooperate", "defect_label": "defect"}}
        assert agent.parse_action("garbage", state) == "defect"


class TestRockPaperScissors:
    def test_rock(self):
        agent = _agent(RockPaperScissorsAgent)
        assert agent.parse_action("I choose rock", {}) == "rock"

    def test_paper(self):
        agent = _agent(RockPaperScissorsAgent)
        assert agent.parse_action("paper please", {}) == "paper"

    def test_scissors(self):
        agent = _agent(RockPaperScissorsAgent)
        assert agent.parse_action("scissors", {}) == "scissors"

    def test_unknown_defaults_to_rock(self):
        agent = _agent(RockPaperScissorsAgent)
        assert agent.parse_action("garbage", {}) == "rock"


class TestBattleOfTheSexes:
    def test_opera(self):
        agent = _agent(BattleOfTheSexesAgent)
        state = {"option_a": "opera", "option_b": "football"}
        assert agent.parse_action("I want opera", state) == "opera"

    def test_football(self):
        agent = _agent(BattleOfTheSexesAgent)
        state = {"option_a": "opera", "option_b": "football"}
        assert agent.parse_action("football", state) == "football"


class TestStagHunt:
    def test_stag(self):
        agent = _agent(StagHuntAgent)
        assert agent.parse_action("stag", {}) == "stag"

    def test_hare(self):
        agent = _agent(StagHuntAgent)
        assert agent.parse_action("hare", {}) == "hare"

    def test_unknown_defaults_to_stag(self):
        agent = _agent(StagHuntAgent)
        assert agent.parse_action("garbage", {}) == "stag"


class TestCentipede:
    def test_take(self):
        agent = _agent(CentipedeAgent)
        assert agent.parse_action("take", {}) == "take"

    def test_pass(self):
        agent = _agent(CentipedeAgent)
        assert agent.parse_action("I pass", {}) == "pass"

    def test_unknown_defaults_to_pass(self):
        agent = _agent(CentipedeAgent)
        assert agent.parse_action("garbage", {}) == "pass"


class TestCournotDuopoly:
    def test_simple(self):
        agent = _agent(CournotDuopolyAgent)
        state = {"max_quantity": 100}
        assert agent.parse_action("I produce 25", state) == 25.0

    def test_clamps_to_max(self):
        agent = _agent(CournotDuopolyAgent)
        state = {"max_quantity": 100}
        assert agent.parse_action("I produce 200", state) == 100.0

    def test_negative_clamps_to_zero(self):
        agent = _agent(CournotDuopolyAgent)
        state = {"max_quantity": 100}
        assert agent.parse_action("I produce -5", state) == 0.0


class TestPublicGoods:
    def test_contribute(self):
        agent = _agent(PublicGoodsAgent)
        state = {"endowment": 20}
        assert agent.parse_action("I contribute 10", state) == 10.0

    def test_clamp_to_endowment(self):
        agent = _agent(PublicGoodsAgent)
        state = {"endowment": 20}
        assert agent.parse_action("I contribute 50", state) == 20.0

    def test_no_number_returns_half(self):
        agent = _agent(PublicGoodsAgent)
        state = {"endowment": 20}
        assert agent.parse_action("nothing", state) == 10.0


class TestTexasHoldEm:
    def test_check(self):
        agent = _agent(TexasHoldEmAgent)
        move, amount = agent.parse_action("I check", {})
        assert move == "check"
        assert amount == 0.0

    def test_fold(self):
        agent = _agent(TexasHoldEmAgent)
        move, amount = agent.parse_action("I fold my hand", {})
        assert move == "fold"
        assert amount == 0.0

    def test_bet_with_amount(self):
        agent = _agent(TexasHoldEmAgent)
        move, amount = agent.parse_action("I bet 50", {})
        assert move == "bet"
        assert amount == 50.0

    def test_raise_with_amount(self):
        agent = _agent(TexasHoldEmAgent)
        move, amount = agent.parse_action("raise 25", {})
        assert move == "raise"
        assert amount == 25.0

    def test_all_in(self):
        agent = _agent(TexasHoldEmAgent)
        move, amount = agent.parse_action("all in", {})
        assert move == "all_in"
        assert amount == 0.0

    def test_unknown_defaults_to_fold(self):
        agent = _agent(TexasHoldEmAgent)
        move, _ = agent.parse_action("garbage", {})
        assert move == "fold"
