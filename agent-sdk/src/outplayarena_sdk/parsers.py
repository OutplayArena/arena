"""Action parsers for the OutplayArena SDK.

Each parser turns raw LLM text into a structured game action. The parsers
are forgiving: when the LLM produces unparseable output, they fall back to
a safe default rather than raising, so the agent loop never crashes on
bad generations.

The parsers were lifted from the old ``llm_agent.py`` so they can be reused
by per-game :class:`BaseAgent` subclasses and by the high-level
``quick_play`` helper.
"""
from __future__ import annotations

import ast
import json
import re
from typing import Any


def parse_allocation(text: str, n_fields: int, total: int) -> list[int]:
    """Parse a list allocation from LLM output.

    Searches *text* for the first substring that looks like a Python list
    (e.g. ``"[3, 2, 5]"``), evaluates it, and validates that it contains
    exactly *n_fields* non-negative integers summing to *total*.  If the
    text cannot be parsed or the allocation is invalid, a balanced default
    allocation is returned instead.

    Args:
        text: Raw text output from the LLM potentially containing a list.
        n_fields: Required number of fields (length of the allocation list).
        total: Required total that all allocation values must sum to.

    Returns:
        A list of *n_fields* non-negative integers summing to *total*.
    """
    match = re.search(r"\[[^\]]+\]", text)
    if match is None:
        return _balanced_allocation(n_fields, total)
    try:
        alloc = ast.literal_eval(match.group())
    except (SyntaxError, ValueError):
        return _balanced_allocation(n_fields, total)
    if not isinstance(alloc, list) or len(alloc) != n_fields:
        return _balanced_allocation(n_fields, total)
    if (
        not all(isinstance(x, int) and not isinstance(x, bool) for x in alloc)
        or not all(x >= 0 for x in alloc)
    ):
        return _balanced_allocation(n_fields, total)
    if sum(alloc) != total:
        return _balanced_allocation(n_fields, total)
    return alloc


def parse_offer(text: str, total: float, min_offer: float = 0.0) -> float:
    """Parse a numeric offer from LLM output.

    Extracts the first number found in *text* and clamps it to the range
    ``[min_offer, total]``.  If no number is found, returns ``total * 0.4``
    as a default offer.
    """
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if nums:
        return max(min_offer, min(float(nums[0]), total))
    return total * 0.4


def parse_accept_reject(text: str) -> str:
    """Parse an accept/reject decision from LLM output.

    Returns ``"accept"`` if the stripped, lowercased *text* contains the
    word ``"accept"``; otherwise returns ``"reject"``.
    """
    return "accept" if "accept" in text.strip().lower() else "reject"


def parse_choice(text: str, options: list[str], default: str | None = None) -> str:
    """Parse a single-token choice from a closed set.

    Picks the first *option* whose lowercase form appears as a whole
    word in *text* (case-insensitive, with word boundaries).  This
    avoids spurious matches like ``"a" in "garbage"``.

    Args:
        text: Raw LLM output.
        options: Allowed action tokens, e.g. ``["cooperate", "defect"]``.
        default: Token to return if no option is found. If ``None``,
            the first option is used.

    Returns:
        One of the strings in *options* (verbatim).
    """
    lowered = text.lower()
    for opt in options:
        # Use a word-boundary match. Escape the option to avoid
        # regex injection from the input.
        pattern = r"\b" + re.escape(opt.lower()) + r"\b"
        if re.search(pattern, lowered):
            return opt
    return default if default is not None else options[0]


def parse_quantity(
    text: str,
    max_quantity: float,
    default: float | None = None,
) -> float:
    """Parse a non-negative numeric quantity from LLM output.

    Used by Cournot Duopoly (production quantity) and Public Goods
    (contribution). Recognizes a leading minus sign and clamps
    negatives to ``0``. Clamps values above *max_quantity* down to
    *max_quantity*.

    Args:
        text: Raw LLM output.
        max_quantity: Upper bound; values above are clamped down.
        default: Value to return if no number is found. If ``None``,
            returns ``max_quantity * 0.5``.
    """
    # Match an optional leading minus, then digits, then optional fraction.
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if match:
        value = float(match.group())
        return max(0.0, min(value, max_quantity))
    if default is not None:
        return max(0.0, min(default, max_quantity))
    return max_quantity * 0.5


def parse_poker_action(
    text: str,
    legal_moves: list[str],
    default_move: str = "fold",
) -> tuple[str, float]:
    """Parse a poker-style action from LLM output.

    Returns ``(move, amount)``.  *amount* is ``0.0`` for non-betting moves
    (``check``, ``call``, ``fold``, ``all_in``); it is parsed from the
    text for ``bet`` and ``raise`` moves.

    Underscores in move names are normalized to spaces for the
    substring match, so ``"all_in"`` matches both ``"all_in"`` and
    ``"all in"`` in the LLM output.

    Args:
        text: Raw LLM output.
        legal_moves: The subset of moves currently legal in the state.
        default_move: Move to return if no recognized token is found.
    """
    lowered = text.lower().replace("_", " ")
    move = default_move
    for m in legal_moves:
        needle = m.lower().replace("_", " ")
        if needle in lowered:
            move = m
            break

    amount = 0.0
    if move in ("bet", "raise"):
        nums = re.findall(r"\d+(?:\.\d+)?", text)
        if nums:
            amount = max(0.0, float(nums[0]))
    return move, amount


def _balanced_allocation(n: int, total: int) -> list[int]:
    """Compute a balanced allocation that sums to *total* across *n* fields.

    Remainder is distributed one-per-field starting from index 0.
    """
    if n <= 0:
        return []
    base = total // n
    alloc = [base] * n
    for i in range(total - sum(alloc)):
        alloc[i % n] += 1
    return alloc


def _safe_json_loads(text: str) -> Any:
    """Try to parse *text* as JSON; return ``None`` on failure."""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


__all__ = [
    "parse_allocation",
    "parse_offer",
    "parse_accept_reject",
    "parse_choice",
    "parse_quantity",
    "parse_poker_action",
    "_balanced_allocation",
    "_safe_json_loads",
]
