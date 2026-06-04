import argparse

from games.core.colonelblotto.agent import Agent, GreedyAgent, LiteLLMAgent, LLMAgent, RandomAgent, UniformAgent
from games.core.colonelblotto.engine import ColonelBlottoGame


AGENTS = {
    "uniform": UniformAgent,
    "random": RandomAgent,
    "greedy": GreedyAgent,
    "llm-local": LLMAgent,
    "llm-api": LiteLLMAgent,
}


def run_experiment(agent_a: Agent, agent_b: Agent, num_rounds=10):
    colonel_blotto_game = ColonelBlottoGame(num_battlefields=5, total_resources=100)
    result = colonel_blotto_game.play_match(agent_a, agent_b, num_rounds)
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
