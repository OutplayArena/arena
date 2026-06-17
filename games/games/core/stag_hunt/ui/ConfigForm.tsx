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

export default function StagHuntConfigForm({ gameSlug, locked, sessionStatus, initialValues }: Props) {
  const [variant, setVariant] = useState("classic");
  const roundsRef = useRef<HTMLInputElement>(null);
  const stagStagRef = useRef<HTMLInputElement>(null);
  const hareHareRef = useRef<HTMLInputElement>(null);
  const stagHareRef = useRef<HTMLInputElement>(null);
  const noiseRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);

  const { players, setPlayers, agents, remoteKeys,
    status, running, isReplay, formDisabled, handleStartGame } =
    useGameConfig({ gameSlug, locked, sessionStatus, initialValues,
      defaultAgents: ["interactive", "remote"] });

  const onSubmit = (e: React.FormEvent) => {
    const extra: Record<string, unknown> = {
      variant,
      rounds: Number(roundsRef.current?.value ?? 10),
      payoff_stag_stag: Number(stagStagRef.current?.value ?? 4),
      payoff_hare_hare: Number(hareHareRef.current?.value ?? 2),
      payoff_stag_hare: Number(stagHareRef.current?.value ?? 0),
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
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Variant
        <select value={variant} onChange={(e) => setVariant(e.target.value)} className={inputClass} disabled={formDisabled}>
          <option value="classic">Classic</option>
          <option value="noisy">Noisy</option>
        </select>
      </label>
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Rounds
        <input ref={roundsRef} type="number" min={1} max={100} defaultValue={10} className={inputClass} disabled={formDisabled} />
      </label>
      <div className="grid grid-cols-3 gap-2">
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Stag-Stag
          <input ref={stagStagRef} type="number" step="0.5" defaultValue={4} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Hare-Hare
          <input ref={hareHareRef} type="number" step="0.5" defaultValue={2} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Stag-Hare
          <input ref={stagHareRef} type="number" step="0.5" defaultValue={0} className={inputClass} disabled={formDisabled} />
        </label>
      </div>
      {variant === "noisy" && (
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Noise
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
