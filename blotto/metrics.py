def compute_blotto_metrics(history, total_scores):
    payoff_average = average_payoff(history, total_scores)
    win_counts = round_win_counts(history)
    win_rate = round_win_rate(history, win_counts)
    concentration = allocation_concentration(history)
    
    return {
        "total_payoff": dict(total_scores),
        "average_payoff": payoff_average,
        "round_win_counts": win_counts,
        "round_win_rate": win_rate,
        "allocation_concentration": concentration,
    }
	    
def average_payoff(history, total_scores):
    num_rounds = len(history)
    if num_rounds == 0:
        return {player: 0 for player in total_scores}

    return {player: score / num_rounds for player, score in total_scores.items()}

def round_win_counts(history):
    counts = {"A": 0, "B": 0, "Tie": 0}
    for entry in history:
        winner = entry.get("winner")
        if winner not in counts:
            raise ValueError(f"unknown round winner: {winner}")
        counts[winner] += 1
    
    return counts
	    
def round_win_rate(history, round_win_counts):
    num_rounds = len(history)
    if num_rounds == 0:
        return {player: 0 for player in round_win_counts}
	    
    return {player: count / num_rounds for player, count in round_win_counts.items()}
	    
def allocation_concentration(history):
    totals = {"A": 0.0, "B": 0.0}
    counts = {"A": 0, "B": 0}

    for entry in history:
        for player, allocation in entry.get("allocations", {}).items():
            allocation_total = sum(allocation)
            concentration = 0 if allocation_total == 0 else max(allocation) / allocation_total
            totals[player] = totals.get(player, 0.0) + concentration
            counts[player] = counts.get(player, 0) + 1

    return {
        player: (totals[player] / counts[player] if counts[player] else 0)
        for player in totals
    }
