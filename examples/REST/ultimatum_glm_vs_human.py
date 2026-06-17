#!/usr/bin/env python3
"""Ultimatum bot: GLM-5.1 plays Player B against a human (Player A)."""

import json
import os
import time

import httpx
from openai import OpenAI

BASE_URL = "http://127.0.0.1:8000/api"
SESSION_ID = "2c872b83-b0c2-4824-9595-c0dc0a1a58ec"
PLAYER = "B"
SESSION_KEY = "nks_MmM4NzJiODMtYjBjMi00ODI0LTk1OTUtYzBkYzBhMWE1OGVjOkI6N2I3NmQ5NDYzMjc1ZTA4YWZmNTc5NTI2OGNmNTBkMmMyZjIxZDcxMDBlZmVkZDhiNTAxYjg3ZjMzYTM4NzcyYQ"

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


def submit_action(action: dict) -> dict:
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


def parse_offer(text: str, total: float) -> float:
    import re
    numbers = re.findall(r'\d+(?:\.\d+)?', text)
    if numbers:
        offer = float(numbers[0])
        return max(0.0, min(total, offer))
    return total / 2


def parse_response(text: str) -> str:
    text_lower = text.lower()
    if "reject" in text_lower:
        return "reject"
    return "accept"


def build_proposer_prompts(state: dict) -> tuple[str, str]:
    total = state["total"]
    history = state.get("history", [])
    round_num = state["round"]
    my_score = state["total_scores"].get(PLAYER, 0.0)
    opp_score = state["total_scores"].get("A", 0.0)

    system = (
        f"You are playing the Ultimatum Game. There are {state['round_total']} rounds.\n"
        f"Each round, one player proposes how to split {total} points; the other accepts or rejects.\n"
        f"If accepted: proposer keeps (total - offer), responder receives offer.\n"
        f"If rejected: both players receive 0 for that round.\n"
        f"Roles alternate each round.\n\n"
        "Respond with a number representing your offer to the responder."
    )

    history_text = ""
    for entry in history:
        proposer_label = "You" if entry["proposer"] == PLAYER else "Opponent"
        history_text += f"Round {entry['round']}: {proposer_label} proposed {entry['offer']} ({entry['offer_fraction']*100:.0f}%) → {entry['response']}\n"

    user = (
        f"Round {round_num} of {state['round_total']}. You are the PROPOSER.\n"
        f"Your total score: {my_score} | Opponent's score: {opp_score}\n\n"
        f"History:\n{history_text}\n"
        f"How many points do you offer the responder? (0 to {total})\n"
        "Respond with a number."
    )

    return system, user


def build_responder_prompts(state: dict) -> tuple[str, str]:
    total = state["total"]
    offer = state.get("pending_offer", 0)
    offer_fraction = offer / total if total > 0 else 0
    history = state.get("history", [])
    round_num = state["round"]
    my_score = state["total_scores"].get(PLAYER, 0.0)
    opp_score = state["total_scores"].get("A", 0.0)

    system = (
        f"You are playing the Ultimatum Game. There are {state['round_total']} rounds.\n"
        f"Each round, one player proposes how to split {total} points; the other accepts or rejects.\n"
        f"If accepted: proposer keeps (total - offer), responder receives offer.\n"
        f"If rejected: both players receive 0 for that round.\n"
        f"Roles alternate each round.\n\n"
        "Respond with exactly one word: accept or reject."
    )

    history_text = ""
    for entry in history:
        proposer_label = "You" if entry["proposer"] == PLAYER else "Opponent"
        history_text += f"Round {entry['round']}: {proposer_label} proposed {entry['offer']} → {entry['response']}\n"

    user = (
        f"Round {round_num} of {state['round_total']}. You are the RESPONDER.\n"
        f"Your total score: {my_score} | Opponent's score: {opp_score}\n"
        f"The proposer offers you {offer} out of {total} ({offer_fraction*100:.0f}%).\n\n"
        f"History:\n{history_text}\n"
        "Do you accept or reject this offer?\n"
        "Respond with exactly one word: accept or reject."
    )

    return system, user


def main():
    print(f"=== Ultimatum Bot (Player {PLAYER}) ===")
    print(f"Session: {SESSION_ID}")

    while True:
        state = get_state()
        phase = state.get("phase")
        round_num = state.get("round")
        total = state.get("total", 100)

        print(f"\nRound {round_num}/{state['round_total']} | Phase: {phase}")
        print(f"Proposer: {state.get('proposer')} | Responder: {state.get('responder')}")
        print(f"Scores: A={state['total_scores'].get('A', 0)}, B={state['total_scores'].get('B', 0)}")

        if phase == "complete":
            print("\n=== GAME OVER ===")
            print(f"Final scores: A={state['total_scores']['A']}, B={state['total_scores']['B']}")
            if state["history"]:
                print("\nHistory:")
                for entry in state["history"]:
                    print(f"  Round {entry['round']}: {entry['proposer']} proposed {entry['offer']} → {entry['response']}")
            break

        if PLAYER not in state.get("awaiting", []):
            print(f"Waiting for Player A...")
            time.sleep(2)
            continue

        if phase == "awaiting_proposal":
            system, user = build_proposer_prompts(state)
            print(f"\nAsking GLM-5.1 (as proposer)...")
            response = ask_glm(system, user)
            print(f"GLM-5.1 response: {response}")

            offer = parse_offer(response, total)
            print(f"Parsed offer: {offer}")

            result = submit_action({"offer": offer})
            print(f"Submit result: phase={result.get('phase')}, pending_offer={result.get('pending_offer')}")

        elif phase == "awaiting_response":
            system, user = build_responder_prompts(state)
            print(f"\nAsking GLM-5.1 (as responder)...")
            response = ask_glm(system, user)
            print(f"GLM-5.1 response: {response}")

            decision = parse_response(response)
            print(f"Parsed decision: {decision}")

            result = submit_action({"accept": decision == "accept"})
            print(f"Submit result: phase={result.get('phase')}")

        time.sleep(1)


if __name__ == "__main__":
    main()
