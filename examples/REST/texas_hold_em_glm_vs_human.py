#!/usr/bin/env python3
"""Texas Hold'em bot: GLM-5.1 plays Player B against a human (Player A)."""

import json
import os
import time

import httpx
from openai import OpenAI

BASE_URL = "http://127.0.0.1:8000/api"
SESSION_ID = "f5fe74c6-0b80-4219-af33-c86d29ba00e2"
PLAYER = "B"
SESSION_KEY = "nks_ZjVmZTc0YzYtMGI4MC00MjE5LWFmMzMtYzg2ZDI5YmEwMGUyOkI6YjIwMThiYzk5Yjg2YjlkODlkYzFkZjNjOGU5OGJhNGZmOTBiNTNhMDllZmM0M2JiNzY1NjMwYjQ2OTczZjZiZA"

client = OpenAI(
    base_url="https://opencode.ai/zen/v1",
    api_key=os.environ["OPENCODE_GO_API_KEY"].strip(),
)

http = httpx.Client(timeout=30)


def get_state() -> dict:
    resp = http.get(
        f"{BASE_URL}/session/{SESSION_ID}/interactive/state",
        params={"player": PLAYER},
        headers={"Authorization": f"Bearer {SESSION_KEY}"},
    )
    resp.raise_for_status()
    return resp.json()


def submit_action(action: str) -> dict:
    resp = http.post(
        f"{BASE_URL}/session/{SESSION_ID}/interactive/action",
        params={"player": PLAYER},
        headers={"Authorization": f"Bearer {SESSION_KEY}"},
        json={"action": action},
    )
    resp.raise_for_status()
    return resp.json()


def ask_glm(system_prompt: str, user_prompt: str) -> str:
    resp = client.chat.completions.create(
        model="glm-5.1",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        extra_body={"thinking": {"type": "disabled"}},
    )
    return resp.choices[0].message.content.strip()


def parse_action(text: str) -> str:
    text_lower = text.lower()
    for action in ["fold", "check", "call", "raise"]:
        if action in text_lower:
            return action
    return "fold"


def build_prompts(state: dict) -> tuple[str, str]:
    player_id = PLAYER
    opponent_id = "A"
    hand_number = state.get("hand_number", 1)
    street = state.get("street", "preflop")
    hole_cards = state.get("hole_cards", {})
    community_cards = state.get("community_cards", [])
    chips = state.get("chips", {})
    pot = state.get("pot", 0)
    street_actions = state.get("street_actions", [])

    to_call = 0
    if chips.get(player_id, 0) > chips.get(opponent_id, 0):
        to_call = 0
    else:
        to_call = chips.get(opponent_id, 0) - chips.get(player_id, 0)

    system = (
        "You are playing Texas Hold'em.\n\n"
        "Rules:\n"
        "- Each hand you and your opponent take turns betting over 4 streets\n"
        "- Actions: fold (give up), check (pass if no bet), call (match bet), raise (increase bet)\n"
        "- At showdown the best five-card poker hand wins the pot\n"
        "- You can see both players' hole cards (face-up variant)\n"
        "- Each player starts with 100 chips, ante 1, bet size 2\n\n"
        "Respond with exactly one word (fold, check, call, or raise). Do not explain."
    )

    history_text = ""
    if street_actions:
        for sa in street_actions:
            history_text += f"  {sa.get('player')}: {sa.get('action')}\n"

    user = (
        f"You are player {player_id}.\n"
        f"Hand {hand_number}, {street}.\n"
        f"Your hole cards: {hole_cards.get(player_id, [])}\n"
        f"Opponent's cards: {hole_cards.get(opponent_id, [])}\n"
        f"Community cards: {community_cards}\n"
        f"Your chips: {chips.get(player_id, 0)}\n"
        f"Pot: {pot}\n"
        f"To call: {to_call}\n\n"
        f"Actions this street:\n{history_text}\n"
        "It is your turn. Respond with exactly one word: fold, check, call, or raise."
    )

    return system, user


def main():
    print(f"=== Texas Hold'em Bot (Player {PLAYER}) ===")
    print(f"Session: {SESSION_ID}")

    while True:
        state = get_state()
        phase = state.get("phase")
        hand_num = state.get("hand_number")
        street = state.get("street")

        print(f"\nHand {hand_num}/{state['round_total']} | Street: {street} | Phase: {phase}")
        print(f"Your cards: {state.get('hole_cards', {}).get(PLAYER, [])}")
        print(f"Opponent cards: {state.get('hole_cards', {}).get('A', [])}")
        print(f"Community: {state.get('community_cards', [])}")
        print(f"Chips: A={state['chips'].get('A', 0)}, B={state['chips'].get('B', 0)}")
        print(f"Pot: {state.get('pot', 0)}")

        if phase == "complete":
            print("\n=== GAME OVER ===")
            print(f"Final scores: A={state['total_scores']['A']}, B={state['total_scores']['B']}")
            if state["history"]:
                print("\nHand history:")
                for h in state["history"]:
                    result = h.get("result", {})
                    print(f"  Hand {h['hand']}: {result.get('outcome')} - winner: {result.get('winner')}")
            break

        if PLAYER not in state.get("awaiting", []):
            print(f"Waiting for Player A...")
            time.sleep(2)
            continue

        system, user = build_prompts(state)
        print(f"\nAsking GLM-5.1...")
        response = ask_glm(system, user)
        print(f"GLM-5.1 response: {response}")

        action = parse_action(response)
        print(f"Parsed action: {action}")

        try:
            result = submit_action(action)
            print(f"Submit result: phase={result.get('phase')}, street={result.get('street')}")
        except Exception as e:
            print(f"Error submitting action: {e}")
            action = "fold"
            print(f"Fallback: folding")
            result = submit_action(action)

        time.sleep(1)


if __name__ == "__main__":
    main()
