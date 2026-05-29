"""Test prompt variants for reasoning budget control."""

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

OPENCODE_GO_API_KEY = os.environ.get("OPENCODE_GO_API_KEY_2", "").strip()
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/go/v1"

MODELS = ["mimo-v2.5", "glm-5.1"]
NUM_RUNS = 5
TEMPERATURE = 0.9
MAX_TOKENS = 512

BASE_SYSTEM = (
    "You are a General playing Colonel Blotto. "
    "Distribute exactly 100 troops across 5 battlefields. "
    "Output a Python list like [30,25,20,15,10]."
)

EFFORT_INSTRUCTIONS = {
    "none": "You have NO time to think. Respond immediately with ONLY the list. No analysis, no strategy discussion.",
    "low": "You have a brief moment. Think in at most 1 sentence, then output the list.",
    "medium": "You have time for a short assessment. Think in 2-3 sentences, then output the list.",
    "high": "Take your time to analyze the situation thoroughly before outputting the list.",
}

USER_PROMPT_TEMPLATE = """Round {round}/{total}. Allocate 100 across 5 fields.
Previous: {prev}
Your allocation:"""


@dataclass
class TestResult:
    model: str
    effort: str
    variant: str
    run: int
    time_s: float
    reasoning_tokens: int
    total_tokens: int
    allocation: Optional[list[int]]
    parse_success: bool
    raw_content: str


def parse_allocation(text: Optional[str]) -> Optional[list[int]]:
    """Extract Python list from text."""
    if not text:
        return None
    match = re.search(r"\[[^\]]+\]", text)
    if not match:
        return None
    try:
        nums = [int(x.strip()) for x in match.group()[1:-1].split(",")]
        if len(nums) == 5 and sum(nums) == 100 and all(n >= 0 for n in nums):
            return nums
    except (ValueError, SyntaxError):
        pass
    return None


def call_model(model: str, system: str, user: str) -> tuple[float, int, int, str]:
    """Make API call and return (time, reasoning_tokens, total_tokens, content)."""
    t0 = time.time()
    resp = httpx.post(
        f"{OPENCODE_GO_API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENCODE_GO_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
        },
        timeout=60.0,
    )
    dt = time.time() - t0
    
    if resp.status_code != 200:
        return dt, 0, 0, f"HTTP {resp.status_code}"
    
    data = resp.json()
    choice = data["choices"][0]
    usage = data.get("usage", {})
    reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
    total_tokens = usage.get("completion_tokens", 0)
    content = choice["message"].get("content") or ""
    
    return dt, reasoning_tokens, total_tokens, content


def run_test(model: str, effort: str, variant: str, run: int) -> TestResult:
    """Run a single test."""
    system = BASE_SYSTEM
    if effort != "baseline":
        system += " " + EFFORT_INSTRUCTIONS[effort]
    
    user = USER_PROMPT_TEMPLATE.format(
        round=run,
        total=NUM_RUNS,
        prev="[20,20,20,20,20]" if run > 1 else "none"
    )
    
    dt, reasoning_tokens, total_tokens, content = call_model(model, system, user)
    allocation = parse_allocation(content)
    
    return TestResult(
        model=model,
        effort=effort,
        variant=variant,
        run=run,
        time_s=dt,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
        allocation=allocation,
        parse_success=allocation is not None,
        raw_content=content,
    )


def compute_diversity(allocations: list[list[int]]) -> tuple[float, int]:
    """Compute std dev and unique count."""
    if not allocations:
        return 0.0, 0
    
    unique = len(set(tuple(a) for a in allocations))
    
    if len(allocations) < 2:
        return 0.0, unique
    
    import statistics
    flat = [x for alloc in allocations for x in alloc]
    std = statistics.stdev(flat) if len(flat) > 1 else 0.0
    
    return std, unique


def main():
    if not OPENCODE_GO_API_KEY:
        print("ERROR: OPENCODE_GO_API_KEY_2 not set")
        return
    
    results: list[TestResult] = []
    
    print(f"Testing {len(MODELS)} models × {len(EFFORT_INSTRUCTIONS)} effort levels × {NUM_RUNS} runs")
    print("=" * 80)
    
    for model in MODELS:
        for effort in EFFORT_INSTRUCTIONS.keys():
            print(f"\n{model} | effort={effort}")
            for run in range(1, NUM_RUNS + 1):
                result = run_test(model, effort, "budget", run)
                results.append(result)
                print(f"  Run {run}: {result.time_s:.1f}s | reasoning={result.reasoning_tokens:4d} | "
                      f"total={result.total_tokens:4d} | parse={result.parse_success} | "
                      f"alloc={result.allocation}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for model in MODELS:
        print(f"\n{model}")
        print("-" * 80)
        print(f"{'Effort':<10} {'Avg Time':<10} {'Avg Reason':<12} {'Avg Total':<11} "
              f"{'Parse %':<9} {'Std Dev':<9} {'Unique':<8}")
        print("-" * 80)
        
        for effort in EFFORT_INSTRUCTIONS.keys():
            subset = [r for r in results if r.model == model and r.effort == effort]
            
            avg_time = sum(r.time_s for r in subset) / len(subset)
            avg_reason = sum(r.reasoning_tokens for r in subset) / len(subset)
            avg_total = sum(r.total_tokens for r in subset) / len(subset)
            parse_rate = sum(r.parse_success for r in subset) / len(subset) * 100
            
            allocations = [r.allocation for r in subset if r.allocation]
            std_dev, unique = compute_diversity(allocations)
            
            print(f"{effort:<10} {avg_time:<10.1f} {avg_reason:<12.0f} {avg_total:<11.0f} "
                  f"{parse_rate:<9.0f} {std_dev:<9.1f} {unique:<8}")
    
    print("\n" + "=" * 80)
    print("RAW RESULTS")
    print("=" * 80)
    
    for result in results:
        print(f"{result.model:<12} {result.effort:<8} run={result.run} | "
              f"{result.time_s:.1f}s | reason={result.reasoning_tokens:4d} | "
              f"total={result.total_tokens:4d} | {result.raw_content[:60]}")


if __name__ == "__main__":
    main()
