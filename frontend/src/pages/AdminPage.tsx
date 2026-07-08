import { useCallback, useEffect, useState } from "react";
import {
  getAdminStats,
  getAdminSettings,
  updateAdminSettings,
} from "../api";
import type { AdminSettings, AdminStatsResponse } from "../types";

export function AdminPage() {
  const [stats, setStats] = useState<AdminStatsResponse | null>(null);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, c] = await Promise.all([getAdminStats(), getAdminSettings()]);
      setStats(s);
      setSettings(c);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [s, c] = await Promise.all([getAdminStats(), getAdminSettings()]);
        if (!cancelled) {
          setStats(s);
          setSettings(c);
          setError(null);
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Failed to load admin data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function saveSetting<K extends keyof AdminSettings>(
    key: K,
    value: AdminSettings[K],
  ) {
    try {
      await updateAdminSettings({ [key]: value } as Partial<AdminSettings>);
      setSettings((prev) => (prev ? { ...prev, [key]: value } : prev));
    } catch (e) {
      setError(e instanceof Error ? e.message : `Failed to update ${key}`);
      void reload();
    }
  }

  if (loading) {
    return (
      <div className="flex-1 px-6 py-10">
        <p className="text-sm text-muted">Loading admin dashboard…</p>
      </div>
    );
  }

  if (error || !stats || !settings) {
    return (
      <div className="flex-1 px-6 py-10">
        <p className="text-sm text-danger">{error ?? "No admin data available."}</p>
        <button
          type="button"
          onClick={() => void reload()}
          className="mt-3 h-8 px-3 rounded-[var(--radius-button)] bg-accent text-white text-xs font-semibold"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 px-6 py-8 max-w-5xl mx-auto w-full">
      <h1 className="text-xl font-bold text-ink mb-1">Admin dashboard</h1>
      <p className="text-xs text-muted mb-6">
        Platform-wide telemetry and runtime controls. Source of truth is the backend
        <code className="mx-1">platform_settings</code> table.
      </p>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <Stat label="Running" value={stats.sessions_running} />
        <Stat label="Ready" value={stats.sessions_ready} />
        <Stat label="Queued" value={stats.sessions_queued} />
        <Stat label="Failed" value={stats.sessions_failed} />
        <Stat label="W&B users" value={stats.wandb_users} />
        <Stat label="DB size" value={formatBytes(stats.db_size_bytes)} />
        <Stat label="Backup" value={stats.backup.status} muted />
        <Stat label="Login" value={stats.login_enabled ? "enabled" : "disabled"} muted />
      </div>

      {/* Runtime controls */}
      <section className="border border-line rounded-[var(--radius-card)] p-5 bg-surface">
        <h2 className="text-sm font-semibold text-ink mb-4">Platform controls</h2>

        <ControlRow label="Max concurrent sessions (global)">
          <NumberInput
            key={settings.max_concurrent_sessions}
            value={settings.max_concurrent_sessions}
            onCommit={(v) => void saveSetting("max_concurrent_sessions", v)}
          />
        </ControlRow>

        <ControlRow label="Max concurrent sessions per user">
          <NumberInput
            key={settings.max_concurrent_sessions_per_user}
            value={settings.max_concurrent_sessions_per_user}
            onCommit={(v) => void saveSetting("max_concurrent_sessions_per_user", v)}
          />
        </ControlRow>

        <ControlRow label="Allow new logins">
          <Toggle
            checked={settings.login_enabled}
            onChange={(v) => void saveSetting("login_enabled", v)}
          />
        </ControlRow>
      </section>

      <p className="mt-4 text-xs text-muted">
        Tip: the concurrency caps are read by the admission gate at session-creation
        time (#117). The login toggle rejects new OAuth login redirects with 403.
      </p>
    </div>
  );
}

function Stat({
  label,
  value,
  muted,
}: {
  label: string;
  value: number | string;
  muted?: boolean;
}) {
  return (
    <div className="border border-line rounded-[var(--radius-card)] p-4 bg-surface">
      <p className="text-xs text-muted mb-1">{label}</p>
      <p className={"text-lg font-semibold " + (muted ? "text-muted" : "text-ink")}>
        {value}
      </p>
    </div>
  );
}

function ControlRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-line last:border-b-0">
      <span className="text-sm text-ink">{label}</span>
      {children}
    </div>
  );
}

function NumberInput({
  value,
  onCommit,
}: {
  value: number;
  onCommit: (v: number) => void;
}) {
  const [draft, setDraft] = useState(value);
  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        min={1}
        value={draft}
        onChange={(e) => setDraft(Number(e.target.value))}
        className="h-8 w-24 text-sm text-ink bg-surface border border-line rounded-[var(--radius-input)] px-2 outline-none focus:border-accent"
      />
      <button
        type="button"
        onClick={() => draft !== value && onCommit(draft)}
        className="h-8 px-3 rounded-[var(--radius-button)] bg-accent text-white text-xs font-semibold disabled:opacity-50"
        disabled={draft === value}
      >
        Save
      </button>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={
        "w-10 h-6 rounded-full transition-colors " +
        (checked ? "bg-accent" : "bg-surface-container")
      }
    >
      <span
        className={
          "block w-5 h-5 bg-white rounded-full shadow transition-transform " +
          (checked ? "translate-x-4" : "translate-x-0.5")
        }
      />
    </button>
  );
}

function formatBytes(bytes: number | string): string {
  if (typeof bytes === "string") return bytes;
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}