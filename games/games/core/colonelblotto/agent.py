import os
import random
import re
import ast
import litellm
from functools import lru_cache
from pathlib import Path
from transformers import pipeline

import yaml

from arena.game_components.game_agent import GameAgent
from outplayarena_sdk.reasoning import ReasoningModerator


PROMPTS_PATH = Path(__file__).with_name("prompts.yaml")
LLM_AGENT_PROMPT_KEY = "llm_agent"


@lru_cache(maxsize=1)
def load_prompt_templates():
    with PROMPTS_PATH.open(encoding="utf-8") as prompt_file:
        return yaml.safe_load(prompt_file) or {}


def render_prompt_template(template, variables):
    rendered = template
    for name, value in variables.items():
        rendered = rendered.replace(f"{{{{ {name} }}}}", str(value))
        rendered = rendered.replace(f"{{{{{name}}}}}", str(value))
    return rendered


def render_llm_agent_prompt(num_battlefields, total_resources, history):
    template = load_prompt_templates()[LLM_AGENT_PROMPT_KEY]
    return render_prompt_template(
        template,
        {
            "num_battlefields": num_battlefields,
            "total_resources": total_resources,
            "history": history,
        },
    )


# DUPLICATE: Also defined in agent-sdk/src/outplayarena_sdk/llm_agent.py as _balanced_allocation
# Keep implementations in sync.
def balanced_allocation(num_battlefields, total_resources):
    base = total_resources // num_battlefields
    allocation = [base] * num_battlefields
    for index in range(total_resources - sum(allocation)):
        allocation[index] += 1
    return allocation

class Agent(GameAgent):
    def __init__(self, name):
        self.name = name

    def act(self, history):
        allocation = []
        return allocation

class UniformAgent(Agent):
    def __init__(self, num_battlefields=5, total_resources=100):
        super().__init__("UniformAgent")
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources

    def act(self, history):
        return balanced_allocation(self.num_battlefields, self.total_resources)

class RandomAgent(Agent):
    def __init__(self, num_battlefields=5, total_resources=100):
        super().__init__("RandomAgent")
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources

    def act(self, history):
        cuts = sorted(random.sample(range(self.total_resources+1), self.num_battlefields-1))
        values = [cuts[0]]

        for i in range(1, len(cuts)):
            values.append(cuts[i] - cuts[i-1])

        values.append(self.total_resources - cuts[-1])
        return values

# ** GREEDY AGENT **
#
# Copies or slightly beats opponent's last move
class GreedyAgent(Agent):
    def __init__(self, num_battlefields=5, total_resources=100):
        super().__init__("GreedyAgent")
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources

    def act(self, history):
        if len(history) == 0:
            return balanced_allocation(self.num_battlefields, self.total_resources)

        last_round = history[-1]
        opponent_action = last_round["opponent_action"]

        allocation = [x+1 for x in opponent_action]
        total = sum(allocation)

        while total > self.total_resources:
            max_index = allocation.index(max(allocation))
            allocation[max_index] -= 1
            total -= 1

        while total < self.total_resources:
            min_index = allocation.index(min(allocation))
            allocation[min_index] += 1
            total += 1

        return allocation

