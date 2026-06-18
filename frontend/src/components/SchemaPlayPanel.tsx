import { useEffect, useRef, useState } from "react";
import { getInteractiveSchema } from "../api";
import { useInteractivePlay } from "../hooks/useInteractivePlay";
import { useApp } from "../hooks/useApp";
import { PlayScoreHeader } from "./play/PlayScoreHeader";
import { RoundResultBanner } from "./play/RoundResultBanner";

interface UiMetadata {
  input_type?: string;
  choices?: string[];
  choice_labels?: Record<string, string>;
  min?: number;
  max?: number;
  fields?: Array<{ key: string; label: string; min?: number; max?: number }>;
  budget_key?: string;
}

interface SchemaPlayPanelProps {
  onGameEnd: () => void;
}

function ChoiceButtons({
  choices,
  labels,
  onChoose,
  disabled,
}: {
  choices: string[];
  labels?: Record<string, string>;
  onChoose: (c: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-wrap justify-center gap-3 p-6">
      {choices.map((c) => (
        <button
          key={c}
          type="button"
          onClick={() => onChoose(c)}
          disabled={disabled}
          className="px-6 py-3 rounded-xl border border-line/40 bg-surface hover:bg-accent/8 hover:border-accent/50 disabled:opacity-40 disabled:cursor-not-allowed font-semibold text-sm text-ink transition-all capitalize"
        >
          {labels?.[c] ?? c}
        </button>
      ))}
    </div>
  );
}

function NumberSlider({
  min,
  max,
  onSubmit,
  disabled,
  label,
}: {
  min: number;
  max: number;
  onSubmit: (v: number) => void;
  disabled: boolean;
  label: string;
}) {
  const [value, setValue] = useState(Math.round((min + max) / 2));

  return (
    <div className="flex flex-col gap-4 p-6 max-w-sm mx-auto w-full">
      <div className="flex justify-between text-xs text-muted">
        <span>{min}</span>
        <span className="font-bold text-ink text-base tabular-nums">{value}</span>
        <span>{max}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        disabled={disabled}
        className="w-full accent-accent"
      />
      <button
        type="button"
        onClick={() => onSubmit(value)}
        disabled={disabled}
        className="w-full py-2.5 rounded-lg bg-accent text-white text-sm font-bold hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {label}
      </button>
    </div>
  );
}

function NumberInput({
  min,
  max,
  onSubmit,
  disabled,
}: {
  min?: number;
  max?: number;
  onSubmit: (v: number) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState(min ?? 0);

  return (
    <div className="flex flex-col gap-3 p-6 max-w-xs mx-auto w-full">
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => setValue(Number(e.target.value))}
        disabled={disabled}
        className="w-full px-3 py-2 rounded-lg border border-line/40 bg-surface text-ink text-center text-lg font-bold focus:outline-none focus:border-accent/60"
      />
      <button
        type="button"
        onClick={() => onSubmit(value)}
        disabled={disabled}
        className="w-full py-2.5 rounded-lg bg-accent text-white text-sm font-bold hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Submit
      </button>
    </div>
  );
}

function AllocationInputs({
  fields,
  budget,
  onSubmit,
  disabled,
}: {
  fields: Array<{ key: string; label: string; min?: number; max?: number }>;
  budget: number;
  onSubmit: (values: Record<string, number>) => void;
  disabled: boolean;
}) {
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(fields.map((f) => [f.key, 0]))
  );

  const total = Object.values(values).reduce((s, v) => s + v, 0);
  const remaining = budget - total;
  const isValid = remaining === 0;

  const set = (key: string, v: number) =>
    setValues((prev) => ({ ...prev, [key]: Math.max(0, v) }));

  return (
    <div className="flex flex-col gap-3 p-4 max-w-sm mx-auto w-full">
      <div className={`text-center text-sm font-bold tabular-nums ${remaining < 0 ? "text-red-500" : remaining === 0 ? "text-emerald-500" : "text-muted"}`}>
        Remaining: {remaining} / {budget}
      </div>
      <div className="grid gap-2">
        {fields.map((f) => (
          <div key={f.key} className="flex items-center gap-3">
            <label className="text-xs font-semibold text-muted w-28 shrink-0">{f.label}</label>
            <input
              type="number"
              value={values[f.key]}
              min={f.min ?? 0}
              max={f.max ?? budget}
              onChange={(e) => set(f.key, Number(e.target.value))}
              disabled={disabled}
              className="flex-1 px-2 py-1 rounded border border-line/40 bg-surface text-ink text-center text-sm focus:outline-none focus:border-accent/60"
            />
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => onSubmit(values)}
        disabled={disabled || !isValid}
        className="w-full py-2.5 rounded-lg bg-accent text-white text-sm font-bold hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Submit Allocation
      </button>
    </div>
  );
}

function TextFallback({
  onSubmit,
  disabled,
}: {
  onSubmit: (v: string) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState("");

  return (
    <div className="flex gap-2 p-4">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && value.trim()) { onSubmit(value.trim()); setValue(""); } }}
        disabled={disabled}
        placeholder="Enter your action..."
        className="flex-1 px-3 py-2 rounded-lg border border-line/40 bg-surface text-ink text-sm focus:outline-none focus:border-accent/60"
      />
      <button
        type="button"
        onClick={() => { if (value.trim()) { onSubmit(value.trim()); setValue(""); } }}
        disabled={disabled || !value.trim()}
        className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-bold hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {disabled ? "..." : "Submit"}
      </button>
    </div>
  );
}

