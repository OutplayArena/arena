import os

from nash_arena.client import ArenaClient
from games.core.blotto.config import BlottoExperimentConfig

BASE_URL = os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000")
INTERNAL_API_TOKEN = os.environ.get("NASH_ARENA_INTERNAL_API_TOKEN")


def main():
    if not INTERNAL_API_TOKEN:
        raise SystemExit("NASH_ARENA_INTERNAL_API_TOKEN is required")

    arena = ArenaClient(BASE_URL, internal_api_token=INTERNAL_API_TOKEN)
    config = BlottoExperimentConfig.classic(
        num_battlefields=3,
        total_resources=10,
        rounds=1,
        seed=42,
    )

    created = arena.create_experiment(config)
    agent_a = ArenaClient.for_player(
        BASE_URL,
        created,
        "A",
        internal_api_token=INTERNAL_API_TOKEN,
    )
    agent_b = ArenaClient.for_player(
        BASE_URL,
        created,
        "B",
        internal_api_token=INTERNAL_API_TOKEN,
    )

    print(f"created session={created['session_id']}")
    print(agent_a.get_state())

    agent_a.submit_action([10, 0, 0])
    agent_b.submit_action([0, 5, 5])

    results = agent_a.get_results()
    print(f"winner={results['winner']}")
    print(results["metrics"])


if __name__ == "__main__":
    main()
