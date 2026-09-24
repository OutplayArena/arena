interface Tab {
  id: string;
  label: string;
}

interface TabBarProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
}

export function TabBar({ tabs, activeTab, onTabChange }: TabBarProps) {
  return (
    <nav className="flex border-b border-line/40 shrink-0 bg-surface-container/10" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`px-5 py-2.5 text-sm font-bold transition-colors border-b-2 -mb-[1px] ${
            activeTab === tab.id
              ? "border-accent text-accent"
              : "border-transparent text-muted hover:text-ink hover:border-line/30"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