export function SchemaPlayPanel({ onGameEnd }: SchemaPlayPanelProps) {
  const {
    humanPlayer, isMyTurn, isComplete, isSubmitting,
    lastRoundResult, totalScores, round, roundTotal, submitMove, currentState,
  } = useInteractivePlay();
  const { state } = useApp();
  const pg = state.pendingGame;
  const match = state.activeMatch;
  const sessionId = pg?.sessionId;

  const [uiMeta, setUiMeta] = useState<UiMetadata | null>(null);
  const [schema, setSchema] = useState<Record<string, unknown> | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const lastFetchedRound = useRef(-1);

  useEffect(() => {
    if (isComplete) onGameEnd();
  }, [isComplete, onGameEnd]);

  useEffect(() => {
    if (!sessionId || !humanPlayer || !isMyTurn) return;
    if (lastFetchedRound.current === round && uiMeta) return;
    lastFetchedRound.current = round;

    setLoadingSchema(true);
    getInteractiveSchema(sessionId, humanPlayer).then((data) => {
      setUiMeta(data.ui_metadata as UiMetadata);
      setSchema(data.schema);
    }).catch(console.error).finally(() => setLoadingSchema(false));
  }, [sessionId, humanPlayer, isMyTurn, round, uiMeta]);

  const handleSubmit = async (action: unknown) => {
    setSubmitError(null);
    try {
      await submitMove(action);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleRawText = async (raw: string) => {
    let action: unknown = raw;
    try { action = JSON.parse(raw); } catch { /* keep as string */ }
    await handleSubmit(action);
  };

  const budget = (() => {
    if (!uiMeta?.budget_key || !currentState) return 0;
    const budgets = currentState.budgets as Record<string, number> | undefined;
    if (budgets && humanPlayer) return budgets[humanPlayer] ?? 0;
    return 0;
  })();

  const renderInput = () => {
    if (!isMyTurn) {
      return (
        <div className="flex-1 flex items-center justify-center text-muted text-sm">
          Waiting for opponent to move...
        </div>
      );
    }

    if (loadingSchema || !uiMeta) {
      return (
        <div className="flex-1 flex items-center justify-center gap-2 text-muted text-sm">
          <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
          Loading game controls...
        </div>
      );
    }

    const inputType = uiMeta?.input_type;

    if (inputType === "choice" && uiMeta?.choices) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center">
          <p className="text-xs text-muted mb-4">Choose your move:</p>
          <ChoiceButtons
            choices={uiMeta.choices}
            labels={uiMeta.choice_labels}
            onChoose={(c) => handleSubmit(c)}
            disabled={isSubmitting}
          />
        </div>
      );
    }

    if ((inputType === "slider" || inputType === "number_slider") && uiMeta) {
      const props = schema?.properties as Record<string, Record<string, unknown>> | undefined;
      const firstProp = props ? Object.values(props)[0] : undefined;
      const min = uiMeta.min ?? (firstProp?.minimum as number) ?? 0;
      const max = uiMeta.max ?? (firstProp?.maximum as number) ?? 100;
      return (
        <div className="flex-1 flex items-center justify-center">
          <NumberSlider min={min} max={max} onSubmit={(v) => handleSubmit(v)} disabled={isSubmitting} label="Submit" />
        </div>
      );
    }

    if (inputType === "number" && uiMeta) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <NumberInput min={uiMeta.min} max={uiMeta.max} onSubmit={(v) => handleSubmit(v)} disabled={isSubmitting} />
        </div>
      );
    }

    if (inputType === "allocation" && uiMeta?.fields) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <AllocationInputs fields={uiMeta.fields} budget={budget} onSubmit={(v) => handleSubmit(v)} disabled={isSubmitting} />
        </div>
      );
    }

    return (
      <div className="flex-1 flex flex-col justify-end">
        <TextFallback onSubmit={handleRawText} disabled={isSubmitting} />
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-surface-soft">
      <PlayScoreHeader
        match={match}
        humanPlayer={humanPlayer}
        isMyTurn={isMyTurn}
        round={round}
        roundTotal={roundTotal}
      />

      {lastRoundResult && (
        <RoundResultBanner result={lastRoundResult} humanPlayer={humanPlayer} />
      )}

      {submitError && (
        <div className="shrink-0 mx-4 mt-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800/40 text-xs text-red-600 dark:text-red-400">
          {submitError}
        </div>
      )}

      {isComplete ? (
        <div className="flex-1 flex items-center justify-center text-center px-6">
          <div>
            <div className="text-2xl mb-2">🏁</div>
            <p className="text-sm font-bold text-ink">Game complete!</p>
            <p className="text-xs text-muted mt-1">
              Final: You {totalScores[humanPlayer ?? "A"]} — Opp {totalScores[humanPlayer === "A" ? "B" : "A"]}
            </p>
          </div>
        </div>
      ) : (
        renderInput()
      )}
    </div>
  );
}
