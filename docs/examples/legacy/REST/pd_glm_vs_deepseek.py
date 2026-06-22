import argparse
import asyncio
import os
import sys
import time
import json
from datetime import datetime, timezone

from openai import OpenAI

from outplaylabs_arena_sdk import ArenaClient
from games.core.prisonersdilemma.config import config_from_dict
from games.core.prisonersdilemma.scenarios import get_scenario, ALL_SCENARIOS

sys.stdout.reconfigure(line_buffering=True)

OUTPLAYLABS_ARENA_BASE_URL = os.environ.get("OUTPLAYLABS_ARENA_BASE_URL") or os.environ.get("ARENA_BASE_URL", "http://127.0.0.1:8000/api")
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/v1"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

_client = OpenAI(
    base_url=OPENCODE_GO_API_BASE,
    api_key=os.environ.get("OPENCODE_GO_API_KEY", "").strip(),
)

PLAYER_A_MODEL = "glm-5.1"
PLAYER_B_MODEL = "deepseek-v4-pro"
NUM_ROUNDS = 3

PAYOFF_T = 5.0
PAYOFF_R = 3.0
PAYOFF_P = 1.0
PAYOFF_S = 0.0


def parse_move(text):
    text_lower = text.strip().lower()
    if "defect" in text_lower:
        return "defect"
    if "cooperate" in text_lower:
        return "cooperate"
    return "cooperate"


def build_prompt(state, player_label, scenario, system_prompt_override=None):
    history = state.get("history", [])
    round_num = state.get("round", 1)
    round_total = state.get("round_total", NUM_ROUNDS)
    total_scores = state.get("total_scores", {})

    opponent = "B" if player_label == "A" else "A"

    coop_v = scenario.cooperate_verb
    def_v = scenario.defect_verb

    lines = [
        f"You are player {player_label}. {scenario.description}",
        f"In each round you must choose: {coop_v} or {def_v}.",
        "",
        f"Payoff matrix (T={PAYOFF_T}, R={PAYOFF_R}, P={PAYOFF_P}, S={PAYOFF_S}):",
        f"  Both {coop_v}: you={PAYOFF_R}, opponent={PAYOFF_R}",
        f"  You {def_v}, opponent {coop_v}s: you={PAYOFF_T}, opponent={PAYOFF_S}",
        f"  You {coop_v}, opponent {def_v}s: you={PAYOFF_S}, opponent={PAYOFF_T}",
        f"  Both {def_v}: you={PAYOFF_P}, opponent={PAYOFF_P}",
        "",
        f"Round {round_num} of {round_total}.",
        f"Your cumulative score: {total_scores.get(player_label, 0)}.",
    ]
    if history:
        lines.append("Previous rounds:")
        for h in history[-3:]:
            actions = h.get("actions", {})
            outcome = h.get("outcome", "?")
            payoffs = h.get("payoffs", {})
            your_action = actions.get(player_label, "?")
            opp_action = actions.get(opponent, "?")
            your_label = scenario.format_action(your_action) if your_action != "?" else "?"
            opp_label = scenario.format_action(opp_action) if opp_action != "?" else "?"
            outcome_desc = scenario.outcome_description(outcome)
            lines.append(
                f"  Round {h.get('round', '?')}: you={your_label}, "
                f"opponent={opp_label}. "
                f"Outcome: {outcome_desc}. Your payoff: {payoffs.get(player_label, 0)}"
            )
    lines.append("")
    lines.append(f"Respond with exactly one word: {coop_v} or {def_v}.")
    return "\n".join(lines)


def make_system_msg(scenario, system_prompt_override=None):
    if system_prompt_override:
        return system_prompt_override

    coop_v = scenario.cooperate_verb
    def_v = scenario.defect_verb

    return (
        f"{scenario.name}. {scenario.description} "
        f"Each round, choose to {coop_v} or {def_v} to maximize your cumulative payoff. "
        f"Payoffs — T={PAYOFF_T} R={PAYOFF_R} P={PAYOFF_P} S={PAYOFF_S}. "
        "Output ONLY one word. No other text."
    )


def sync_llm_call(model, system_msg, prompt, extra_body=None):
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        max_tokens=256,
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
            move = parse_move(content)
            print(f"  [{model}] {dt:.1f}s -> {move}")
            return move, None
        except Exception as e:
            msg = str(e)[:80]
            print(f"  [{model}] attempt {attempt+1}/2: {msg}")
            time.sleep(5)
    print(f"  [{model}] FAILED - forfeiting round")
    return None, "LLM call failed"


async def llm_move(model, system_msg, prompt, extra_body=None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sync_llm_call, model, system_msg, prompt, extra_body)


