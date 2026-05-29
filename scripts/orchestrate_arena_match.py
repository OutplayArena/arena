import json
import os
import sys
import re
import ast
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx

from nash_arena.client import ArenaClient
from games.core.blotto.config import BlottoExperimentConfig
from nash_arena.reasoning import ReasoningControlEngine, ReasoningEffort

sys.stdout.reconfigure(line_buffering=True)

ARENA_BASE_URL = os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000")
OPENCODE_GO_API_KEY = os.environ.get("OPENCODE_GO_API_KEY_2", "").strip()
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/go/v1"

PLAYER_A_MODEL = "deepseek-v4-flash"
PLAYER_B_MODEL = "kimi-k2.5"

REASONING_EFFORT = ReasoningEffort.NONE
TEMPERATURE = 0.9

NUM_BATTLEFIELDS = 5
TOTAL_RESOURCES = 100
NUM_ROUNDS = 20


def balanced_allocation(num_battlefields, total_resources):
    base = total_resources // num_battlefields
    allocation = [base] * num_battlefields
    for i in range(total_resources - sum(allocation)):
        allocation[i] += 1
    return allocation


def parse_allocation(text, num_battlefields, total_resources):
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return balanced_allocation(num_battlefields, total_resources)
    try:
        allocation = ast.literal_eval(match.group())
    except (SyntaxError, ValueError):
        return balanced_allocation(num_battlefields, total_resources)
    if not isinstance(allocation, list):
        return balanced_allocation(num_battlefields, total_resources)
    if len(allocation) != num_battlefields:
        return balanced_allocation(num_battlefields, total_resources)
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in allocation):
        return balanced_allocation(num_battlefields, total_resources)
    if not all(x >= 0 for x in allocation):
        return balanced_allocation(num_battlefields, total_resources)
    if sum(allocation) != total_resources:
        return balanced_allocation(num_battlefields, total_resources)
    return allocation


def build_prompt(state, player_label):
    history = state.get("history", [])
    round_num = state.get("round", 1)
    round_total = state.get("round_total", NUM_ROUNDS)

    lines = [f"Round {round_num}/{round_total}. Allocate 100 across 5 fields."]

    if history:
        h = history[-1]
        lines.append(f"Previous: {h['allocations'][player_label]}")

    lines.append("Your allocation:")
    return "\n".join(lines)


def llm_allocate(model, prompt):
    engine = ReasoningControlEngine(model, effort=REASONING_EFFORT)
    base_system = (
        "You are an allocation bot. Output format: a Python list of 5 non-negative integers summing to 100. "
        "No text before or after the list."
    )
    system_msg = engine.build_system_prompt(base_system)
    limits = engine.get_limits()
    fallback = balanced_allocation(NUM_BATTLEFIELDS, TOTAL_RESOURCES)

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    request_body = engine.prepare_request_body(messages, temperature=TEMPERATURE)

    for attempt in range(3):
        try:
            t0 = time.time()
            resp = httpx.post(
                f"{OPENCODE_GO_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENCODE_GO_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=request_body,
                timeout=limits["timeout"],
            )

            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  [{model}] 429 rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            dt = time.time() - t0

            choice = data["choices"][0]
            finish = choice.get("finish_reason")
            content, reasoning = engine.extract_response_text(data)

            text = content if content.strip() else reasoning
            alloc = parse_allocation(text, NUM_BATTLEFIELDS, TOTAL_RESOURCES)
            is_fallback = alloc == fallback and not content.strip()

            print(
                f"  [{model}] {dt:.1f}s finish={finish} "
                f"content={repr(content)[:60] or '(empty)'} "
                f"→ {alloc}"
                + (" (from reasoning)" if not content.strip() and reasoning else "")
                + (" (FALLBACK)" if is_fallback else "")
            )
            return alloc, text

        except (httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            print(f"  [{model}] timeout ({exc.__class__.__name__}) attempt {attempt+1}/3")

    print(f"  [{model}] all retries exhausted, using uniform allocation")
    return fallback, ""


def run_match():
    if not OPENCODE_GO_API_KEY:
        print("ERROR: OPENCODE_GO_API_KEY environment variable is required")
        sys.exit(1)

    print("Creating arena session...")
    arena = ArenaClient(ARENA_BASE_URL)
    config = BlottoExperimentConfig.classic(
        num_battlefields=NUM_BATTLEFIELDS,
        total_resources=TOTAL_RESOURCES,
        rounds=NUM_ROUNDS,
        seed=42,
    )
    created = arena.create_experiment(config)
    session_id = created["session_id"]
    token_a = created["player_tokens"]["A"]
    token_b = created["player_tokens"]["B"]

    agent_a = ArenaClient(ARENA_BASE_URL, session_id=session_id, token=token_a)
    agent_b = ArenaClient(ARENA_BASE_URL, session_id=session_id, token=token_b)

    print(f"Session: {session_id}")
    print(f"Player A ({PLAYER_A_MODEL}) vs Player B ({PLAYER_B_MODEL})")
    print(f"Config: {NUM_BATTLEFIELDS} battlefields, {TOTAL_RESOURCES} troops, {NUM_ROUNDS} rounds")
    print()

    full_history = []

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        t_round = time.time()

        state = agent_a.get_state()

        if state.get("phase") == "complete":
            break

        prompt_a = build_prompt(state, "A")
        prompt_b = build_prompt(state, "B")

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(llm_allocate, PLAYER_A_MODEL, prompt_a)
            future_b = pool.submit(llm_allocate, PLAYER_B_MODEL, prompt_b)
            alloc_a, raw_a = future_a.result()
            alloc_b, raw_b = future_b.result()

        agent_a.submit_action(alloc_a)
        agent_b.submit_action(alloc_b)

        updated = agent_a.get_state()
        round_history = updated.get("history", [])
        if round_history:
            last = round_history[-1]
            a_score = last["scores"]["A"]
            b_score = last["scores"]["B"]
            winner = last["winner"]
            full_history.append(last)
            dt = time.time() - t_round
            print(
                f"Round {round_num:2d}: "
                f"A={alloc_a} B={alloc_b} → "
                f"A={a_score:.1f} B={b_score:.1f} winner={winner} "
                f"({dt:.0f}s)"
            )
        else:
            print(f"Round {round_num:2d}: A={alloc_a} B={alloc_b} (resolving...)")

    results = agent_a.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print()
    print("=" * 50)
    winner_label = (
        f"Player A ({PLAYER_A_MODEL})"
        if winner == "A"
        else f"Player B ({PLAYER_B_MODEL})"
        if winner == "B"
        else "Tie"
    )
    print(f"Winner: {winner_label}")
    print(f"Final score: A={total_a:.1f}  B={total_b:.1f}")
    if metrics:
        print(f"Metrics: {json.dumps(metrics, indent=2)}")

    output = {
        "session_id": session_id,
        "config": {
            "num_battlefields": NUM_BATTLEFIELDS,
            "total_resources": TOTAL_RESOURCES,
            "num_rounds": NUM_ROUNDS,
            "seed": 42,
        },
        "player_a": {"model": PLAYER_A_MODEL, "label": "A"},
        "player_b": {"model": PLAYER_B_MODEL, "label": "B"},
        "total_scores": {"A": total_a, "B": total_b},
        "winner": winner,
        "history": full_history,
        "metrics": metrics,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results_{ts}.json"
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {filename}")


if __name__ == "__main__":
    run_match()
