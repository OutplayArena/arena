from .agent import Agent

# ** GAME DEFINITION **
#
# Parameters: 2 agents, 5 battlefields, 100 total troops, 10 rounds
#
# Agent submits a list like: [20,10,30,25,15]
# Each number is how many troops it puts on each battlefield
#
# Scoring: higher allocation wins that battlefield, 
#          tie gives both 0.5 pts, 
#          winner of round is whoever wins more battlefield points!
class BlottoGame:
    def __init__(self, num_battlefields=5, total_resources=100):
        if num_battlefields < 1:
            raise ValueError("num_battlefields must be at least 1")
        if total_resources < num_battlefields:
            raise ValueError("total_resources must be at least num_battlefields")

        self.num_battlefields = num_battlefields
        self.total_resources = total_resources
        
    def validate_action(self, action):
        if not isinstance(action, list):
            return False

        if len(action) != self.num_battlefields:
            return False
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in action):
            return False
        if not all(x >= 0 for x in action):
            return False
        if sum(action) != self.total_resources:
            return False

        return True
        
    def play_round(self, action_a, action_b):
        if not self.validate_action(action_a):
            raise ValueError(f"Invalid action for Agent A: {action_a}")
        if not self.validate_action(action_b):
            raise ValueError(f"Invalid action for Agent B: {action_b}")
        
        score_a = 0
        score_b = 0
        
        for a,b in zip(action_a, action_b):
            if a > b:
                score_a += 1
            elif b > a:
                score_b += 1
            else:
                score_a += .5
                score_b += .5
                
        if score_a > score_b: winner = "A"
        elif score_b > score_a: winner = "B"
        else: winner = "Tie"
        
        return {
            "action_a": action_a,
            "action_b": action_b,
            "score_a": score_a,
            "score_b": score_b,
            "winner": winner
        }
        
    def play_match(self, agent_a: Agent, agent_b: Agent, num_rounds=10):
        history_a = []
        history_b = []
        full_history = []
        
        total_score_a = 0
        total_score_b = 0
        
        for round_idx in range(num_rounds):
            action_a = agent_a.act(history_a)
            action_b = agent_b.act(history_b)
            
            result = self.play_round(action_a, action_b)
            
            total_score_a += result["score_a"]
            total_score_b += result["score_b"]
            
            full_history.append({
                "round": round_idx + 1,
                "agent_a": agent_a.name,
                "agent_b": agent_b.name,
                **result
            })
            
            history_a.append({
                "own_action": action_a,
                "opponent_action": action_b,
                "own_score": result["score_a"],
                "opponent_score": result["score_b"],
                "winner": result["winner"]
            })
            
            history_b.append({
                "own_action": action_b,
                "opponent_action": action_a,
                "own_score": result["score_b"],
                "opponent_score": result["score_a"],
                "winner": result["winner"]
            })
        
        if total_score_a > total_score_b: match_winner = agent_a.name
        elif total_score_b > total_score_a: match_winner = agent_b.name
        else: match_winner = "Tie"
            
        return {
            "agent_a": agent_a.name,
            "agent_b": agent_b.name,
            "total_score_a": total_score_a,
            "total_score_b": total_score_b,
            "match_winner": match_winner,
            "history": full_history
        }
    
