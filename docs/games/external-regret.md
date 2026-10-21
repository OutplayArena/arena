# External regret for repeated matrix games

External regret asks how much more a player could have earned by committing to
one fixed action, against the **actual observed sequence** of opponent actions.
It evaluates behavior; it neither trains agents nor identifies their internal algorithm.

This evaluation is motivated by Park, Liu, Ozdaglar, and Zhang,
[Do LLM Agents Have Regret? A Case Study in Online Learning and Games (ICLR 2025)](https://proceedings.iclr.cc/paper_files/paper/2025/file/65ea878cb90b440e8b4cd34fe0959914-Paper-Conference.pdf).
The present implementation measures realized, sampled-action regret. It does not
implement regret-loss training or reproduce the paper's experiments or guarantees.

## Definition and interpretation

For player i, with stage payoff u_i and T observed rounds:

```text
R_T(i) = max over a in A_i [sum_{t=1}^T u_i(a, a_{-i,t})]
         - sum_{t=1}^T u_i(a_{i,t}, a_{-i,t})
```

The maximum is **outside** the sum: the comparator uses the same action for all
rounds. Maximizing separately each round gives a different, stronger oracle
comparator. For these finite matrix games, maximizing over fixed mixed strategies
has the same value as the best pure action, since cumulative payoff is linear.

Cumulative regret is a total payoff gap and can grow with the horizon. Average
regret, R_T/T, expresses that gap per round. Every prefix recomputes its own best
fixed action, so its comparator may differ from the final comparator. Curves use
1-based observation indices, even for imported histories numbered from zero.
Equal-best actions are resolved by adapter action order: rock/paper/scissors,
cooperate/defect, or stag/hare. Values are signed and never clamped.

Negative external regret is possible when a changing action sequence beats every
fixed action. For example, playing paper/scissors/rock against the known cyclic
trace rock/paper/scissors earns 3. Every fixed action earns 0, giving R_3 = -3,
average -1, and normalized average -0.5. Prefix regrets are 0, -1, -3. A comparator
allowed to change each round earns 3 and would give zero gap instead.
[Machine-readable hand-checked example](../examples/external_regret/manual_rps.json).

Other hand-checked cases:

| Game and actions (player; opponent) | Actual total | Best fixed total | Cumulative | Average |
|---|---:|---:|---:|---:|
| RPS: rock, rock; paper, paper | -2 | 2 (scissors) | 4 | 2 |
| RPS: rock, rock, rock; rock, paper, scissors | 0 | 0 (rock wins tie) | 0 | 0 |
| PD default: cooperate, defect; cooperate, defect | 4 | 6 (defect) | 2 | 1 |
| Stag Hunt default: stag, hare; stag, hare | 6 | 4 (stag wins tie) | -2 | -1 |

For the player's complete configured stage-payoff matrix, let
`span = max_payoff - min_payoff`. Normalized average regret is `(R_T/T)/span`.
The range uses **all** action pairs, not only observed rewards; negative payoff
values and affine payoff changes are supported. With finite payoffs and positive
span, the signed normalized value lies in [-1, 1], up to floating point error.
When span is zero, raw regret remains valid and normalized values are JSON null.
For RPS the range is [-1, 1]; for PD and Stag Hunt it is derived from the actual
configuration. No equilibrium payoff is substituted for the range.

## Existing metrics and compatibility

`external_regret` is a new object. Historical fields retain their old values:

- `cumulative_regret` is the legacy clamped reference-payoff estimate:
  `max(0, reference_payoff * T - sum(realized_payoffs))`. Its reference does not
  evaluate every fixed action against the observed opponent trace.
- `adaptive_regret_series` uses the largest **realized** payoff in each disjoint
  window as its reference. It is neither windowed external regret nor standard
  adaptive regret. This PR adds no dynamic-regret algorithm.
- Game scores measure achieved reward, not a gap to a comparator. Engines may
  round their running `total_scores` to two decimal places. Exact regret sums the
  logged stage payoffs, before that running-score rounding.
- Nash gap concerns unilateral best-response/equilibrium comparisons. Its existing
  reference-based implementation and output are unchanged; it is not a substitute
  for the trajectory's fixed-action comparator.

Decreasing empirical average regret over finitely many rounds is **evidence
consistent with no-regret behavior, not proof of an asymptotic no-regret guarantee**.
Low measured regret does not prove that an LLM internally implements FTPL or FTRL.

## Supported sessions and result access

Rock Paper Scissors, Prisoner's Dilemma (`prisonersdilemma`), and Stag Hunt support
exact regret for fully observed, normally completed, deterministic rounds. PD and
Stag Hunt use configured payoff values and permit the `noisy` variant only when
its actual noise parameter is zero. All three use the same pure stage-payoff
functions as their engines. No scoring, noise, forfeit, or agent rules change.

The existing `GET /session/{session_id}/results` endpoint (with the deployment's
usual API prefix) exposes both paths:

```python
results = client.get_results()  # existing ArenaClient; no new endpoint
by_role = results["metrics"]["external_regret"]["A"]
by_agent = results["rich_metrics"]["agents"]["my-agent-id"]["external_regret"]
if by_role["status"] == "available":
    print(by_role["cumulative"], by_role["average"])
else:
    print(by_role["reason"])
```

The SDK returns the complete response and `save_results` preserves it. Direct
`game.compute_results(state)` exposes `metrics.external_regret` keyed by player
role. The evaluator uses registered `GameMetricsExtension` implementations, and
`external_regret` is allowed by each supported game's `metrics.yaml`. Numeric
leaderboard aggregation continues to use its existing scalar metrics.
The external-regret subtree retains full floating point precision when other
session metrics are rounded for display. Existing saved reports are not rewritten.
Re-evaluating an accessible historical match adds the new namespace separately.

An available result contains `cumulative`, `average`, `normalized_average`,
`best_fixed_action`, `best_fixed_total_payoff`, `fixed_action_total_payoffs`,
`actual_total_payoff`, `num_rounds`, `payoff_range`, and `series`. Each series point
has a round index, the three regret values, and that prefix's best fixed action.
The final cumulative value is exactly the last series point's cumulative value.

Ambiguous sessions return only an explicit status and reason, for example:

```json
{"status": "unavailable", "reason": "action noise prevents exact decision counterfactuals"}
```

The entire trajectory is unavailable if any round is forfeited, missing actions
or payoffs, duplicated, noncontiguous, inconsistent with configured length, or
inconsistent with the deterministic payoff function. Missing fields are never
silently scored as zero in exact regret. Nonfinite values and invalid
configurations are rejected. Logged payoffs are compared with the engine using
absolute/relative tolerances of 1e-9. Standalone core calls raise `ValueError` for
invalid inputs; empty trajectories explicitly return unavailable. Direct `Match`
imports may omit a planned horizon and completion metadata, in which case all
supplied paired rounds form the evaluation horizon; callers must provide trusted
configuration and preserve noise/forfeit metadata.

Positive action noise is excluded even when the realized round happened not to
flip: logged actions are executed actions, and a counterfactual intended decision
requires a well-defined treatment of randomness. This PR does not estimate
expected noisy regret. Forfeits may fabricate opponent actions or special payoffs
and are excluded even when their action labels look ordinary. Session conversion
and agent namespacing retain this evidence. If two roles resolve to the same agent
identifier, the rich metric reports unavailable because that report cannot
separate the players; the engine's role-keyed results remain available.

Unsupported games omit the metric entirely. Hidden information, stochastic
outcomes, and state-dependent games need explicit future adapters specifying what
is held fixed under counterfactual play. Poker and Blotto have no regret adapter.

## Reproducible offline comparisons

From the repository root, using the existing Python environment:

```bash
uv run --with matplotlib python scripts/external_regret_example.py --rounds 100 --seed 7 \
  --output-dir results/external_regret
```

No paid APIs, model keys, server, or LLM calls are needed. Matplotlib is optional;
`--with matplotlib` installs it in an isolated environment if necessary. Omit that
option to produce JSON/CSV with only the existing dependencies.
The example runs the existing RPS `CounterAgent` and seeded FTPL/FTRL baselines
against constant, cyclic, switching, and uniform generated opponent traces. It
writes full game histories and calculations to `results.json`, tidy prefix data
to `curves.csv`, and plots to `cumulative.svg`, `average.svg`, and corresponding PNG files.
[Small sample curves (12 rounds, seed 7)](../examples/external_regret/curves.csv)
are committed with [cumulative](../examples/external_regret/cumulative.svg) and
[average](../examples/external_regret/average.svg) plots.

Both learners choose before receiving the current opponent action. They maintain
cumulative **full-information** losses for every action, normalized by the whole
matrix: `(max_payoff - payoff)/span`. Constant matrices yield zero losses.

- FTPL samples independent fresh Exp(1) variables Z_t(a) each round and chooses
  `argmin_a [L_{t-1}(a) - Z_t(a)/eta]`. Perturbation scale is `1/eta` in normalized
  loss units. Ties use action order.
- Entropy-regularized FTRL/Hedge minimizes
  `<L_{t-1}, p> + sum_a p(a) log p(a)/eta` on the probability simplex. It samples
  an action with probabilities proportional to `exp(-eta * L_{t-1}(a))`, computed
  after subtracting the minimum loss for numerical stability.

Both use a seeded local random generator. The default constant learning rate is
`sqrt(2 * log(K)/T)` for known horizon T and K actions, with eta=1 for a single
choice or empty trace. This shared comparison convention is not a claim that the
FTPL constant is optimal. `replay_baseline` also accepts an explicit learning rate.
Reported regret is for sampled actions, not expected strategy payoffs, so a single
seed should not be treated as a statistical assessment.

**Offline fixed-trace replay is different from live interaction.** Each candidate
faces exactly the same recorded or generated trace, with no counterfactual
response from the opponent. This includes replaying traces originally produced
by adaptive opponents. Live opponents can change their future behavior when a
candidate changes its actions; testing that requires separate live sessions.
External regret still conditions on observed opponent actions and is not the
causal value of having changed the whole interaction policy.

## Extending the framework

`arena.metrics.external_regret.FiniteActionGame` holds ordered action sets and a
pure payoff callback from one player's perspective; the mathematical core has no
game imports. `external_regret` costs O(TK + KM) for K own and M opponent actions,
with O(T + K + KM) storage including the returned curve and matrix.
`MatrixRegretExtension` supplies conservative history validation for the three
symmetric two-player games. Its optional hook is merged by `MatchEvaluator`;
ordinary extensions inherit a hook that returns None. Registry discovery skips
abstract helper classes. Future asymmetric or multi-player adapters can use the
same core with a suitable opponent profile encoding and perspective-specific
payoff function, but must define and validate those counterfactuals explicitly.

Relevant tests:

```bash
uv run pytest backend/tests/test_external_regret*.py backend/tests/test_regret_baselines.py
uv run pytest games/games/core/rock_paper_scissors games/games/core/prisonersdilemma \
  games/games/core/stag_hunt
```
