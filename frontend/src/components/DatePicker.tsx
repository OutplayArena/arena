import { useEffect, useRef, useState } from "react";
import { formatYMD, parseYMD } from "./dateShared";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const DAY_LABELS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

const TRIGGER_CLS =
  "inline-flex items-center gap-1.5 h-9 px-3 text-sm font-mono rounded-[var(--radius-input)] border border-line bg-surface text-ink outline-none transition-colors " +
  "hover:border-line-strong focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)] cursor-pointer";

const ICON_CLS = "text-ink/65 dark:text-ink/70";

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function shiftMonth(d: Date, delta: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + delta, 1);
}

function buildMonthGrid(viewMonth: Date): Array<Date | null> {
  const first = startOfMonth(viewMonth);
  const startWeekday = first.getDay(); // 0 (Sun) - 6 (Sat)
  const daysInMonth = new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 0).getDate();
  const cells: Array<Date | null> = [];
  for (let i = 0; i < startWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push(new Date(viewMonth.getFullYear(), viewMonth.getMonth(), d));
  }
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

export interface DatePickerProps {
  /** Selected date in YYYY-MM-DD format, or empty string for no selection. */
  value: string;
  onChange: (next: string) => void;
  /** Optional earliest allowed date (YYYY-MM-DD). */
  minDate?: string;
  /** Optional latest allowed date (YYYY-MM-DD). */
  maxDate?: string;
  /** Test id and label for accessibility. */
  label: string;
  testId?: string;
  /** Optional placeholder shown when no date is set. */
  placeholder?: string;
  /** When true, show a small × button inside the trigger to clear the value. */
  clearable?: boolean;
  /** Alignment of the calendar popover relative to the trigger. */
  align?: "start" | "end";
  /**
   * When true, the trigger is non-interactive (greyed out, no popup,
   * no clear). Use when the picker has no meaningful range to operate
   * on (e.g. the underlying dataset is empty).
   */
  disabled?: boolean;
}