class LLMAgent(Agent):
    def __init__(self,
                 num_battlefields=5,
                 total_resources=100,
                 model_name="Qwen/Qwen3.5-0.8B",
                 temperature=0.7,
                 reasoning=None):
        super().__init__("LLMAgent")
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources
        self.temperature = temperature
        self.reasoning = reasoning or ReasoningModerator(model_name)

        self.generator = pipeline(
            "text-generation",
            model=model_name,
            device_map="auto"
        )

    def build_prompt(self, history):
        base_prompt = render_llm_agent_prompt(
            self.num_battlefields,
            self.total_resources,
            history,
        )
        reasoning = getattr(self, "reasoning", None)
        if reasoning is None:
            return base_prompt
        return reasoning.build_system_prompt(base_prompt)

    # DUPLICATE: Also defined in agent-sdk/src/outplayarena_sdk/llm_agent.py as a standalone function
    # Keep implementations in sync. This version has the bool guard that the SDK version should also have.
    def parse_allocation(self, text):
        match = re.search(r"\[[^\]]+\]", text)

        if match is None:
            return balanced_allocation(self.num_battlefields, self.total_resources)

        try:
            allocation = ast.literal_eval(match.group())
        except (SyntaxError, ValueError):
            return balanced_allocation(self.num_battlefields, self.total_resources)

        if not isinstance(allocation, list):
            return balanced_allocation(self.num_battlefields, self.total_resources)

        if len(allocation) != self.num_battlefields:
            return balanced_allocation(self.num_battlefields, self.total_resources)

        if not all(isinstance(x, int) and not isinstance(x, bool) for x in allocation):
            return balanced_allocation(self.num_battlefields, self.total_resources)

        if not all(x >= 0 for x in allocation):
            return balanced_allocation(self.num_battlefields, self.total_resources)

        if sum(allocation) != self.total_resources:
            return balanced_allocation(self.num_battlefields, self.total_resources)

        return allocation

    def act(self, history):
        prompt = self.build_prompt(history)
        limits = self.reasoning.get_limits()

        output = self.generator(
            prompt,
            max_new_tokens=limits["max_tokens"],
            do_sample=True,
            temperature=self.temperature
        )[0]["generated_text"]

        response = output[len(prompt):]
        return self.parse_allocation(response)


class LiteLLMAgent(Agent):
    def __init__(self,
                 num_battlefields=5,
                 total_resources=100,
                 model_name=None,
                 api_base=None,
                 api_key=None,
                 temperature=0.7,
                 reasoning=None):
        super().__init__("LiteLLMAgent")
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources
        self.model_name = model_name or os.environ.get("LLM_MODEL", "opencode/go")
        self.api_base = api_base or os.environ.get("LLM_API_BASE", "http://127.0.0.1:11434/v1")
        raw_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENCODE_GO_API_KEY") or ""
        self.api_key = raw_key.strip()
        self.temperature = temperature
        self.reasoning = reasoning or ReasoningModerator(self.model_name)

    def build_prompt(self, history):
        base_prompt = render_llm_agent_prompt(
            self.num_battlefields,
            self.total_resources,
            history,
        )
        reasoning = getattr(self, "reasoning", None)
        if reasoning is None:
            return base_prompt
        return reasoning.build_system_prompt(base_prompt)

    def _fallback_allocation(self):
        return balanced_allocation(self.num_battlefields, self.total_resources)

    # DUPLICATE: Also defined in agent-sdk/src/outplayarena_sdk/llm_agent.py as a standalone function
    # Keep implementations in sync. Note: This version is missing the bool guard that the LLMAgent version has.
    def parse_allocation(self, text):
        match = re.search(r"\[[^\]]+\]", text)
        if match is None:
            return self._fallback_allocation()

        try:
            allocation = ast.literal_eval(match.group())
        except (SyntaxError, ValueError):
            return self._fallback_allocation()

        if (
            isinstance(allocation, list)
            and len(allocation) == self.num_battlefields
            and all(isinstance(x, int) for x in allocation)
            and all(x >= 0 for x in allocation)
            and sum(allocation) == self.total_resources
        ):
            return allocation

        return self._fallback_allocation()

    def act(self, history):
        prompt = self.build_prompt(history)
        limits = self.reasoning.get_limits()
        kwargs = dict(
            model=f"openai/{self.model_name}",
            messages=[{"role": "user", "content": prompt}],
            api_base=self.api_base,
            max_tokens=limits["max_tokens"],
            temperature=self.temperature,
            **self.reasoning.get_api_params(),
        )
        if self.api_key:
            kwargs["api_key"] = self.api_key
        response = litellm.completion(**kwargs)
        message = response.choices[0].message
        response_data = {
            "choices": [
                {
                    "message": {
                        "content": message.content,
                        "reasoning_content": getattr(message, "reasoning_content", ""),
                    }
                }
            ]
        }
        content, reasoning = self.reasoning.extract_response_text(response_data)
        return self.parse_allocation(content or reasoning)
