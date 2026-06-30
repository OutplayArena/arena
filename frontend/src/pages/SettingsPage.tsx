import { useEffect, useState } from "react";
import { getWandbKeyStatus, saveWandbKey, deleteWandbKey } from "../api";

const inputClass =
  "h-9 text-ink bg-surface border border-line rounded-[var(--radius-input)] px-3 text-sm outline-none transition-colors " +
  "hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)]";

function SpinIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="animate-spin">
      <circle cx="12" cy="12" r="10" strokeDasharray="31.4" strokeDashoffset="10" />
    </svg>
  );
}

export function SettingsPage() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getWandbKeyStatus()
      .then((s) => { setConfigured(s.configured); setUpdatedAt(s.updated_at); })
      .catch(() => setConfigured(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await saveWandbKey(apiKey.trim());
      setConfigured(true);
      setUpdatedAt(new Date().toISOString());
      setApiKey("");
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    setRemoving(true);
    setError(null);
    try {
      await deleteWandbKey();
      setConfigured(false);
      setUpdatedAt(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRemoving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-ink tracking-tight">Settings</h1>
        <p className="text-xs text-muted mt-1 max-w-md">
          Configure integrations and platform preferences.
        </p>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2.5 rounded-[var(--radius-chip)] border border-danger/20 bg-danger/5 text-xs text-danger">
          {error}
        </div>
      )}

      {/* W&B integration */}
      <div className="rounded-[var(--radius-card)] border border-line bg-surface overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-line/60 bg-surface-soft flex items-center gap-3">
          <span className="text-sm font-bold text-ink">Weights &amp; Biases</span>
          {configured === true && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-[var(--radius-chip)] text-success bg-success/10">
              Connected
            </span>
          )}
          {configured === false && (
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-[var(--radius-chip)] text-muted bg-surface-container">
              Not configured
            </span>
          )}
        </div>

        <div className="p-5 space-y-4">
          <p className="text-xs text-muted leading-relaxed">
            Log experiment results to your own W&amp;B account. Your API key is encrypted
            at rest and never returned by the platform — it is only used when transmitting
            results at the end of a game.
          </p>

          {configured && updatedAt && (
            <p className="text-[11px] text-quiet">
              Last updated: {new Date(updatedAt).toLocaleString()}
            </p>
          )}

          {saved && (
            <div className="px-3 py-2 rounded-[var(--radius-chip)] border border-success/20 bg-success/5 text-xs text-success">
              Key saved — logging is now enabled for new experiments.
            </div>
          )}

          <form onSubmit={handleSave} className="space-y-3">
            <label className="block text-xs font-semibold text-ink">
              {configured ? "Replace API key" : "API key"}
            </label>
            <div className="flex gap-2.5">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className={`${inputClass} flex-1`}
                placeholder="Paste your W&B API key…"
                autoComplete="off"
              />
              <button
                type="submit"
                disabled={saving || !apiKey.trim()}
                className="h-9 px-4 bg-accent text-white rounded-[var(--radius-button)] font-medium text-sm transition-opacity hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
              >
                {saving && <SpinIcon />}
                {configured ? "Replace" : "Save"}
              </button>
            </div>
            <p className="text-[11px] text-quiet">
              Find your key at{" "}
              <a
                href="https://wandb.ai/authorize"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                wandb.ai/authorize
              </a>
            </p>
          </form>

          {configured && (
            <div className="pt-2 border-t border-line/40">
              <button
                type="button"
                onClick={handleRemove}
                disabled={removing}
                className="flex items-center gap-1.5 text-xs text-muted hover:text-danger transition-colors disabled:opacity-50"
              >
                {removing ? <SpinIcon /> : (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                )}
                Remove key
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
