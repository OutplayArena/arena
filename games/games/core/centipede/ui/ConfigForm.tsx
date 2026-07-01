import { useRef } from "react";
import { useGameConfig } from "@frontend/hooks/useGameConfig";
import { LobbyConfigShell } from "@frontend/components/LobbyConfigShell";
import { inputClass } from "@frontend/components/formStyles";

interface Props {
  gameSlug: string;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
}

export default function CentipedeConfigForm({ gameSlug, locked, sessionStatus, initialValues }: Props) {
  const maxStepsRef = useRef<HTMLInputElement>(null);
  const potARef = useRef<HTMLInputElement>(null);
  const potBRef = useRef<HTMLInputElement>(null);
  const growthRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);

  const { players, setPlayers, agents, remoteKeys,
    status, running, isReplay, formDisabled, handleStartGame } =
    useGameConfig({ gameSlug, locked, sessionStatus, initialValues,
      defaultAgents: ["interactive", "remote"] });

  const onSubmit = (e: React.FormEvent) =>
    handleStartGame(e, () => ({
      max_steps: Number(maxStepsRef.current?.value ?? 6),
      initial_pot_a: Number(potARef.current?.value ?? 4),
      initial_pot_b: Number(potBRef.current?.value ?? 1),
      growth_factor: Number(growthRef.current?.value ?? 2),
      seed: seedRef.current?.value ? Number(seedRef.current.value) : null,
    }));

  return (
    <LobbyConfigShell
      players={players} onPlayersChange={setPlayers}
      agents={agents} remoteKeys={remoteKeys}
      onStartGame={onSubmit}
      disabled={formDisabled} running={running}
      isReplay={isReplay} locked={locked} status={status}
    >
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Max Steps
        <input ref={maxStepsRef} type="number" min={2} max={20} defaultValue={6} className={inputClass} disabled={formDisabled} />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Initial Pot A
          <input ref={potARef} type="number" step="1" min={1} defaultValue={4} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Initial Pot B
          <input ref={potBRef} type="number" step="1" min={1} defaultValue={1} className={inputClass} disabled={formDisabled} />
        </label>
      </div>
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Growth Factor
        <input ref={growthRef} type="number" step="0.5" min={1} defaultValue={2} className={inputClass} disabled={formDisabled} />
      </label>
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Seed (optional)
        <input ref={seedRef} type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
      </label>
    </LobbyConfigShell>
  );
}