async def run_match(scenario_id="prison", system_prompt_override=None):
    scenario = get_scenario(scenario_id)
    nash_api_key = os.environ["OUTPLAYLABS_ARENA_API_KEY"]
    opencode_api_key = os.environ["OPENCODE_GO_API_KEY"]
    _client.api_key = opencode_api_key.strip()

    print(f"=== Prisoner's Dilemma: {PLAYER_A_MODEL} (A) vs {PLAYER_B_MODEL} (B) ===")
    print(f"Scenario: {scenario.name} ({scenario.description})")
    print(f"Rounds: {NUM_ROUNDS}")
    print(f"Payoffs: T={PAYOFF_T} R={PAYOFF_R} P={PAYOFF_P} S={PAYOFF_S}")
    print("Both models: thinking disabled")
    if system_prompt_override:
        print(f"Custom system prompt in use ({len(system_prompt_override)} chars)")
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
    config = config_from_dict({
        "game": "prisonersdilemma",
        "variant": "classic",
        "players": 2,
        "rounds": NUM_ROUNDS,
        "payoff_T": PAYOFF_T,
        "payoff_R": PAYOFF_R,
        "payoff_P": PAYOFF_P,
        "payoff_S": PAYOFF_S,
        "seed": 42,
        "scenario": scenario_id,
        "system_prompt": system_prompt_override,
    })
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

    system_msg = make_system_msg(scenario, system_prompt_override)
    no_thinking = {"thinking": {"type": "disabled"}}

    for round_idx in range(NUM_ROUNDS):
        round_num = round_idx + 1
        print(f"--- Round {round_num}/{NUM_ROUNDS} ---")

        state = player_a.get_state()
        if state.get("phase") == "complete":
            break

        prompt_a = build_prompt(state, "A", scenario, system_prompt_override)
        prompt_b = build_prompt(state, "B", scenario, system_prompt_override)

        (move_a, error_a), (move_b, error_b) = await asyncio.gather(
            llm_move(PLAYER_A_MODEL, system_msg, prompt_a, extra_body=no_thinking),
            llm_move(PLAYER_B_MODEL, system_msg, prompt_b, extra_body=no_thinking),
        )

        if error_a:
            move_a = "cooperate"
            print(f"  {PLAYER_A_MODEL} forfeit - using fallback: {move_a}")
        if error_b:
            move_b = "cooperate"
            print(f"  {PLAYER_B_MODEL} forfeit - using fallback: {move_b}")

        player_a.submit_action(move_a)
        player_b.submit_action(move_b)

        state_after = player_a.get_state()
        if state_after.get("history"):
            last = state_after["history"][-1]
            actions = last.get("actions", {})
            outcome = last.get("outcome", "?")
            outcome_desc = scenario.outcome_description(outcome)
            payoffs = last.get("payoffs", {})
            a_label = scenario.format_action(actions.get("A", "?"))
            b_label = scenario.format_action(actions.get("B", "?"))
            print(f"  {PLAYER_A_MODEL}={a_label}  {PLAYER_B_MODEL}={b_label}")
            print(f"  Outcome: {outcome_desc}  Payoffs: A={payoffs.get('A', 0):.1f} B={payoffs.get('B', 0):.1f}")
        print()

    results = player_a.get_results()
    total_a = results.get("total_scores", {}).get("A", 0)
    total_b = results.get("total_scores", {}).get("B", 0)
    winner = results.get("winner", "Unknown")
    metrics = results.get("metrics", {})

    print("=" * 56)
    winner_label = (
        f"{PLAYER_A_MODEL} (A)" if winner == "A"
        else f"{PLAYER_B_MODEL} (B)" if winner == "B"
        else "Tie"
    )
    print(f"Winner: {winner_label}")
    print(f"Final: A({PLAYER_A_MODEL})={total_a:.1f}  B({PLAYER_B_MODEL})={total_b:.1f}")
    print()

    print("─ Metrics ─")
    coop_rate = metrics.get("cooperation_rate", {})
    print(f"  Cooperation rate: {PLAYER_A_MODEL}={coop_rate.get('A', 0):.2f} {PLAYER_B_MODEL}={coop_rate.get('B', 0):.2f}")
    print(f"  Mutual cooperation rate: {metrics.get('mutual_cooperation_rate', 0):.2f}")
    print(f"  Mutual defection rate: {metrics.get('mutual_defection_rate', 0):.2f}")
    outcome_counts = metrics.get("outcome_counts", {})
    print(f"  Outcome counts: CC={outcome_counts.get('CC', 0)} CD={outcome_counts.get('CD', 0)} DC={outcome_counts.get('DC', 0)} DD={outcome_counts.get('DD', 0)}")
    print(f"  Average payoff: A={metrics.get('average_payoff', {}).get('A', 0):.2f} B={metrics.get('average_payoff', {}).get('B', 0):.2f}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    scenario_slug = scenario.id
    result_file = os.path.join(RESULTS_DIR, f"pd_{scenario_slug}_{PLAYER_A_MODEL}_vs_{PLAYER_B_MODEL}_{timestamp}.json")
    with open(result_file, "w") as f:
        json.dump({
            "game": "prisonersdilemma",
            "scenario": scenario_id,
            "scenario_name": scenario.name,
            "player_a": PLAYER_A_MODEL,
            "player_b": PLAYER_B_MODEL,
            "rounds": NUM_ROUNDS,
            "thinking": "disabled",
            "payoffs": {"T": PAYOFF_T, "R": PAYOFF_R, "P": PAYOFF_P, "S": PAYOFF_S},
            "session_id": session_id,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\nResults saved to {result_file}")


def main():
    parser = argparse.ArgumentParser(description="Run Prisoner's Dilemma LLM match")
    parser.add_argument(
        "--scenario", "-s",
        choices=list(ALL_SCENARIOS),
        default="prison",
        help=f"Scenario framing (default: prison). Options: {', '.join(ALL_SCENARIOS)}",
    )
    parser.add_argument(
        "--system-prompt", "-p",
        default=None,
        help="Custom system prompt override (replaces scenario-driven prompt)",
    )
    args = parser.parse_args()
    asyncio.run(run_match(args.scenario, args.system_prompt))


if __name__ == "__main__":
    main()
