import { NavLink } from "react-router-dom";
import type { WandbLoggingState, WandbLoggingSetters } from "../hooks/useWandbLoggingConfig";

const inputClass =
  "h-8 text-ink bg-surface border border-line rounded-[var(--radius-input)] px-2.5 text-xs outline-none transition-colors " +
  "hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_2px_var(--color-accent-soft)] " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

const selectClass = inputClass + " cursor-pointer";

interface WandbLoggingSectionProps extends WandbLoggingState, WandbLoggingSetters {
  disabled?: boolean;
}

export function WandbLoggingSection({
  enabled,
  setEnabled,
  entity,
  setEntity,
  project,
  setProject,
  runName,
  setRunName,
  availableEntities,
  keyConfigured,
  entitiesLoading,
  disabled = false,
}: WandbLoggingSectionProps) {
  const fieldDisabled = disabled || !enabled || !keyConfigured;

  return (
    <section>
      <h2 className="text-[10px] font-extrabold text-muted uppercase tracking-widest mb-3 flex items-center gap-2">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
        Logging
      </h2>

      <div className="rounded-[var(--radius-card)] border border-line bg-surface-soft p-3 space-y-3">
        {/* Enable toggle */}
        <label className="flex items-center gap-2.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={enabled && keyConfigured}
            disabled={disabled || !keyConfigured}
            onChange={(e) => setEnabled(e.target.checked)}
            className="rounded accent-accent disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <span className={`text-xs font-semibold ${keyConfigured ? "text-ink" : "text-muted"}`}>
            Log results to Weights &amp; Biases
          </span>
        </label>

        {/* No key hint */}
        {!keyConfigured && (
          <p className="text-[11px] text-muted">
            Add a W&amp;B API key in{" "}
            <NavLink to="/settings" className="text-accent hover:underline">
              Settings
            </NavLink>{" "}
            to enable logging.
          </p>
        )}

        {/* Config fields — shown when enabled and key configured */}
        {keyConfigured && enabled && (
          <div className="space-y-2.5 pt-0.5">
            {/* Entity */}
            <div className="grid gap-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-wider">
                Entity
              </label>
              {availableEntities.length > 0 ? (
                <select
                  value={entity}
                  onChange={(e) => setEntity(e.target.value)}
                  disabled={fieldDisabled || entitiesLoading}
                  className={selectClass + " w-full"}
                >
                  {availableEntities.map((e) => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={entity}
                  onChange={(e) => setEntity(e.target.value)}
                  disabled={fieldDisabled}
                  placeholder={entitiesLoading ? "Loading…" : "your-username"}
                  className={inputClass + " w-full"}
                />
              )}
            </div>

            {/* Project */}
            <div className="grid gap-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-wider">
                Project
              </label>
              <input
                type="text"
                value={project}
                onChange={(e) => setProject(e.target.value)}
                disabled={fieldDisabled}
                placeholder="outplayarena"
                className={inputClass + " w-full"}
              />
            </div>

            {/* Run name */}
            <div className="grid gap-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-wider">
                Run name
              </label>
              <input
                type="text"
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
                disabled={fieldDisabled}
                placeholder="auto: session id"
                className={inputClass + " w-full"}
              />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
