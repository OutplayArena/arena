import asyncio
import os
import re
import ast
import sys
import time

from openai import OpenAI

from outplaylabs_arena_sdk import ArenaClient
from games.core.colonelblotto.config import ColonelBlottoExperimentConfig

sys.stdout.reconfigure(line_buffering=True)

OUTPLAYLABS_ARENA_BASE_URL = os.environ.get("OUTPLAYLABS_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
NUM_BATTLEFIELDS = 5
TOTAL_RESOURCES = 100
NUM_ROUNDS = 3


def balanced_allocation(n, total):
    base = total // n
    alloc = [base] * n
    for i in range(total - sum(alloc)):
        alloc[i] += 1
    return alloc


def parse_allocation(text, n_fields, total_res):
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return balanced_allocation(n_fields, total_res)
    try:
        alloc = ast.literal_eval(match.group())
    except (SyntaxError, ValueError):
        return balanced_allocation(n_fields, total_res)
    if not isinstance(alloc, list) or len(alloc) != n_fields:
        return balanced_allocation(n_fields, total_res)
    if not all(isinstance(x, int) for x in alloc) or not all(x >= 0 for x in alloc):
        return balanced_allocation(n_fields, total_res)
    if sum(alloc) != total_res:
        return balanced_allocation(n_fields, total_res)
    return alloc


def build_prompt(state, player_label):
    history = state.get("history", [])
    round_num = state.get("round", 1)
    round_total = state.get("round_total", NUM_ROUNDS)
    total_scores = state.get("total_scores", {})

    lines = [
        f"R{round_num}/{round_total}. You={player_label}. Troops={TOTAL_RESOURCES}. "
        f"Fields={NUM_BATTLEFIELDS}. Scores A={total_scores.get('A', 0)} B={total_scores.get('B', 0)}.",
    ]
    if history:
        for h in history[-3:]:
            lines.append(
                f"R{h['round']}: A={h['allocations']['A']} B={h['allocations']['B']} -> {h['winner']}"
            )
    lines.append("Allocation:")
    return "\n".join(lines)


def make_system_msg():
    return (
        f"You are playing the resource allocation game. "
        f"Distribute exactly {TOTAL_RESOURCES} troops across {NUM_BATTLEFIELDS} equal battlefields. "
        "Output ONLY a Python list of integers. No other text."
    )


def sync_llm_call(model, system_msg, prompt, extra_body=None):
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        max_tokens=4096,
        temperature=0.7,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body

    for attempt in range(2):
        try:
            t0 = time.time()
            completion = _client.chat.completions.create(**kwargs)
            content = completion.choices[0].message.content or ""
            dt = time.time() - t0
            alloc = parse_allocation(content, NUM_BATTLEFIELDS, TOTAL_RESOURCES)
            print(f"  [{model}] {dt:.1f}s -> {alloc}")
            return alloc, None
        except Exception as e:
            msg = str(e)[:80]
            print(f"  [{model}] attempt {attempt+1}/2: {msg}")
            time.sleep(5)
    print(f"  [{model}] FAILED — forfeiting round")
    return None, "LLM call failed"


async def llm_allocate(model, prompt, extra_body=None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sync_llm_call, model, make_system_msg(), prompt, extra_body)


async def run_match():
    nash_api_key = os.environ["OUTPLAYLABS_ARENA_API_KEY"]
    opencode_api_key = os.environ["OPENCODE_GO_API_KEY"]
    _client.api_key = opencode_api_key.strip()

    print(f"=== {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Battlefields: {NUM_BATTLEFIELDS}, Troops: {TOTAL_RESOURCES}, Rounds: {NUM_ROUNDS}")
    print("GLM 5.1: no thinking mode | DeepSeek V4 Pro: thinking mode")
    print()

    print("Warming up LLM APIs...")
    for model in [PLAYER_A_MODEL, PLAYER_B_MODEL]:
        try:
            t0 = time.time()
            completion = _client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Say 'ready'"},
                ],
                max_tokens=256,
                temperature=0,
            )
            content = completion.choices[0].message.content or ""
            print(f"  [{model}] warmup OK ({len(content)} chars, {time.time() - t0:.1f}s)")
        except Exception as e:
            print(f"  [{model}] warmup failed ({e}), continuing anyway")
    print()

    arena = ArenaClient(OUTPLAYLABS_ARENA_BASE_URL)
    config = ColonelBlottoExperimentConfig.classic(
        num_battlefields=NUM_BATTLEFIELDS,
        total_resources=TOTAL_RESOURCES,
        rounds=NUM_ROUNDS,
        seed=42,
    )
    created = arena.create_experiment(
        config,
        agents={"A": PLAYER_A_MODEL, "B": PLAYER_B_MODEL},
        api_key=nash_api_key,
    )
    session_id = created["session_id"]
    created["player_tokens"]["A"]
    created["player_tokens"]["B"]
    print(f"Session: {session_id}")
    print()

    player_a = ArenaClient.for_player(OUTPLAYLABS_ARENA_BASE_URL, created, "A")
    player_b = ArenaClient.for_player(OUTPLAYLABS_ARENA_BASE_URL, created, "B")

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        state = player_a.get_state()
        if state.get("phase") == "complete":
            break

        prompt_a = build_prompt(state, "A")
        prompt_b = build_prompt(state, "B")

        # Both LLMs think concurrently
        (alloc_a, error_a), (alloc_b, error_b) = await asyncio.gather(
            llm_allocate(PLAYER_A_MODEL, prompt_a),
            llm_allocate(PLAYER_B_MODEL, prompt_b, extra_body={"thinking": {"type": "enabled", "budget_tokens": 2048}}),
        )

        if error_a:
            alloc_a = balanced_allocation(NUM_BATTLEFIELDS, TOTAL_RESOURCES)
            print(f"  {PLAYER_A_MODEL} forfeit — using balanced fallback: {alloc_a}")
        if error_b:
            alloc_b = balanced_allocation(NUM_BATTLEFIELDS, TOTAL_RESOURCES)
            print(f"  {PLAYER_B_MODEL} forfeit — using balanced fallback: {alloc_b}")

        player_a.submit_action(alloc_a)
        player_b.submit_action(alloc_b)

        state_after = player_a.get_state()
        if state_after.get("history"):
            last = state_after["history"][-1]
            print(
                f"  A({PLAYER_A_MODEL})={alloc_a}  B({PLAYER_B_MODEL})={alloc_b}"
            )
            print(
                f"  Scores: A={last['scores']['A']:.1f} B={last['scores']['B']:.1f} -> {last['winner']}"
            )
        print()

    results = player_a.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")

    print("=" * 56)
    winner_label = (
        f"{PLAYER_A_MODEL} (A)" if winner == "A"
        else f"{PLAYER_B_MODEL} (B)" if winner == "B"
        else "Tie"
    )
    print(f"Winner: {winner_label}")
    print(f"Final: A({PLAYER_A_MODEL})={total_a:.1f}  B({PLAYER_B_MODEL})={total_b:.1f}")
    print(f"Replay: http://localhost:5173/play/colonelblotto/{session_id}")


if __name__ == "__main__":
    asyncio.run(run_match())
