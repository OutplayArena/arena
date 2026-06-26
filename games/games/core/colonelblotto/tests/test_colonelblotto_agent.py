

from games.core.colonelblotto.agent import (
    GreedyAgent,
    LiteLLMAgent,
    LLMAgent,
    RandomAgent,
    UniformAgent,
    balanced_allocation,
    load_prompt_templates,
    render_llm_agent_prompt,
    render_prompt_template,
)


def make_observation(
    values=None,
    battalions=10,
    opponent_values=None,
    battlefield_values=None,
    num_battlefields=None,
    total_resources=None,
    history=None,
):
    return {
        "values": values or [3, 4, 5, 6, 7],
        "battalions": battalions,
        "opponent_values": opponent_values or [4, 5, 6, 7, 8],
        "battlefield_values": battlefield_values or [1.0] * (num_battlefields or 5),
        "num_battlefields": num_battlefields or 5,
        "total_resources": total_resources or 25,
        "history": history or [],
    }


class TestBalancedAllocation:
    def test_balanced_even_division(self):
        result = balanced_allocation(5, 100)
        assert sum(result) == 100
        assert len(result) == 5
        assert all(isinstance(x, int) for x in result)

    def test_balanced_with_remainder(self):
        result = balanced_allocation(3, 10)
        assert sum(result) == 10
        assert len(result) == 3
        assert max(result) - min(result) <= 1

    def test_balanced_zero_resources(self):
        result = balanced_allocation(5, 0)
        assert sum(result) == 0
        assert len(result) == 5
        assert all(x == 0 for x in result)


class TestUniformAgent:
    def test_uniform_default_params(self):
        agent = UniformAgent()
        result = agent.act([])
        assert sum(result) == 100
        assert len(result) == 5
        assert all(isinstance(x, int) for x in result)

    def test_uniform_custom_params(self):
        agent = UniformAgent(num_battlefields=3, total_resources=30)
        result = agent.act([])
        assert sum(result) == 30
        assert len(result) == 3

    def test_uniform_with_history_ignores_it(self):
        agent = UniformAgent()
        result = agent.act([{"opponent_action": [10, 0, 0, 0, 0]}])
        assert sum(result) == 100


class TestRandomAgent:
    def test_random_default(self):
        agent = RandomAgent()
        result = agent.act([])
        assert sum(result) == 100
        assert len(result) == 5
        assert all(x >= 0 for x in result)

    def test_random_custom(self):
        agent = RandomAgent(num_battlefields=3, total_resources=15)
        result = agent.act([])
        assert sum(result) == 15
        assert len(result) == 3

    def test_random_distribution_valid(self):
        agent = RandomAgent(num_battlefields=4, total_resources=20)
        for _ in range(20):
            result = agent.act([])
            assert sum(result) == 20
            assert all(x >= 0 for x in result)


class TestGreedyAgent:
    def test_greedy_no_history_uses_balanced(self):
        agent = GreedyAgent()
        result = agent.act([])
        assert sum(result) == 100
        assert len(result) == 5

    def test_greedy_copies_opponent_plus_one(self):
        agent = GreedyAgent(num_battlefields=3, total_resources=12)
        result = agent.act([{"opponent_action": [3, 3, 3]}])
        assert sum(result) == 12
        assert all(x == 4 for x in result)

    def test_greedy_clamps_too_large_allocation(self):
        agent = GreedyAgent(num_battlefields=3, total_resources=10)
        result = agent.act([{"opponent_action": [10, 10, 10]}])
        assert sum(result) == 10
        assert all(x >= 0 for x in result)

    def test_greedy_clamps_too_small_allocation(self):
        agent = GreedyAgent(num_battlefields=3, total_resources=20)
        result = agent.act([{"opponent_action": [1, 1, 1]}])
        assert sum(result) == 20


class TestLLMAgentParseAllocation:
    def _make_agent(self):
        return LLMAgent.__new__(LLMAgent)

    def test_parse_no_match_returns_balanced(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("no brackets here")
        assert sum(result) == 9
        assert len(result) == 3

    def test_parse_valid_list(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("here is [3, 3, 3] allocation")
        assert result == [3, 3, 3]

    def test_parse_invalid_syntax_returns_balanced(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("here is [bad, syntax] allocation")
        assert sum(result) == 9

    def test_parse_wrong_type_returns_balanced(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("here is 42 not a list")
        assert sum(result) == 9

    def test_parse_wrong_length_returns_balanced(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("here is [1, 2] too short")
        assert sum(result) == 9

    def test_parse_non_int_values_returns_balanced(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("here is [1.5, 2.5, 5.0] floats")
        assert sum(result) == 9

    def test_parse_bool_treated_as_int_returns_balanced(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("here is [True, 4, 4] bools")
        assert sum(result) == 9

    def test_parse_negative_values_returns_balanced(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("here is [-1, 5, 5] negative")
        assert sum(result) == 9

    def test_parse_wrong_sum_returns_balanced(self):
        agent = self._make_agent()
        agent.num_battlefields = 3
        agent.total_resources = 9
        result = agent.parse_allocation("here is [1, 2, 3] sum is 6")
        assert sum(result) == 9


class TestLiteLLMAgentParseAllocation:
    def _make_agent(self):
        agent = LiteLLMAgent.__new__(LiteLLMAgent)
        agent.num_battlefields = 3
        agent.total_resources = 9
        return agent

    def test_parse_no_match_returns_balanced(self):
        agent = self._make_agent()
        result = agent.parse_allocation("nothing here")
        assert sum(result) == 9
        assert len(result) == 3

    def test_parse_valid_list(self):
        agent = self._make_agent()
        result = agent.parse_allocation("here is [3, 3, 3]")
        assert result == [3, 3, 3]

    def test_parse_invalid_syntax_returns_balanced(self):
        agent = self._make_agent()
        result = agent.parse_allocation("here is [bad, syntax]")
        assert sum(result) == 9

    def test_parse_wrong_sum_returns_balanced(self):
        agent = self._make_agent()
        result = agent.parse_allocation("[1, 2, 2] sum 5 != 9")
        assert sum(result) == 9

    def test_parse_negative_values_returns_balanced(self):
        agent = self._make_agent()
        result = agent.parse_allocation("[-1, 5, 5] sum 9 but negative")
        assert sum(result) == 9


class TestPromptRendering:
    def test_render_prompt_template_jinja_syntax(self):
        out = render_prompt_template("{{ name }}", {"name": "alice"})
        assert out == "alice"

    def test_render_prompt_template_preserves_unknown(self):
        out = render_prompt_template("{name}", {"name": "bob"})
        assert out == "{name}"

    def test_render_llm_agent_prompt(self):
        result = render_llm_agent_prompt(5, 100, [])
        assert "5" in result
        assert "100" in result

    def test_load_prompt_templates_caches(self):
        t1 = load_prompt_templates()
        t2 = load_prompt_templates()
        assert t1 is t2
        assert "llm_agent" in t1
