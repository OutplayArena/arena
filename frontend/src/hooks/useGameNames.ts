import { useEffect, useState } from "react";
import { listGames } from "../api";
import type { GameEntry } from "../types";

/**
 * Hook that returns a slug → human-readable name map for every game
 * served by `/api/games`. Falls back to an empty map (which then makes
 * consumers display the technical slug) while loading or on error.
 *
 * The result is shared per mount: every call to `useGameNames()` in the
 * same React tree uses the same in-memory cache.
 */
let cache: Map<string, string> | null = null;
let inflight: Promise<void> | null = null;
const subscribers = new Set<(m: Map<string, string>) => void>();

function notify(map: Map<string, string>) {
  for (const cb of subscribers) cb(map);
}

async function ensureLoaded() {
  if (cache) return;
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const games: GameEntry[] = await listGames();
      cache = new Map(games.map((g) => [g.slug, g.name]));
      notify(cache);
    } catch {
      // Leave cache null; consumers will fall back to the slug.
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}

/** Reset the module-level cache. Test-only — never call from app code. */
export function __resetGameNamesCache(): void {
  cache = null;
  inflight = null;
  subscribers.clear();
}

export function useGameNames(): Map<string, string> {
  const [, force] = useState(0);

  useEffect(() => {
    if (cache) return;
    const cb = () => force((n) => n + 1);
    subscribers.add(cb);
    ensureLoaded();
    return () => {
      subscribers.delete(cb);
    };
  }, []);

  return cache ?? new Map();
}

/** Synchronous lookup; returns the slug unchanged if no entry is known. */
export function gameName(slug: string | undefined, names: Map<string, string>): string {
  if (!slug) return "Overall";
  return names.get(slug) ?? slug;
}
