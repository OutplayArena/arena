import { useRef, useState } from "react";
import { useGameConfig } from "@frontend/hooks/useGameConfig";
import { LobbyConfigShell } from "@frontend/components/LobbyConfigShell";
import { inputClass } from "@frontend/components/formStyles";

interface Props {
  gameSlug: string;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
}

const SCENARIOS = [
  { value: "prison", label: "Prison" },
  { value: "business", label: "Business Deal" },
  { value: "climate", label: "Climate Change" },
  { value: "arms_race", label: "Arms Race" },
  { value: "roommates", label: "Roommates" },
];

export default function PDConfigForm({ gameSlug, locked, sessionStatus, initialValues }: Props) {
  const [variant, setVariant] = useState("classic");
  const [scenario, setScenario] = useState("prison");
  const roundsRef = useRef<HTMLInputElement>(null);
  const payoffTRef = useRef<HTMLInputElement>(null);
  const payoffRRef = useRef<HTMLInputElement>(null);
  const payoffPRef = useRef<HTMLInputElement>(null);
  const payoffSRef = useRef<HTMLInputElement>(null);
  const noiseRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);

  const { players, setPlayers, agents, remoteKeys,
    status, running, isReplay, formDisabled, handleStartGame } =
    useGameConfig({ gameSlug, locked, sessionStatus, initialValues,
      defaultAgents: ["interactive", "remote"] });

  const onSubmit = (e: React.FormEvent) => {
    const extra: Record<string, unknown> = {
      variant,
      scenario,
      rounds: Number(roundsRef.current?.value ?? 10),
      payoff_T: Number(payoffTRef.current?.value ?? 5),
      payoff_R: Number(payoffRRef.current?.value ?? 3),
      payoff_P: Number(payoffPRef.current?.value ?? 1),
      payoff_S: Number(payoffSRef.current?.value ?? 0),
      seed: seedRef.current?.value ? Number(seedRef.current.value) : null,
    };
    if (variant === "noisy" && noiseRef.current) {
      extra.noise = Number(noiseRef.current.value);
    }
    return handleStartGame(e, () => extra);
  };

  return (
    <LobbyConfigShell
      players={players} onPlayersChange={setPlayers}
      agents={agents} remoteKeys={remoteKeys}
      onStartGame={onSubmit}
      disabled={formDisabled} running={running}
      isReplay={isReplay} locked={locked} status={status}
    >
      <div className="grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Variant
          <select value={variant} onChange={(e) => setVariant(e.target.value)} className={inputClass} disabled={formDisabled}>
            <option value="classic">Classic</option>
            <option value="noisy">Noisy</option>
          </select>
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Scenario
          <select value={scenario} onChange={(e) => setScenario(e.target.value)} className={inputClass} disabled={formDisabled}>
            {SCENARIOS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
      </div>
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Rounds
        <input ref={roundsRef} type="number" min={1} max={100} defaultValue={10} className={inputClass} disabled={formDisabled} />
      </label>
      <div className="grid grid-cols-4 gap-2">
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          T (tempt)
          <input ref={payoffTRef} type="number" step="0.5" defaultValue={5} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          R (reward)
          <input ref={payoffRRef} type="number" step="0.5" defaultValue={3} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          P (punish)
          <input ref={payoffPRef} type="number" step="0.5" defaultValue={1} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          S (sucker)
          <input ref={payoffSRef} type="number" step="0.5" defaultValue={0} className={inputClass} disabled={formDisabled} />
        </label>
      </div>
      {variant === "noisy" && (
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Noise probability
          <input ref={noiseRef} type="number" step="0.01" min={0} max={0.5} defaultValue={0.1} className={inputClass} disabled={formDisabled} />
        </label>
      )}
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Seed (optional)
        <input ref={seedRef} type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
      </label>
    </LobbyConfigShell>
  );
}
