import { useEffect, useState } from "react";
import { listKeys, createKey, deleteKey, disableKey, enableKey } from "../api";
import { copyToClipboard } from "../components/utils";
import { LoadingSpinner } from "../components/LoadingSpinner";
import type { ApiKeyRow, ApiKeyCreatedResponse } from "../types";

const inputClass =
  "min-h-[40px] text-ink bg-surface-container border rounded-input px-3 text-sm outline-none hover:border-accent/40 focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)] border-line/40";

export function KeysPage() {
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [keyName, setKeyName] = useState("");
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const [lastCreated, setLastCreated] = useState<ApiKeyCreatedResponse | null>(null);

  const fetchKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listKeys();
      setKeys(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await listKeys();
        if (!cancelled) setKeys(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdding(true);
    try {
      const created = await createKey(keyName.trim() || undefined);
      setKeyName("");
      setLastCreated(created);
      await fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (keyId: string) => {
    setDeleting(keyId);
    try {
      await deleteKey(keyId);
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeleting(null);
    }
  };

  const handleDisable = async (keyId: string) => {
    setToggling(keyId);
    try {
      await disableKey(keyId);
      setKeys((prev) => prev.map((k) => (k.id === keyId ? { ...k, is_active: false } : k)));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setToggling(null);
    }
  };

  const handleEnable = async (keyId: string) => {
    setToggling(keyId);
    try {
      await enableKey(keyId);
      setKeys((prev) => prev.map((k) => (k.id === keyId ? { ...k, is_active: true } : k)));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setToggling(null);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-black text-ink tracking-tight mb-1">API Keys</h1>
        <p className="text-sm text-muted">
          Generate API keys for programmatic REST API access — manage sessions, query results, and configure games.
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-chip border border-red-500/20 bg-red-500/5 text-xs text-red-500">
          {error}
        </div>
      )}

      {lastCreated && (
        <div className="mb-6 p-4 rounded-card border border-accent/30 bg-accent/5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-extrabold text-ink">Key Created</h3>
            <button
              type="button"
              onClick={() => setLastCreated(null)}
              className="text-xs text-muted hover:text-ink"
            >
              Dismiss
            </button>
          </div>
          <p className="text-xs text-muted mb-2">
            Save this key now — it won't be shown again.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-[11px] bg-ink/6 px-2 py-1.5 rounded text-ink break-all font-mono">
              {lastCreated.full_key}
            </code>
            <button
              type="button"
              onClick={() => copyToClipboard(lastCreated.full_key)}
              title="Copy key"
              className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:text-accent hover:bg-accent/[0.12] cursor-pointer transition-colors shrink-0"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleAdd} className="mb-8 p-5 rounded-card border border-line/40 bg-surface/50">
        <div className="grid gap-3">
          <div className="grid gap-1">
            <label className="text-[11px] font-extrabold text-muted uppercase">Key Name (optional)</label>
            <input
              type="text"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              className={inputClass}
              placeholder="e.g. CI/CD Pipeline"
            />
          </div>
          <button
            type="submit"
            disabled={adding}
            className="min-h-[42px] bg-accent border-accent text-white rounded-input px-6 font-extrabold text-sm shadow-elevation-2 transition-[transform,background,box-shadow] duration-150 hover:not-disabled:-translate-y-px hover:not-disabled:shadow-elevation-3 active:not-disabled:translate-y-0.5 disabled:cursor-not-allowed disabled:bg-line/50 disabled:border-line/50 disabled:text-quiet disabled:shadow-none"
          >
            {adding ? "Generating..." : "Generate Key"}
          </button>
        </div>
      </form>

      <div>
        <h2 className="text-sm font-extrabold text-ink mb-3">Keys</h2>
        {loading ? (
          <LoadingSpinner />
        ) : keys.length === 0 ? (
          <p className="text-sm text-muted">No API keys generated yet.</p>
        ) : (
          <div className="rounded-card border border-line/40 overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line/40 bg-surface-container/50">
                  <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Prefix</th>
                  <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Name</th>
                  <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Status</th>
                  <th className="px-4 py-2.5 text-[11px] font-extrabold text-muted">Created</th>
                  <th className="px-3 py-2.5 w-0" />
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id} className={`border-b border-line/20 last:border-b-0 group ${!k.is_active ? "opacity-50" : ""}`}>
                    <td className="px-4 py-2.5 text-xs text-muted font-mono">
                      {k.key_prefix}...
                    </td>
                    <td className="px-4 py-2.5 text-xs text-ink font-medium">
                      {k.name || "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-[11px] font-extrabold px-2 py-0.5 rounded-chip ${k.is_active ? "text-green-600 bg-green-600/10" : "text-muted bg-ink/6"}`}>
                        {k.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted whitespace-nowrap">
                      {k.created_at ? new Date(k.created_at).toLocaleDateString() : "-"}
                    </td>
                    <td className="px-2 py-2.5">
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        {k.is_active ? (
                          <button
                            type="button"
                            onClick={() => handleDisable(k.id)}
                            disabled={toggling === k.id}
                            title="Disable"
                            className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:text-amber-500 hover:bg-amber-500/15 cursor-pointer transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            {toggling === k.id ? (
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
                                <circle cx="12" cy="12" r="10" strokeDasharray="31.4" strokeDashoffset="10" />
                              </svg>
                            ) : (
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10" />
                                <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
                              </svg>
                            )}
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleEnable(k.id)}
                            disabled={toggling === k.id}
                            title="Enable"
                            className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:text-green-500 hover:bg-green-500/15 cursor-pointer transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            {toggling === k.id ? (
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
                                <circle cx="12" cy="12" r="10" strokeDasharray="31.4" strokeDashoffset="10" />
                              </svg>
                            ) : (
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                            )}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDelete(k.id)}
                          disabled={deleting === k.id}
                          title="Delete"
                          className="w-7 h-7 flex items-center justify-center rounded-md text-muted hover:text-red-500 hover:bg-red-500/15 cursor-pointer transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          {deleting === k.id ? (
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
                              <circle cx="12" cy="12" r="10" strokeDasharray="31.4" strokeDashoffset="10" />
                            </svg>
                          ) : (
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <line x1="18" y1="6" x2="6" y2="18" />
                              <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
