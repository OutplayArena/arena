import { memo, useCallback } from "react";

interface Tab {
  id: string;
  label: string;
}

interface TabBarProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

export const TabBar = memo(function TabBar({ tabs, activeTab, onTabChange }: TabBarProps) {
  const handleKeyDown = useCallback((e: React.KeyboardEvent, tabId: string) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const idx = tabs.findIndex((t) => t.id === tabId);
      const next = e.key === "ArrowRight"
        ? (idx + 1) % tabs.length
        : (idx - 1 + tabs.length) % tabs.length;
      onTabChange(tabs[next].id);
      (e.currentTarget.parentElement?.children[next] as HTMLElement)?.focus();
    }
  }, [tabs, onTabChange]);

  return (
    <nav className="flex border-b border-line shrink-0" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.id}
          aria-controls={`tabpanel-${tab.id}`}
          tabIndex={activeTab === tab.id ? 0 : -1}
          onClick={() => onTabChange(tab.id)}
          onKeyDown={(e) => handleKeyDown(e, tab.id)}
          className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === tab.id
              ? "border-accent text-ink"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
});
