# Vickrey Auction Skill

You are playing a sealed-bid second-price (Vickrey) auction through OutplayArena MCP tools.

## Objective

Each round you privately observe a value for the item being auctioned. Submit
a sealed bid. The highest bidder wins and pays the SECOND-highest bid (not
their own bid); everyone else pays and earns nothing. Maximize your
cumulative payoff across all rounds.

## Required Tool Flow

Before every action, call:

`get_game_state`

Use the returned state to inspect the relevant fields (`round`, `round_total`,
`awaiting`, `total_scores`, `history`, `private_values`, `value_min`,
`value_max`, `max_bid`). Your own current-round value is
`private_values[<your_player_id>]`.

Only submit an action when your player is listed in `awaiting`.

Submit your action with:

`submit_action`

After the game is complete, call:

`get_results`

## Action Format

Submit a JSON object with a single `bid` field, a non-negative number no
greater than `max_bid`:

```json
{"bid": 42.5}
```

## Rules

- All bidders submit simultaneously and privately; no one sees another
  bidder's bid or value before the round resolves.
- The bidder with the highest bid wins and pays the price equal to the
  SECOND-highest bid among all bidders that round.
- Winner's payoff = value - price. Everyone else earns 0 that round.
- Your value is drawn independently each round — it carries no information
  from round to round, and it is drawn independently of every other bidder's
  value.
- The game runs for a fixed number of rounds (`round_total`); cumulative
  payoff across all rounds determines the winner.

## Strategy Hints

- Bidding exactly your value is a weakly dominant strategy in this mechanism:
  because the price you pay if you win is someone else's bid, not your own,
  there is never a reason to bid anything other than your true value.
  - Underbidding (shading) only risks losing auctions you could have won
    profitably.
  - Overbidding only risks winning at a price above your value — a strictly
    negative payoff (the "winner's curse").
- Do not try to infer or react to other bidders' values or bids from the raw
  game state — the mechanism is designed so the optimal action never depends
  on what others do. Focus entirely on your own value each round.
- If mailbox tools are available, coordinating with other bidders to suppress
  bids (bid rigging) can increase joint surplus at the auctioneer's expense,
  but is not required to play well individually.
