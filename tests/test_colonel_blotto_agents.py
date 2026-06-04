from games.core.colonelblotto.agent import LLMAgent, LiteLLMAgent, load_prompt_templates


def assert_agent_uses_yaml_prompt(agent):
    prompt = agent.build_prompt([{"round": 1, "opponent_action": [3, 3, 4]}])

    assert "There are 3 battlefields." in prompt
    assert "You have exactly 10 troops." in prompt
    assert "Return only a Python list of 3 nonnegative integers." in prompt
    assert "[3, 3, 4]" in prompt


def test_litellm_agent_prompt_is_loaded_from_yaml():
    templates = load_prompt_templates()
    assert "llm_agent" in templates

    agent = LiteLLMAgent(num_battlefields=3, total_resources=10)
    assert_agent_uses_yaml_prompt(agent)


def test_llm_agent_prompt_is_loaded_from_yaml():
    agent = LLMAgent.__new__(LLMAgent)
    agent.num_battlefields = 3
    agent.total_resources = 10

    assert_agent_uses_yaml_prompt(agent)
