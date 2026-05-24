import argparse

from blotto.engine import BlottoGame
from blotto.agent import Agent, UniformAgent, RandomAgent, GreedyAgent, LLMAgent, LiteLLMAgent

AGENTS = {
    "uniform": UniformAgent,
    "random": RandomAgent,
    "greedy": GreedyAgent,
    "llm-local": LLMAgent,
    "llm-api": LiteLLMAgent
}

def run_experiment(agent_a:Agent, agent_b:Agent, num_rounds=10):
    blotto_game = BlottoGame(num_battlefields=5, total_resources=100)
    
    result = blotto_game.play_match(agent_a, agent_b, num_rounds)
    print(f'Winner of match is {result["match_winner"]}')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent_a", type=str, default="uniform")
    parser.add_argument("--agent_b", type=str, default="random")
    parser.add_argument("--rounds", type=int, default=10)
    
    args = parser.parse_args()
    agent_a = AGENTS[args.agent_a]()
    agent_b = AGENTS[args.agent_b]()
    rounds = args.rounds
    
    run_experiment(agent_a, agent_b, rounds)
