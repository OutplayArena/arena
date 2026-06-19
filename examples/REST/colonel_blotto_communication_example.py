import os

from nash_arena_sdk import ArenaClient
from games.core.colonelblotto.config import ColonelBlottoExperimentConfig

BASE_URL = os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")


def main():
    api_key = os.environ.get("NASH_ARENA_API_KEY")
    if not api_key:
        raise SystemExit("NASH_ARENA_API_KEY environment variable is required")
    arena = ArenaClient(BASE_URL)
    config = ColonelBlottoExperimentConfig.classic(
        num_battlefields=3,
        total_resources=10,
        rounds=1,
        seed=42,
    )

    created = arena.create_experiment(config, api_key=api_key)
    agent_a = ArenaClient.for_player(BASE_URL, created, "A")
    agent_b = ArenaClient.for_player(BASE_URL, created, "B")

    print(f"created session={created['session_id']}")

    # Player A sends a message to Player B
    result = agent_a.send_message("Let's split the battlefields evenly")
    print(f"A sent message: {result}")

    # Player B checks their messages
    messages = agent_b.get_messages()
    print(f"B sees messages: {messages}")

    # Player B sends a reply
    agent_b.send_message("I'll take the first 2, you take the last one")
    agent_b.send_message("Or we can fight it out")

    # Player B submits their action
    state = agent_b.get_state()
    print(f"Game state includes messages: {state.get('messages', [])}")
    print(f"Communication config: {state.get('communication_config', {})}")

    # Players can see each other's communication config
    print(f"Game communication config: {state.get('communication_config', {})}")

    agent_a.submit_action([5, 3, 2])
    agent_b.submit_action([4, 4, 2])

    results = agent_a.get_results()
    print(f"winner={results['winner']}")


if __name__ == "__main__":
    main()
