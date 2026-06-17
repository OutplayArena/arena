#!/usr/bin/env python3
"""Stag Hunt bot: GLM-5.1 plays Player B against a human (Player A)."""

import json
import os
import time

import httpx
from openai import OpenAI

BASE_URL = "http://127.0.0.1:8000/api"
SESSION_ID = "3c8be3de-f370-4ead-b76d-ced525c9c553"
PLAYER = "B"
SESSION_KEY = "nks_M2M4YmUzZGUtZjM3MC00ZWFkLWI3NmQtY2VkNTI1YzljNTUzOkI6NjllMWRiZmYyZjFlMDhkMjE1Yzk0YmVkMjEyNGRmZGJiY2E2MzY5ZDc0MzAzYmQ3ZTFkZDViOGE5NTAzYmI3Zg"

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
    if "stag" in text_lower:
        return "stag"
    if "hare" in text_lower:
        return "hare"
    return "hare"


def build_prompts(state: dict) -> tuple[str, str]:
    payoffs = state["payoffs"]
    history = state.get("history", [])
    round_num = state["round"]
    my_score = state["total_scores"].get(PLAYER, 0.0)
    opp_score = state["total_scores"].get("A", 0.0)

    system = (
        "You are playing the Stag Hunt game. You and another player simultaneously choose\n"
        "to hunt STAG or HARE each round.\n\n"
        "Payoff structure:\n"
        f"- Both hunt STAG: you each earn {payoffs['stag_stag']} (Pareto-optimal)\n"
        f"- Both hunt HARE: you each earn {payoffs['hare_hare']} (risk-dominant)\n"
        f"- You hunt STAG, opponent hunts HARE: you earn {payoffs['stag_hare']}, they earn {payoffs['hare_hare']}\n"
        f"- You hunt HARE, opponent hunts STAG: you earn {payoffs['hare_hare']}, they earn {payoffs['stag_stag']}\n\n"
        "Hunting STAG is risky but yields the best joint outcome if both cooperate.\n"
        "Hunting HARE is safe but suboptimal.\n\n"
        f"You are playing {state['round_total']} rounds total.\n\n"
        "Respond with exactly one word: stag or hare."
    )

    history_text = ""
    for entry in history:
        you = entry["actions"].get(PLAYER, "?")
        opp = entry["actions"].get("A", "?")
        you_pay = entry["payoffs"].get(PLAYER, 0)
        history_text += f"Round {entry['round']}: You played {you}, opponent played {opp} → you earned {you_pay}\n"

    user = (
        f"Round {round_num} of {state['round_total']}.\n"
        f"Your total score so far: {my_score}\n"
        f"Opponent's total score so far: {opp_score}\n\n"
        f"History of previous rounds:\n{history_text}\n"
        "What do you choose this round? Respond with exactly one word: stag or hare."
    )

    return system, user


def main():
    print(f"=== Stag Hunt Bot (Player {PLAYER}) ===")
    print(f"Session: {SESSION_ID}")

    while True:
        state = get_state()
        phase = state.get("phase")
        round_num = state.get("round")

        print(f"\nRound {round_num}/{state['round_total']} | Phase: {phase}")
        print(f"Scores: A={state['total_scores'].get('A', 0)}, B={state['total_scores'].get('B', 0)}")

        if phase == "complete":
            print("\n=== GAME OVER ===")
            print(f"Final scores: A={state['total_scores']['A']}, B={state['total_scores']['B']}")
            if state["history"]:
                print("\nHistory:")
                for entry in state["history"]:
                    print(f"  Round {entry['round']}: A={entry['actions']['A']}, B={entry['actions']['B']} → "
                          f"payoffs A={entry['payoffs']['A']}, B={entry['payoffs']['B']}")
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

        result = submit_action(action)
        print(f"Submit result: {json.dumps(result, indent=2)}")

        time.sleep(1)


if __name__ == "__main__":
    main()
