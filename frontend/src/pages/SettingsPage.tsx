import { useEffect, useState } from "react";
import { getWandbKeyStatus, saveWandbKey, deleteWandbKey, downloadUserData, deleteAccount } from "../api";
import { useAuth } from "../hooks/useAuth";

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

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

/** Minimal confirmation modal. */
function ConfirmModal({
  title,
  message,
  confirmLabel,
  danger,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        className="bg-surface rounded-[var(--radius-card)] shadow-elevation-5 border border-line w-full max-w-sm p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-bold text-ink">{title}</h2>
        <p className="text-xs text-muted leading-relaxed">{message}</p>
        <div className="flex justify-end gap-2.5 pt-1">
          <button
            type="button"
            onClick={onCancel}
            className="h-8 px-4 rounded-[var(--radius-button)] text-xs font-semibold text-muted border border-line hover:bg-surface-container transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`h-8 px-4 rounded-[var(--radius-button)] text-xs font-semibold text-white transition-opacity hover:opacity-90 ${danger ? "bg-danger" : "bg-accent"}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { logout } = useAuth();

  // W&B state
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [keyFingerprint, setKeyFingerprint] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [wandbError, setWandbError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [open, setOpen] = useState(true);

  // GDPR state
  const [downloading, setDownloading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [gdprError, setGdprError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<"export" | "delete" | null>(null);

  useEffect(() => {
    getWandbKeyStatus()
      .then((s) => {
        setConfigured(s.configured);
        setUpdatedAt(s.updated_at);
        setKeyFingerprint(s.key_fingerprint);
      })
      .catch(() => setConfigured(false));
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setSaving(true);
    setWandbError(null);
    setSaved(false);
    try {
      await saveWandbKey(apiKey.trim());
      const s = await getWandbKeyStatus();
      setConfigured(s.configured);
      setUpdatedAt(s.updated_at);
      setKeyFingerprint(s.key_fingerprint);
      setApiKey("");
      setSaved(true);
    } catch (err) {
      setWandbError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    setRemoving(true);
    setWandbError(null);
    try {
      await deleteWandbKey();
      setConfigured(false);
      setUpdatedAt(null);
      setKeyFingerprint(null);
    } catch (err) {
      setWandbError(err instanceof Error ? err.message : String(err));
    } finally {
      setRemoving(false);
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    setGdprError(null);
    try {
      await downloadUserData();
    } catch (err) {
      setGdprError(err instanceof Error ? err.message : String(err));
    } finally {
      setDownloading(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    setGdprError(null);
    try {
      await deleteAccount();
      logout();
    } catch (err) {
      setGdprError(err instanceof Error ? err.message : String(err));
      setDeleting(false);
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

      {/* ── W&B integration ─────────────────────────────────────────── */}
      {wandbError && (
        <div className="mb-4 px-3 py-2.5 rounded-[var(--radius-chip)] border border-danger/20 bg-danger/5 text-xs text-danger">
          {wandbError}
        </div>
      )}

      <div className="w-full rounded-[var(--radius-card)] border border-line bg-surface overflow-hidden mb-6">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="w-full px-5 py-4 flex items-center gap-3 bg-surface-soft hover:bg-surface-container transition-colors text-left"
        >
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

          {configured && keyFingerprint && (
            <span className="ml-auto mr-2 font-mono text-[11px] text-quiet tracking-wide select-all">
              …{keyFingerprint}
            </span>
          )}

          <span className={`${configured && keyFingerprint ? "" : "ml-auto"} text-muted shrink-0`}>
            <ChevronIcon open={open} />
          </span>
        </button>

        <div className={`grid transition-[grid-template-rows] duration-200 ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
          <div className="overflow-hidden">
            <div className="border-t border-line/60 p-5 space-y-4">
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
      </div>

      {/* ── Danger Zone ──────────────────────────────────────────────── */}
      <div className="w-full rounded-[var(--radius-card)] border border-danger/30 bg-surface overflow-hidden shadow-[0_0_0_1px_rgba(var(--color-danger-rgb,220,38,38),0.08),0_4px_16px_rgba(var(--color-danger-rgb,220,38,38),0.06)]">
        <div className="px-5 py-4 border-b border-danger/20 bg-danger/[0.03]">
          <h2 className="text-sm font-bold text-danger">Danger Zone</h2>
        </div>

        <div className="divide-y divide-line/60">
          {/* Export data */}
          <div className="px-5 py-4 flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-ink">Export my data</p>
              <p className="text-[11px] text-muted mt-0.5">
                Download a full JSON archive of your account, game sessions, and message history.
                Sensitive credentials are redacted.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setConfirm("export")}
              disabled={downloading}
              className="shrink-0 h-8 px-3 rounded-[var(--radius-button)] text-xs font-semibold border border-line text-ink hover:bg-surface-container transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              {downloading ? <SpinIcon /> : (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
              )}
              Export
            </button>
          </div>

          {/* Delete account */}
          <div className="px-5 py-4 flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-ink">Delete my account</p>
              <p className="text-[11px] text-muted mt-0.5">
                Permanently erase your account, all game sessions, API keys, and any stored
                credentials. This cannot be undone.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setConfirm("delete")}
              disabled={deleting}
              className="shrink-0 h-8 px-3 rounded-[var(--radius-button)] text-xs font-semibold bg-danger text-white hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-1.5"
            >
              {deleting ? <SpinIcon /> : (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6" /><path d="M14 11v6" />
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                </svg>
              )}
              Delete
            </button>
          </div>
        </div>

        {gdprError && (
          <div className="mx-5 mb-4 px-3 py-2.5 rounded-[var(--radius-chip)] border border-danger/20 bg-danger/5 text-xs text-danger">
            {gdprError}
          </div>
        )}
      </div>

      {/* ── Confirmation modals ───────────────────────────────────────── */}
      {confirm === "export" && (
        <ConfirmModal
          title="Export your data?"
          message="A JSON file containing your account details, game sessions, and message history will be downloaded. Sensitive credentials (API keys, W&B key) are redacted in the export."
          confirmLabel="Download export"
          onConfirm={() => { setConfirm(null); handleDownload(); }}
          onCancel={() => setConfirm(null)}
        />
      )}

      {confirm === "delete" && (
        <ConfirmModal
          title="Delete your account?"
          message="This will permanently delete your account, all game sessions, API keys, W&B credentials, and message history. This action cannot be undone and there is no recovery option."
          confirmLabel="Yes, delete everything"
          danger
          onConfirm={() => { setConfirm(null); handleDeleteAccount(); }}
          onCancel={() => setConfirm(null)}
        />
      )}
    </div>
  );
}
