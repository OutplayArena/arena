from api import BlottoGame
from agent import Agent, UniformAgent, RandomAgent

def run_experiment(agent_a:Agent, agent_b:Agent, num_rounds=10):
    blotto_game = BlottoGame(num_battlefields=5, total_resources=100)
    
    result = blotto_game.play_match(agent_a, agent_b, num_rounds)
    print(f"Winner of match is {result["match_winner"]}")

if __name__ == "__main__":
    run_experiment(RandomAgent(), RandomAgent(), 99)