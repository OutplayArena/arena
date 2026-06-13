# Metrics Reference

Comprehensive reference for all metrics tracked across NashArena games.

## Universal Metrics

These metrics are computed for every game:

| Metric | Description |
|--------|-------------|
| `total_payoff` | Cumulative score across all rounds |
| `average_payoff` | Mean score per round |
| `strategy_entropy` | Predictability of strategy |
| `behavioral_consistency` | Stability of behavior over time |
| `cumulative_regret` | Deviation from optimal play |
| `gini_coefficient` | Inequality in payoffs between players |
| `social_welfare` | Total payoff across all players |
| `pareto_efficiency` | How close to Pareto optimal |
| `nash_gap` | Distance from Nash equilibrium |

## Game-Specific Metrics

### Battle of the Sexes

- `coordination_rate`
- `outcome_counts`
- `bos_coordination_rate`
- `bos_a_preferred_rate`
- `bos_b_preferred_rate`
- `equilibrium_selection_rate`

### Centipede Game

- `steps_played`
- `game_ended_early`
- `take_step`
- `cp_steps_played`
- `cp_take_at_step`
- `cp_backward_induction_adherence`
- `cp_cooperation_index`
- `backward_induction_adherence`

### Colonel Blotto

- `round_win_counts`
- `round_win_rate`
- `allocation_concentration`

### Cournot Duopoly

- `avg_quantity`
- `avg_price`
- `avg_total_quantity`
- `cd_avg_quantity_a`
- `cd_avg_quantity_b`
- `cd_nash_quantity`
- `cd_collusive_quantity`
- `cd_collusion_index`

### Prisoner's Dilemma

- `cooperation_rate`
- `mutual_cooperation_rate`
- `mutual_defection_rate`
- `outcome_counts`
- `pd_outcome_counts`
- `pd_mutual_cooperation_rate`
- `pd_price_of_anarchy`
- `exploitation_rate`
- `forgiveness_rate`
- `first_move`
- `tit_for_tat_adherence`
- `forgiveness_index`
- `conditional_cooperation`
- `multilateral_cooperation_index`

### Public Goods Game

- `avg_contribution`
- `contribution_rate`
- `avg_pool`
- `free_rider_count`
- `pgg_avg_pool`
- `pgg_contribution_efficiency`
- `pgg_price_of_anarchy`
- `multilateral_cooperation_index`

### Rock-Paper-Scissors

- `round_win_counts`
- `round_win_rate`
- `move_frequencies`
- `rps_collision_rate`
- `nash_distance`
- `pattern_exploitability`

### Stag Hunt

- `stag_rate`
- `mutual_stag_rate`
- `mutual_hare_rate`
- `outcome_counts`
- `sh_outcome_counts`
- `sh_mutual_stag_rate`
- `sh_mutual_hare_rate`
- `sh_price_of_risk`
- `equilibrium_selection_rate`
- `cooperation_rate`
- `tit_for_tat_adherence`
- `forgiveness_index`
- `conditional_cooperation`
- `multilateral_cooperation_index`

### Texas Hold'em

- `hand_win_counts`
- `hand_win_rate`
- `fold_rate`
- `raise_rate`
- `showdown_count`
- `fold_count`
- `raise_count`
- `the_showdown_rate`

### Ultimatum Game

- `avg_offer_fraction`
- `acceptance_rate`
- `offer_fairness_index`
- `ug_avg_offer_fraction`
- `ug_acceptance_rate`
- `ug_offer_fairness_index`
- `backward_induction_adherence`
