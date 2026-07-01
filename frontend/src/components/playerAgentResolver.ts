import type { GameAgent } from "../types";

/**
 * The frontend's player dropdown knows two fixed sentinel agent IDs that
 * every game exposes: "interactive" (a human player via the Live View)
 * and "remote" (an external LLM/MCP agent connecting with a session key).
 * Every other entry in the game's agent list (e.g. "uniform", "random",
 * "greedy" for Colonel Blotto) is a built-in bot whose `id` is registered
 * via `getGameAgents(gameSlug)`.
 *
 * The backend persists only the *display name* of each player in
 * `SessionModel.agents_json` (and the `_session_summary` exposes it as
 * `agent_a` / `agent_b`).  The dropdown `id` that produced that name is
 * NOT stored, so on replay we have to reconstruct it heuristically:
 *
 *  1. If the name is the human sentinel "You", the original id was
 *     "interactive".
 *  2. If the name matches a registered agent's `id` verbatim, use that
 *     id (some games store the id directly as the display name).
 *  3. If the name matches a registered agent's `label` (case-insensitive),
 *     use the corresponding id.
 *  4. Otherwise assume the player was an external LLM/MCP agent picked
 *     from the "remote" option, so the id is "remote".  This is the
 *     common case for sessions where the user typed an arbitrary model
 *     name (e.g. "deepseek-v4-pro") into the Display Name field after
 *     selecting "Remote Agent (LLM/MCP)" from the dropdown.
 */
export function resolveAgentId(
  displayName: string | null | undefined,
  agents: GameAgent[],
): string {
  if (!displayName) return "interactive";
  if (displayName === "You") return "interactive";
  if (agents.some((a) => a.id === displayName)) return displayName;
  const lower = displayName.toLowerCase();
  const byLabel = agents.find((a) => a.label.toLowerCase() === lower);
  if (byLabel) return byLabel.id;
  return "remote";
}
