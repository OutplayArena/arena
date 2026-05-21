import os
import random 
import re
import ast
from transformers import pipeline
import litellm

class Agent:
    def __init__(self, name):
        self.name = name
        
    def act(self, history):
        allocation = []
        return allocation
    
class UniformAgent(Agent):
    def __init__(self):
        super().__init__("UniformAgent")
        
    def act(self, history):
        return [20,20,20,20,20]

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
# Copies or slightly beats oppoenent's last move
class GreedyAgent(Agent):
    def __init__(self, num_battlefields=5, total_resources=100):
        super().__init__("GreedyAgent")
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources
    
    def act(self, history):
        if len(history) == 0: return [20,20,20,20,20]
        
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
                 model_name="Qwen/Qwen3.5-0.8B"):
        super().__init__("LLMAgent")
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources
        
        self.generator = pipeline(
            "text-generation",
            model=model_name,
            device_map="auto"
        )

    def build_prompt(self, history):
        return f"""
                You are playing Colonel Blotto.

                Rules:
                - There are 5 battlefields.
                - You have exactly 100 troops.
                - Return only a Python list of 5 nonnegative integers.
                - The list must sum to 100.
                - Do not explain.

                History:
                {history}

                Your allocation:
                """
    
    def parse_allocation(self, text):
        match = re.search(r"\[[^\]]+\]", text)

        if match is None:
            return [20, 20, 20, 20, 20]

        try:
            allocation = ast.literal_eval(match.group())
        except:
            return [20, 20, 20, 20, 20]

        if not isinstance(allocation, list):
            return [20, 20, 20, 20, 20]

        if len(allocation) != 5:
            return [20, 20, 20, 20, 20]

        if not all(isinstance(x, int) for x in allocation):
            return [20, 20, 20, 20, 20]

        if not all(x >= 0 for x in allocation):
            return [20, 20, 20, 20, 20]

        if sum(allocation) != 100:
            return [20, 20, 20, 20, 20]

        return allocation

    def act(self, history):
        prompt = self.build_prompt(history)
        
        output = self.generator(
            prompt,
            max_new_tokens=50,
            do_sample=True,
            temperature=0.7
        )[0]["generated_text"]
        
        response = output[len(prompt):]
        return self.parse_allocation(response)


class LiteLLMAgent(Agent):
    def __init__(self,
                 num_battlefields=5,
                 total_resources=100,
                 model_name=None,
                 api_base=None,
                 api_key=None):
        super().__init__("LiteLLMAgent")
        self.num_battlefields = num_battlefields
        self.total_resources = total_resources
        self.model_name = model_name or os.environ.get("LLM_MODEL", "opencode/go")
        self.api_base = api_base or os.environ.get("LLM_API_BASE", "http://127.0.0.1:11434/v1")
        raw_key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENCODE_GO_API_KEY") or ""
        self.api_key = raw_key.strip()

    def build_prompt(self, history):
        return f"""
You are playing Colonel Blotto.

Rules:
- There are {self.num_battlefields} battlefields.
- You have exactly {self.total_resources} troops.
- Return only a Python list of {self.num_battlefields} nonnegative integers.
- The list must sum to {self.total_resources}.
- Do not explain.

History:
{history}

Your allocation:
"""

    def _fallback_allocation(self):
        base = self.total_resources // self.num_battlefields
        allocation = [base] * self.num_battlefields
        for index in range(self.total_resources - sum(allocation)):
            allocation[index] += 1
        return allocation

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
        kwargs = dict(
            model=f"openai/{self.model_name}",
            messages=[{"role": "user", "content": prompt}],
            api_base=self.api_base,
            max_tokens=50,
            temperature=0.7,
        )
        if self.api_key:
            kwargs["api_key"] = self.api_key
        response = litellm.completion(**kwargs)
        text = response.choices[0].message.content
        return self.parse_allocation(text)