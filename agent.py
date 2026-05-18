import random 

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
