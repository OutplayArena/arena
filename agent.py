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