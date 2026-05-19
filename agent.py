import random 
import re
import ast
from transformers import pipeline

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