export function DatePicker({
  value,
  onChange,
  minDate,
  maxDate,
  label,
  testId,
  placeholder = "any",
  clearable = true,
  align = "start",
  disabled = false,
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const buttonId = `datepicker-${label.replace(/[^a-z0-9]/gi, "-").toLowerCase()}`;

  // The calendar opens to the month of the current value, or minDate, or today.
  const selected = parseYMD(value);
  const initialMonth = selected ?? parseYMD(minDate ?? "") ?? new Date();
  const [viewMonth, setViewMonth] = useState<Date>(startOfMonth(initialMonth));

  // If the value changes externally while the popover is closed, re-center.
  // Only re-center when the value string changes — depending on `selected`
  // (a fresh Date object every render) would cause an infinite loop.
  useEffect(() => {
    if (open) return;
    if (value) {
      const v = parseYMD(value);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (v) setViewMonth(startOfMonth(v));
    }
  }, [value, open]);

  // Click outside to close.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Derived flag: the popup is only visible when `open` is true AND the
  // picker is not disabled. Computing this from `open` (rather than
  // mirroring `open -> false` in a useEffect when `disabled` flips) avoids
  // a cascading render that the react-hooks/set-state-in-effect rule
  // forbids, and also keeps `aria-expanded` truthful.
  const isOpen = open && !disabled;

  const minDateObj = minDate ? parseYMD(minDate) : null;
  const maxDateObj = maxDate ? parseYMD(maxDate) : null;

  const isDisabled = (d: Date): boolean => {
    if (minDateObj && d < minDateObj) return true;
    if (maxDateObj && d > maxDateObj) return true;
    return false;
  };

  const handleSelect = (d: Date) => {
    if (isDisabled(d)) return;
    onChange(formatYMD(d));
    setOpen(false);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange("");
  };

  const cells = buildMonthGrid(viewMonth);
  const today = new Date();

  return (
    <div className="relative inline-block" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        id={buttonId}
        data-testid={testId}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        disabled={disabled}
        onClick={() => { if (!disabled) setOpen((o) => !o); }}
        className={
          TRIGGER_CLS +
          (disabled
            ? " opacity-50 cursor-not-allowed hover:border-line focus:border-line focus:shadow-none"
            : "")
        }
      >
        {value ? (
          <span className="text-ink">{value}</span>
        ) : (
          <span className="text-muted">{placeholder}</span>
        )}
        {clearable && value && (
          <span
            role="button"
            tabIndex={-1}
            aria-label={`Clear ${label} date`}
            data-testid={testId ? `${testId}-clear` : undefined}
            onClick={handleClear}
            className="ml-0.5 -mr-1 w-4 h-4 flex items-center justify-center rounded text-ink/65 hover:text-ink hover:bg-surface-container dark:text-ink/70"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="6" y1="6" x2="18" y2="18" />
              <line x1="6" y1="18" x2="18" y2="6" />
            </svg>
          </span>
        )}
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={ICON_CLS}
          aria-hidden="true"
        >
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      </button>

      {isOpen && (
        <div
          role="dialog"
          aria-label={`${label} date picker`}
          data-testid={testId ? `${testId}-popup` : undefined}
          className={`absolute z-40 top-full mt-1.5 w-[260px] rounded-[var(--radius-card)] border border-line bg-surface shadow-elevation-4 p-3 ${align === "end" ? "right-0" : "left-0"}`}
        >
          {/* Month / year nav */}
          <div className="flex items-center justify-between mb-2">
            <button
              type="button"
              onClick={() => setViewMonth((d) => shiftMonth(d, -1))}
              className="w-7 h-7 flex items-center justify-center rounded-[var(--radius-chip)] text-ink/65 hover:text-ink hover:bg-surface-container dark:text-ink/70 transition-colors"
              aria-label="Previous month"
              data-testid={testId ? `${testId}-prev` : undefined}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
            <span className="text-xs font-mono font-semibold text-ink">
              {MONTH_NAMES[viewMonth.getMonth()]} {viewMonth.getFullYear()}
            </span>
            <button
              type="button"
              onClick={() => setViewMonth((d) => shiftMonth(d, 1))}
              className="w-7 h-7 flex items-center justify-center rounded-[var(--radius-chip)] text-ink/65 hover:text-ink hover:bg-surface-container dark:text-ink/70 transition-colors"
              aria-label="Next month"
              data-testid={testId ? `${testId}-next` : undefined}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </button>
          </div>

          {/* Day-of-week header */}
          <div className="grid grid-cols-7 mb-1">
            {DAY_LABELS.map((d) => (
              <div key={d} className="text-[10px] font-mono text-muted text-center py-1">{d}</div>
            ))}
          </div>

          {/* Day cells */}
          <div className="grid grid-cols-7 gap-0.5">
            {cells.map((d, i) => {
              if (!d) return <div key={i} />;
              const disabled = isDisabled(d);
              const isSelected = selected ? isSameDay(d, selected) : false;
              const isToday = isSameDay(d, today);
              const classes = [
                "h-7 w-7 mx-auto flex items-center justify-center rounded-[var(--radius-chip)] text-xs font-mono transition-colors",
                disabled
                  ? "text-ink/25 dark:text-ink/30 cursor-not-allowed"
                  : isSelected
                    ? "bg-accent text-white"
                    : isToday
                      ? "text-accent border border-accent/40 hover:bg-accent-soft"
                      : "text-ink hover:bg-surface-container cursor-pointer",
              ].join(" ");
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleSelect(d)}
                  disabled={disabled}
                  tabIndex={disabled ? -1 : 0}
                  aria-pressed={isSelected}
                  aria-label={d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}
                  data-testid={testId ? `${testId}-day-${formatYMD(d)}` : undefined}
                  className={classes}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>

          {/* Footer: clear + today shortcut */}
          <div className="flex items-center justify-between mt-2 pt-2 border-t border-line">
            {clearable ? (
              <button
                type="button"
                onClick={() => { onChange(""); setOpen(false); }}
                className="text-[11px] font-mono text-ink/65 hover:text-ink dark:text-ink/70 transition-colors"
                data-testid={testId ? `${testId}-popup-clear` : undefined}
              >
                Clear
              </button>
            ) : (
              <span />
            )}
            <button
              type="button"
              onClick={() => {
                const t = new Date();
                if (isDisabled(t)) {
                  setViewMonth(startOfMonth(t));
                } else {
                  handleSelect(t);
                }
              }}
              className="text-[11px] font-mono text-accent hover:underline transition-colors"
              data-testid={testId ? `${testId}-today` : undefined}
            >
              Today
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
