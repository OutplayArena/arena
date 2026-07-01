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

export default function BattleOfSexesConfigForm({ gameSlug, locked, sessionStatus, initialValues }: Props) {
  const roundsRef = useRef<HTMLInputElement>(null);
  const optionARef = useRef<HTMLInputElement>(null);
  const optionBRef = useRef<HTMLInputElement>(null);
  const prefARef = useRef<HTMLInputElement>(null);
  const prefBRef = useRef<HTMLInputElement>(null);
  const nonPrefRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);

  const { players, setPlayers, agents, remoteKeys,
    status, running, isReplay, formDisabled, handleStartGame } =
    useGameConfig({ gameSlug, locked, sessionStatus, initialValues,
      defaultAgents: ["interactive", "remote"] });

  const onSubmit = (e: React.FormEvent) =>
    handleStartGame(e, () => ({
      variant: "classic",
      rounds: Number(roundsRef.current?.value ?? 10),
      option_a_label: optionARef.current?.value || "opera",
      option_b_label: optionBRef.current?.value || "football",
      payoff_preferred_a: Number(prefARef.current?.value ?? 3),
      payoff_preferred_b: Number(prefBRef.current?.value ?? 3),
      payoff_nonpreferred: Number(nonPrefRef.current?.value ?? 2),
      payoff_mismatch: 0,
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
        Rounds
        <input ref={roundsRef} type="number" min={1} max={100} defaultValue={10} className={inputClass} disabled={formDisabled} />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Option A label
          <input ref={optionARef} type="text" defaultValue="opera" className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Option B label
          <input ref={optionBRef} type="text" defaultValue="football" className={inputClass} disabled={formDisabled} />
        </label>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Payoff A wins
          <input ref={prefARef} type="number" step="0.5" defaultValue={3} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Payoff B wins
          <input ref={prefBRef} type="number" step="0.5" defaultValue={3} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Payoff coord
          <input ref={nonPrefRef} type="number" step="0.5" defaultValue={2} className={inputClass} disabled={formDisabled} />
        </label>
      </div>
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Seed (optional)
        <input ref={seedRef} type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
      </label>
    </LobbyConfigShell>
  );
}
