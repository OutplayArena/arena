import { useEffect, useState } from "react";
import { listOpenMatches, joinMatch } from "../api";
import type { LobbyMatchSummary } from "../types";

export function LobbyPage() {
  const [matches, setMatches] = useState<LobbyMatchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [joining, setJoining] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await listOpenMatches();
        if (!cancelled) {
          setMatches(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load lobby");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleJoin(matchId: string) {
    setJoining(matchId);
    setError(null);
    try {
      const result = await joinMatch(matchId);
      if (result.session_id) {
        window.location.assign(`/play/colonelblotto/${result.session_id}`);
      } else {
        setError("Joined but match not yet full — waiting for more players.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to join match");
    } finally {
      setJoining(null);
    }
  }

  if (loading) {
    return (
      <div className="flex-1 px-6 py-10">
        <p className="text-sm text-muted">Loading lobby…</p>
      </div>
    );
  }

  return (
    <div className="flex-1 px-6 py-8 max-w-4xl mx-auto w-full">
      <h1 className="text-xl font-bold text-ink mb-1">Lobby</h1>
      <p className="text-xs text-muted mb-6">
        Open matches waiting for opponents. Join one to start playing.
      </p>

      {error && (
        <div className="mb-4 p-3 rounded-[var(--radius-card)] border border-danger/30 bg-danger/5 text-sm text-danger">
          {error}
        </div>
      )}

      {matches.length === 0 ? (
        <div className="border border-line rounded-[var(--radius-card)] p-8 text-center">
          <p className="text-sm text-muted">
            No open matches right now. Create one from the dashboard to invite
            an opponent.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {matches.map((m) => (
            <div
              key={m.id}
              className="border border-line rounded-[var(--radius-card)] p-4 bg-surface flex items-center justify-between"
            >
              <div>
                <p className="text-sm font-semibold text-ink">
                  {m.game_type}
                </p>
                <p className="text-xs text-muted mt-0.5">
                  Host: {m.host_name || "Unknown"} ·{" "}
                  {m.filled_slots}/{m.total_slots} slots filled
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleJoin(m.id)}
                disabled={joining === m.id || m.open_slots === 0}
                className="h-8 px-4 rounded-[var(--radius-button)] bg-accent text-white text-xs font-semibold disabled:opacity-50"
              >
                {joining === m.id ? "Joining…" : "Join"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}