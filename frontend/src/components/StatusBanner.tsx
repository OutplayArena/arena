import { useApp } from "../hooks/useApp";

export function StatusBanner() {
  const { state } = useApp();
  return (
    <div className="absolute top-[18px] left-1/2 w-[min(760px,calc(100%-36px))] -translate-x-1/2 px-[14px] py-[10px] text-ink bg-surface/93 border rounded-chip text-center font-mono text-xs font-extrabold shadow-elevation-4 backdrop-blur-xl border-line/40">
      {state.status}
    </div>
  );
}
