#!/usr/bin/env python3
"""
Public Goods Game bot using GLM-5.1
Plays as players B, C, D in a 4-player game
"""

import os
import time
import httpx
from openai import OpenAI

# Session configuration
SESSION_ID = "ea6abefb-9584-46be-9699-b263e7d05c23"
PLAYER_KEYS = {
    "B": "nks_ZWE2YWJlZmItOTU4NC00NmJlLTk2OTktYjI2M2U3ZDA1YzIzOkI6OGQ5YjY2YmU0NTg5MTEzMDAwZjNlZmJiMDczMGM3MzI1N2ViZmNmNTkxZGUzNjVmYjYzYTgwZmJmNDIzMTFkYw",
    "C": "nks_ZWE2YWJlZmItOTU4NC00NmJlLTk2OTktYjI2M2U3ZDA1YzIzOkM6NDM0YWVhZDgyOGI0ZjJmY2VhNDUxOGZlODY0MGU4ZmJiZWU3MTk4NzkwYjJlZTQwNGU0OGUxMmI5NzY5MzBlOQ",
    "D": "nks_ZWE2YWJlZmItOTU4NC00NmJlLTk2OTktYjI2M2U3ZDA1YzIzOkQ6MWVjYzE0MzJjZTI3NDFlY2FmNDQ1ZjBiYTM0NzBmZTk5ZjE5ZmM1ZTRkOThlZGM1ZjZjNmE2YzE1MDYxY2M5NA",
}

BACKEND_URL = "http://127.0.0.1:8000/api"
OPENCODE_GO_API_KEY = os.environ.get("OPENCODE_GO_API_KEY", "").strip()
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
MODEL = "glm-5.1"

client = OpenAI(api_key=OPENCODE_GO_API_KEY, base_url=OPENCODE_GO_API_BASE)


def get_state(player: str, key: str) -> dict:
    """Get game state for a player"""
    response = httpx.get(
        f"{BACKEND_URL}/session/{SESSION_ID}/interactive/state",
        params={"player": player},
        headers={"Authorization": f"Bearer {key}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def submit_action(player: str, key: str, action: dict) -> dict:
    """Submit action for a player"""
    response = httpx.post(
        f"{BACKEND_URL}/session/{SESSION_ID}/interactive/action",
        params={"player": player},
        headers={"Authorization": f"Bearer {key}"},
        json={"action": action},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def get_observation(player: str, key: str) -> dict:
    """Get observation (prompts) for a player"""
    response = httpx.get(
        f"{BACKEND_URL}/session/{SESSION_ID}/observation",
        params={"player": player, "variant": "neutral"},
        headers={"Authorization": f"Bearer {key}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def parse_contribution(response_text: str, endowment: float) -> float:
    """Parse contribution amount from LLM response"""
    # Try to extract a number from the response
    import re
    numbers = re.findall(r'\d+(?:\.\d+)?', response_text)
    if numbers:
        contribution = float(numbers[-1])  # Take the last number
        # Clamp to valid range
        return max(0.0, min(endowment, contribution))
    return 0.0  # Default to 0 if no number found


def play_round(player: str, key: str):
    """Play one round for a player"""
    # Get observation (prompts)
    obs = get_observation(player, key)
    system_prompt = obs.get("system", "")
    turn_prompt = obs.get("turn", "")

    print(f"\n[Player {player}] Getting contribution decision...")
    print(f"  System: {system_prompt[:100]}...")
    print(f"  Turn: {turn_prompt[:150]}...")

    # Call LLM
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": turn_prompt},
        ],
        temperature=0.7,
        max_tokens=100,
    )

    llm_response = response.choices[0].message.content
    print(f"  LLM response: {llm_response}")

    # Get current state to know endowment
    state = get_state(player, key)
    endowment = state.get("endowment", 10.0)

    # Parse contribution
    contribution = parse_contribution(llm_response, endowment)
    print(f"  Parsed contribution: {contribution}")

    # Submit action
    action = {"contribution": contribution}
    result = submit_action(player, key, action)
    print(f"  Submitted: {action}")
    print(f"  Result: {result}")

    return result


def main():
    print("=" * 60)
    print("Public Goods Game Bot - Players B, C, D")
    print(f"Session: {SESSION_ID}")
    print("=" * 60)

    # Check initial state
    state = get_state("B", PLAYER_KEYS["B"])
    print("\nInitial state:")
    print(f"  Phase: {state.get('phase')}")
    print(f"  Round: {state.get('round')}/{state.get('round_total')}")
    print(f"  Endowment: {state.get('endowment')}")
    print(f"  Multiplier: {state.get('multiplier')}")
    print(f"  Total scores: {state.get('total_scores')}")

    # Play until game is complete
    while True:
        state = get_state("B", PLAYER_KEYS["B"])
        phase = state.get("phase")
        round_num = state.get("round")
        total_rounds = state.get("round_total")

        print(f"\n--- Round {round_num}/{total_rounds} - Phase: {phase} ---")

        if phase == "complete":
            print("\nGame complete!")
            print(f"Final scores: {state.get('total_scores')}")
            break

        # Play for each player
        for player, key in PLAYER_KEYS.items():
            player_state = get_state(player, key)
            if player_state.get("phase") == "awaiting_action":
                try:
                    play_round(player, key)
                except Exception as e:
                    print(f"Error playing as {player}: {e}")
                    import traceback
                    traceback.print_exc()

        # Small delay between rounds
        time.sleep(1)


if __name__ == "__main__":
    main()
