import { useEffect, useState } from "react";
import { getGameSkill } from "../api";

// Sections from skill.md that are relevant to a human player in the UI.
// "required_tool_flow" is agent/MCP-specific ("call get_game_state…") and
// would confuse someone clicking buttons, so we skip it.
const HUMAN_SECTIONS = ["objective", "action_format", "rules", "strategy_hints"];

const SECTION_LABELS: Record<string, string> = {
  objective: "Objective",
  action_format: "Action Format",
  rules: "Rules",
  strategy_hints: "Strategy Hints",
};

interface GameInstructionsPanelProps {
  gameSlug: string;
  collapsed: boolean;
  onToggle: () => void;
}

export function GameInstructionsPanel({ gameSlug, collapsed, onToggle }: GameInstructionsPanelProps) {
  const [sections, setSections] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getGameSkill(gameSlug)
      .then((data) => {
        if (!cancelled) {
          setSections(data.sections);
          setLoading(false);
        }
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [gameSlug]);

  return (
    <aside
      className={`shrink-0 flex flex-col border-l border-line bg-surface-soft transition-all duration-200 ${
        collapsed ? "w-8" : "w-64 lg:w-72"
      }`}
    >
      {/* Toggle rail */}
      <button
        type="button"
        onClick={onToggle}
        title={collapsed ? "Show instructions" : "Hide instructions"}
        className="w-full flex items-center gap-2 px-2 py-3 text-muted hover:text-ink hover:bg-surface-container transition-colors text-xs font-semibold border-b border-line/50"
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`shrink-0 transition-transform ${collapsed ? "" : "rotate-180"}`}
        >
          <polyline points="15 18 9 12 15 6" />
        </svg>
        {!collapsed && <span className="truncate">Instructions</span>}
      </button>

      {/* Content */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {loading ? (
            <p className="text-xs text-muted animate-pulse">Loading…</p>
          ) : Object.keys(sections).length === 0 ? (
            <p className="text-xs text-muted">No instructions available for this game.</p>
          ) : (
            HUMAN_SECTIONS.filter((key) => sections[key]).map((key) => (
              <div key={key}>
                <h3 className="text-[10px] font-extrabold text-muted uppercase tracking-widest mb-2">
                  {SECTION_LABELS[key] ?? key}
                </h3>
                <div className="text-xs text-ink leading-relaxed whitespace-pre-wrap">
                  {sections[key]}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </aside>
  );
}
