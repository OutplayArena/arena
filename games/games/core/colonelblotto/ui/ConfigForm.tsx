import { useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { buildBattlefields } from "@frontend/components/utils";
import { useGameConfig } from "@frontend/hooks/useGameConfig";
import { LobbyConfigShell } from "@frontend/components/LobbyConfigShell";
import { inputClass } from "@frontend/components/formStyles";

interface Props {
  gameSlug: string;
  locked: boolean;
  sessionStatus?: string;
  initialValues?: Record<string, unknown>;
}

export default function BlottoConfigForm({ gameSlug, locked, sessionStatus, initialValues }: Props) {
  const [searchParams] = useSearchParams();
  const roundsRef = useRef<HTMLInputElement>(null);
  const fieldsRef = useRef<HTMLInputElement>(null);
  const resourcesRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);

  const { players, setPlayers, agents, remoteKeys,
    status, running, isReplay, formDisabled, handleStartGame } =
    useGameConfig({ gameSlug, locked, sessionStatus, initialValues,
      defaultAgents: ["interactive", "remote"] });

  // Pre-populate from URL params
  const defaultRounds = searchParams.get("rounds") ?? "10";
  const defaultFields = searchParams.get("fields") ?? "5";
  const defaultResources = searchParams.get("resources") ?? "100";

  const onSubmit = (e: React.FormEvent) => {
    const numFields = Number(fieldsRef.current?.value ?? 5);
    const totalResources = Number(resourcesRef.current?.value ?? 100);

    if (totalResources < numFields) {
      e.preventDefault();
      return;
    }

    return handleStartGame(e, () => ({
      variant: "classic",
      budget: [totalResources, totalResources] as [number, number],
      battlefields: buildBattlefields(numFields),
      rounds: Number(roundsRef.current?.value ?? 10),
      seed: seedRef.current?.value ? Number(seedRef.current.value) : null,
    }), () => ({ numFields, totalResources }));
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
        Rounds
        <input ref={roundsRef} type="number" min={1} max={50} defaultValue={defaultRounds} className={inputClass} disabled={formDisabled} />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Battlefields
          <input ref={fieldsRef} type="number" min={2} max={20} defaultValue={defaultFields} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Resources
          <input ref={resourcesRef} type="number" min={1} max={1000} defaultValue={defaultResources} className={inputClass} disabled={formDisabled} />
        </label>
      </div>
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Seed (optional)
        <input ref={seedRef} type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
      </label>
    </LobbyConfigShell>
  );
}
