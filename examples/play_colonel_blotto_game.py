import os

from nash_arena.client import ArenaClient
from games.core.colonelblotto.config import ColonelBlottoExperimentConfig

BASE_URL = os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ["NASH_ARENA_API_KEY"]

def main():
    arena = ArenaClient(BASE_URL)
    config = ColonelBlottoExperimentConfig.classic(
        num_battlefields=3,
        total_resources=10,
        rounds=1,
        seed=42,
    )

    created = arena.create_experiment(config, api_key=API_KEY)
    agent_a = ArenaClient.for_player(BASE_URL, created, "A")
    agent_b = ArenaClient.for_player(BASE_URL, created, "B")

    print(f"created session={created['session_id']}")
    print(agent_a.get_state())

    agent_a.submit_action([10, 0, 0])
    agent_b.submit_action([0, 5, 5])

    results = agent_a.get_results()
    print(f"winner={results['winner']}")
    print(results["metrics"])


if __name__ == "__main__":
    main()
