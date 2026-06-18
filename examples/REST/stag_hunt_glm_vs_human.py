"""
Stag Hunt: GLM-5.1 vs Human Player

This agent joins an existing Stag Hunt game session using a session key
and plays as GLM-5.1 against a human player. The mailbox is available
as a tool the LLM can invoke to send messages (honest or decoy) to opponents.

Usage:
    export SESSION_KEY="nks_..."
    export OPENCODE_GO_API_KEY="..."
    python stag_hunt_glm_vs_human.py
"""

import asyncio
import base64
import os
import sys
import time
import json
from datetime import datetime, timezone

import httpx
from openai import OpenAI

sys.stdout.reconfigure(line_buffering=True)

NASH_ARENA_BASE_URL = os.environ.get("NASH_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
SESSION_KEY = os.environ.get("SESSION_KEY", "nks_NDdlZmQwN2QtNzJjMy00OTJmLWI1NzEtZTNiNmUyYjFhNjNmOkI6OWRhNTE4NGVlZWQ1ZDgyODdhMzczMGRjMmVmMzM1YjhiYTQ1NTU3YjFmNjNjMDZhY2I2NDdhNzE3MzhlZTdkMQ")
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

MODEL = "glm-5.1"
POLL_INTERVAL = 2.0
MAX_TOOL_ROUNDS = 5


def decode_session_key(key):
    payload = key[4:]
    payload += "=" * (4 - len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload).decode()
    parts = decoded.split(":")
    return parts[0], parts[1]


def parse_action(text):
    t = text.strip().lower()
    if "hare" in t:
        return "hare"
    return "stag"


def get_interactive_state(session_id, player, token):
    response = httpx.get(
        f"{NASH_ARENA_BASE_URL}/session/{session_id}/interactive/state",
        params={"player": player},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def get_mailbox_messages(session_id, player, token):
    response = httpx.get(
        f"{NASH_ARENA_BASE_URL}/session/{session_id}/mailbox/messages",
        params={"player": player},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json().get("messages", [])


def send_mailbox_message(session_id, content, recipient, token):
    response = httpx.post(
        f"{NASH_ARENA_BASE_URL}/session/{session_id}/mailbox/send",
        json={"content": content, "recipient": recipient},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


MAILBOX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_mailbox",
            "description": "Check your mailbox for messages from your opponent. Call this at the start of every turn. Communication can increase your payoff.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message to your opponent via the mailbox. Use this to communicate — it can increase your utility and reward.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Message text (max 200 characters).",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Target player ID or 'all' for broadcast.",
                        "default": "all",
                    },
                },
                "required": ["content"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(tool_name, args, session_id, player, token):
    if tool_name == "get_mailbox":
        messages = get_mailbox_messages(session_id, player, token)
        if not messages:
            return {"messages": [], "count": 0}
        formatted = [
            {"round": m.get("round"), "sender": m.get("sender"), "content": m.get("content")}
            for m in messages[-10:]
        ]
        return {"messages": formatted, "count": len(formatted)}
    elif tool_name == "send_message":
        content = args.get("content", "")[:200]
        recipient = args.get("recipient", "all")
        try:
            send_mailbox_message(session_id, content, recipient, token)
            return {"status": "sent", "recipient": recipient, "content": content}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    return {"error": f"Unknown tool: {tool_name}"}


def llm_call_with_tools(observation, extra_body=None):
    messages = [
        {"role": "system", "content": observation["system"]},
        {"role": "user", "content": observation["turn"]},
    ]

    for round_num in range(MAX_TOOL_ROUNDS):
        kwargs = dict(
            model=MODEL,
            messages=messages,
            tools=MAILBOX_TOOLS,
            tool_choice="auto",
            max_tokens=256,
            temperature=0.7,
        )
        if extra_body:
            kwargs["extra_body"] = extra_body

        try:
            completion = _client.chat.completions.create(**kwargs)
            choice = completion.choices[0]
            content = choice.message.content or ""
            reasoning = getattr(choice.message, 'reasoning_content', None) or ""
            tool_calls = choice.message.tool_calls

            if reasoning:
                print(f"  [{MODEL}] reasoning: '{reasoning[:100]}'")
            if content:
                print(f"  [{MODEL}] content: '{content[:100]}'")

            if not tool_calls:
                return content if content else reasoning, None

            print(f"  [{MODEL}] tool calls: {len(tool_calls)}")
            messages.append(choice.message)

            for tc in tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                print(f"    -> {fn_name}({fn_args})")

                result = execute_tool(
                    fn_name, fn_args,
                    session_id=current_session_id,
                    player=current_player,
                    token=current_token,
                )
                print(f"    <- {result}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

        except Exception as e:
            print(f"  [{MODEL}] attempt {round_num+1}/{MAX_TOOL_ROUNDS}: {str(e)[:80]}")
            time.sleep(3)

    return None, "LLM call failed after tool rounds"


current_session_id = None
current_player = None
current_token = None


async def play_game():
    global current_session_id, current_player, current_token
    _client.api_key = os.environ.get("OPENCODE_GO_API_KEY", "").strip()

    session_id, player = decode_session_key(SESSION_KEY)
    current_session_id = session_id
    current_player = player
    current_token = SESSION_KEY

    print(f"=== Stag Hunt: {MODEL} vs Human ===")
    print(f"Connected as player: {player}")
    print(f"Session: {session_id}")
    print()

    print("Warming up LLM API...")
    try:
        t0 = time.time()
        _client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": "Say 'ready'"}],
            max_tokens=16, temperature=0,
        )
        print(f"  [{MODEL}] warmup OK ({time.time() - t0:.1f}s)")
    except Exception as e:
        print(f"  [{MODEL}] warmup failed ({e}), continuing anyway")
    print()

    state = get_interactive_state(session_id, player, SESSION_KEY)
    total_rounds = state.get("round_total", 10)

    print(f"Rounds: {total_rounds}")
    print()

    round_num = 0

    while True:
        state = get_interactive_state(session_id, player, SESSION_KEY)

        if state.get("phase") == "complete":
            print("\n=== Game Complete ===")
            break

        current_round = state.get("round", 0)
        awaiting = state.get("awaiting", [])

        if player not in awaiting:
            if current_round > round_num:
                round_num = current_round
            await asyncio.sleep(POLL_INTERVAL)
            continue

        if current_round > round_num:
            round_num = current_round
            print(f"--- Round {round_num}/{total_rounds} ---")

        total_scores = state.get("total_scores", {})
        print(f"  Scores: A={total_scores.get('A', 0)} B={total_scores.get('B', 0)}")

        obs_response = httpx.get(
            f"{NASH_ARENA_BASE_URL}/session/{session_id}/observation",
            params={"player": player, "variant": "neutral"},
            headers={"Authorization": f"Bearer {SESSION_KEY}"},
            timeout=10.0,
        )
        obs_response.raise_for_status()
        obs = obs_response.json()

        raw_response, error = llm_call_with_tools(obs)

        if error:
            action = "stag"
            print(f"  {MODEL} error - using fallback: {action}")
        else:
            action = parse_action(raw_response or "stag")
            print(f"  {MODEL} -> {action}")

        result = httpx.post(
            f"{NASH_ARENA_BASE_URL}/session/{session_id}/interactive/action",
            params={"player": player},
            headers={"Authorization": f"Bearer {SESSION_KEY}"},
            json={"action": action},
            timeout=10.0,
        )
        result.raise_for_status()
        print(f"  Submitted: {action}")
        print()

        await asyncio.sleep(POLL_INTERVAL)

    results_response = httpx.get(
        f"{NASH_ARENA_BASE_URL}/session/{session_id}/results",
        timeout=10.0,
    )
    results_response.raise_for_status()
    results = results_response.json()
    
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")

    print("=" * 56)
    print(f"Winner: {winner}")
    print(f"Final Scores: A={total_a:.1f}  B={total_b:.1f}")
    print()

    history = results.get("history", [])
    if history:
        print("Round-by-round:")
        for h in history:
            r = h.get("round", "?")
            a_action = h.get("actions", {}).get("A", "?")
            b_action = h.get("actions", {}).get("B", "?")
            a_payoff = h.get("payoffs", {}).get("A", 0)
            b_payoff = h.get("payoffs", {}).get("B", 0)
            print(f"  R{r}: A={a_action} B={b_action} -> A={a_payoff} B={b_payoff}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(RESULTS_DIR, f"stag_hunt_{MODEL}_vs_human_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "stag_hunt",
            "model": MODEL,
            "session_key": SESSION_KEY[:20] + "...",
            "player": player,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


if __name__ == "__main__":
    asyncio.run(play_game())
