import { useEffect, useState } from "react";
import { listKeys, createKey, deleteKey, disableKey, enableKey } from "../api";
import { copyToClipboard } from "../components/utils";
import { LoadingSpinner } from "../components/LoadingSpinner";
import type { ApiKeyRow, ApiKeyCreatedResponse } from "../types";

const inputClass =
  "h-9 text-ink bg-surface border border-line rounded-[var(--radius-input)] px-3 text-sm outline-none transition-colors " +
  "hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)]";

function SpinIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
      <circle cx="12" cy="12" r="10" strokeDasharray="31.4" strokeDashoffset="10"/>
    </svg>
  );
}

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
    try { setKeys(await listKeys()); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
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
    } finally { setAdding(false); }
  };

  const handleDelete = async (keyId: string) => {
    setDeleting(keyId);
    try { await deleteKey(keyId); setKeys((prev) => prev.filter((k) => k.id !== keyId)); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setDeleting(null); }
  };

  const handleDisable = async (keyId: string) => {
    setToggling(keyId);
    try { await disableKey(keyId); setKeys((prev) => prev.map((k) => k.id === keyId ? { ...k, is_active: false } : k)); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setToggling(null); }
  };

  const handleEnable = async (keyId: string) => {
    setToggling(keyId);
    try { await enableKey(keyId); setKeys((prev) => prev.map((k) => k.id === keyId ? { ...k, is_active: true } : k)); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setToggling(null); }
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-ink tracking-tight">API Keys</h1>
        <p className="text-xs text-muted mt-1 max-w-md">
          Generate keys for programmatic REST API access — manage sessions, query results, and configure games.
        </p>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2.5 rounded-[var(--radius-chip)] border border-danger/20 bg-danger/5 text-xs text-danger">
          {error}
        </div>
      )}

      {/* Newly created key reveal */}
      {lastCreated && (
        <div className="mb-6 p-4 rounded-[var(--radius-card)] border border-accent/30 bg-accent-soft">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-ink">Key created — save it now, it won't be shown again.</p>
            <button type="button" onClick={() => setLastCreated(null)} className="text-xs text-muted hover:text-ink transition-colors">
              Dismiss
            </button>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <code className="flex-1 text-[11px] font-mono bg-surface border border-line px-2.5 py-1.5 rounded-[var(--radius-chip)] text-ink break-all">
              {lastCreated.full_key}
            </code>
            <button
              type="button"
              onClick={() => copyToClipboard(lastCreated.full_key)}
              title="Copy"
              className="w-8 h-8 flex items-center justify-center rounded-[var(--radius-chip)] text-muted hover:text-accent hover:bg-accent-soft transition-colors shrink-0"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Create form */}
      <form onSubmit={handleAdd} className="mb-8 p-5 rounded-[var(--radius-card)] border border-line bg-surface-soft">
        <p className="text-xs font-semibold text-ink mb-3">Create new key</p>
        <div className="flex gap-2.5">
          <input
            type="text"
            value={keyName}
            onChange={(e) => setKeyName(e.target.value)}
            className={`${inputClass} flex-1`}
            placeholder="Key name (optional)"
          />
          <button
            type="submit"
            disabled={adding}
            className="h-9 px-4 bg-accent text-white rounded-[var(--radius-button)] font-medium text-sm transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {adding ? "Generating…" : "Generate"}
          </button>
        </div>
      </form>

      {/* Keys list */}
      <div>
        <p className="text-xs font-semibold text-ink mb-3">Your keys</p>
        {loading ? (
          <div className="py-8 flex justify-center"><LoadingSpinner /></div>
        ) : keys.length === 0 ? (
          <div className="p-8 text-center rounded-[var(--radius-card)] border border-line bg-surface-soft">
            <p className="text-sm text-muted">No API keys yet.</p>
          </div>
        ) : (
          <div className="rounded-[var(--radius-card)] border border-line overflow-hidden bg-surface">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line bg-surface-soft">
                  <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Prefix</th>
                  <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Name</th>
                  <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Status</th>
                  <th className="px-4 py-2.5 text-[11px] font-mono font-medium text-muted">Created</th>
                  <th className="px-3 py-2.5 w-0" />
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id} className={`border-b border-line/50 last:border-0 group ${!k.is_active ? "opacity-50" : ""}`}>
                    <td className="px-4 py-2.5 text-xs text-muted font-mono">{k.key_prefix}…</td>
                    <td className="px-4 py-2.5 text-xs text-ink font-medium">{k.name || "—"}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-[11px] font-medium px-2 py-0.5 rounded-[var(--radius-chip)] ${k.is_active ? "text-success bg-success/10" : "text-muted bg-surface-container"}`}>
                        {k.is_active ? "Active" : "Disabled"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted whitespace-nowrap">
                      {k.created_at ? new Date(k.created_at).toLocaleDateString() : "—"}
                    </td>
                    <td className="px-2 py-2.5">
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        {k.is_active ? (
                          <button type="button" onClick={() => handleDisable(k.id)} disabled={toggling === k.id} title="Disable" className="w-7 h-7 flex items-center justify-center rounded text-muted hover:text-warning hover:bg-warning/10 transition-colors disabled:opacity-30">
                            {toggling === k.id ? <SpinIcon /> : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>}
                          </button>
                        ) : (
                          <button type="button" onClick={() => handleEnable(k.id)} disabled={toggling === k.id} title="Enable" className="w-7 h-7 flex items-center justify-center rounded text-muted hover:text-success hover:bg-success/10 transition-colors disabled:opacity-30">
                            {toggling === k.id ? <SpinIcon /> : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>}
                          </button>
                        )}
                        <button type="button" onClick={() => handleDelete(k.id)} disabled={deleting === k.id} title="Delete" className="w-7 h-7 flex items-center justify-center rounded text-muted hover:text-danger hover:bg-danger/10 transition-colors disabled:opacity-30">
                          {deleting === k.id ? <SpinIcon /> : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>}
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
