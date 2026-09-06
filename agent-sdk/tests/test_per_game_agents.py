"""Tests for all 11 per-game :class:`BaseAgent` subclasses."""
from __future__ import annotations


from outplayarena_sdk.agents.games import (
    BattleOfTheSexesAgent,
    CentipedeAgent,
    ChickenGameAgent,
    ColonelBlottoAgent,
    CournotDuopolyAgent,
    PrisonersDilemmaAgent,
    PublicGoodsAgent,
    RockPaperScissorsAgent,
    StagHuntAgent,
    TexasHoldEmAgent,
    UltimatumAgent,
    VickreyAuctionAgent,
)
from outplayarena_sdk.base import LLMConfig


def _token(player: str = "A") -> str:
    """Return an opaque session-key string for tests (v0.2.0+)."""
    return f"nks_test_token_for_{player}"


def _agent(cls, **kwargs):
    return cls(
        player="A",
        player_token=_token(),
        session_id="test-session-1",
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

    def test_actions_constant(self):
        from outplayarena_sdk.agents.games.prisonersdilemma import (
            PrisonersDilemmaAgent,
        )
        assert PrisonersDilemmaAgent.ACTIONS == ("cooperate", "defect")


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


class TestChickenGame:
    def test_swerve(self):
        agent = _agent(ChickenGameAgent)
        assert agent.parse_action("swerve", {}) == "swerve"

    def test_dare(self):
        agent = _agent(ChickenGameAgent)
        assert agent.parse_action("dare", {}) == "dare"

    def test_unknown_defaults_to_swerve(self):
        agent = _agent(ChickenGameAgent)
        assert agent.parse_action("garbage", {}) == "swerve"


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

    def test_hint_includes_max_quantity(self):
        agent = _agent(CournotDuopolyAgent)
        agent._last_state = {"max_quantity": 50}
        hint = agent.action_format_hint()
        assert "50" in hint
        assert "non-negative" in hint

    def test_hint_fallback_when_no_state(self):
        agent = _agent(CournotDuopolyAgent)
        agent._last_state = None
        hint = agent.action_format_hint()
        assert "non-negative" in hint
        assert "up to" not in hint

    def test_hint_fallback_when_max_quantity_invalid(self):
        agent = _agent(CournotDuopolyAgent)
        agent._last_state = {"max_quantity": "not a number"}
        hint = agent.action_format_hint()
        assert "non-negative" in hint


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

    def test_hint_includes_endowment(self):
        agent = _agent(PublicGoodsAgent)
        agent._last_state = {"endowment": 30}
        hint = agent.action_format_hint()
        assert "30" in hint
        assert "contribution" in hint

    def test_hint_fallback_when_no_state(self):
        agent = _agent(PublicGoodsAgent)
        agent._last_state = None
        hint = agent.action_format_hint()
        assert "contribution" in hint
        assert "up to" not in hint

    def test_hint_fallback_when_endowment_invalid(self):
        agent = _agent(PublicGoodsAgent)
        agent._last_state = {"endowment": "not a number"}
        hint = agent.action_format_hint()
        assert "contribution" in hint

    def test_parse_action_fallback_endowment_when_invalid(self):
        agent = _agent(PublicGoodsAgent)
        # No endowment in state → defaults to 20.
        result = agent.parse_action("15", {})
        assert result == 15.0

        # Negative endowment → defaults to 20.
        result = agent.parse_action("15", {"endowment": -5})
        assert result == 15.0

    def test_parse_action_fallback_when_state_has_max(self):
        agent = _agent(CournotDuopolyAgent)
        # No max_quantity in state → defaults to 100.
        result = agent.parse_action("75", {})
        assert result == 75.0

        # Negative max → defaults to 100.
        result = agent.parse_action("75", {"max_quantity": -10})
        assert result == 75.0


class TestVickreyAuction:
    def test_simple(self):
        agent = _agent(VickreyAuctionAgent)
        state = {"max_bid": 200}
        assert agent.parse_action("I bid 75", state) == 75.0

    def test_clamps_to_max(self):
        agent = _agent(VickreyAuctionAgent)
        state = {"max_bid": 200}
        assert agent.parse_action("I bid 500", state) == 200.0

    def test_negative_clamps_to_zero(self):
        agent = _agent(VickreyAuctionAgent)
        state = {"max_bid": 200}
        assert agent.parse_action("I bid -5", state) == 0.0

    def test_hint_includes_max_bid(self):
        agent = _agent(VickreyAuctionAgent)
        agent._last_state = {"max_bid": 150}
        hint = agent.action_format_hint()
        assert "150" in hint
        assert "non-negative" in hint

    def test_hint_fallback_when_no_state(self):
        agent = _agent(VickreyAuctionAgent)
        agent._last_state = None
        hint = agent.action_format_hint()
        assert "non-negative" in hint
        assert "up to" not in hint

    def test_hint_fallback_when_max_bid_invalid(self):
        agent = _agent(VickreyAuctionAgent)
        agent._last_state = {"max_bid": "not a number"}
        hint = agent.action_format_hint()
        assert "non-negative" in hint

    def test_parse_action_fallback_when_max_bid_invalid(self):
        agent = _agent(VickreyAuctionAgent)
        # No max_bid in state → defaults to 200.
        result = agent.parse_action("75", {})
        assert result == 75.0

        # Negative max_bid → defaults to 200.
        result = agent.parse_action("75", {"max_bid": -10})
        assert result == 75.0


class TestTexasHoldEm:
    def test_check(self):
        agent = _agent(TexasHoldEmAgent)
        assert agent.parse_action("I check", {}) == "check"

    def test_fold(self):
        agent = _agent(TexasHoldEmAgent)
        assert agent.parse_action("I fold my hand", {}) == "fold"

    def test_bet_with_amount(self):
        agent = _agent(TexasHoldEmAgent)
        # parse_action returns the move name string; the engine uses a
        # fixed bet size, so the amount is dropped.
        assert agent.parse_action("I bet 50", {}) == "bet"

    def test_raise_with_amount(self):
        agent = _agent(TexasHoldEmAgent)
        assert agent.parse_action("raise 25", {}) == "raise"

    def test_all_in(self):
        agent = _agent(TexasHoldEmAgent)
        assert agent.parse_action("all in", {}) == "all_in"

    def test_unknown_defaults_to_fold(self):
        agent = _agent(TexasHoldEmAgent)
        assert agent.parse_action("garbage", {}) == "fold"
