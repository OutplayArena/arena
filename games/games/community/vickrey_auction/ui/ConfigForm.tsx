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

export default function VickreyAuctionConfigForm({ gameSlug, locked, sessionStatus, initialValues }: Props) {
  const roundsRef = useRef<HTMLInputElement>(null);
  const valueMinRef = useRef<HTMLInputElement>(null);
  const valueMaxRef = useRef<HTMLInputElement>(null);
  const maxBidRef = useRef<HTMLInputElement>(null);
  const seedRef = useRef<HTMLInputElement>(null);

  const { players, setPlayers, agents, remoteKeys,
    status, running, isReplay, formDisabled, handleStartGame, wandbLogging } =
    useGameConfig({ gameSlug, locked, sessionStatus, initialValues,
      defaultAgents: ["interactive", "remote"],
      minPlayers: 2, maxPlayers: 8 });

  const onSubmit = (e: React.FormEvent) =>
    handleStartGame(e, () => ({
      rounds: Number(roundsRef.current?.value ?? 10),
      value_min: Number(valueMinRef.current?.value ?? 0),
      value_max: Number(valueMaxRef.current?.value ?? 100),
      max_bid: Number(maxBidRef.current?.value ?? 200),
      seed: seedRef.current?.value ? Number(seedRef.current.value) : null,
    }));

  return (
    <LobbyConfigShell
      players={players} onPlayersChange={setPlayers}
      agents={agents} remoteKeys={remoteKeys}
      onStartGame={onSubmit}
      disabled={formDisabled} running={running}
      isReplay={isReplay} locked={locked} status={status}
      wandbLogging={wandbLogging}
      minPlayers={2} maxPlayers={8}
    >
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Rounds
        <input ref={roundsRef} type="number" min={1} max={100} defaultValue={10} className={inputClass} disabled={formDisabled} />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Value min
          <input ref={valueMinRef} type="number" step="1" min={0} defaultValue={0} className={inputClass} disabled={formDisabled} />
        </label>
        <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
          Value max
          <input ref={valueMaxRef} type="number" step="1" min={1} defaultValue={100} className={inputClass} disabled={formDisabled} />
        </label>
      </div>
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Max bid (bid ceiling)
        <input ref={maxBidRef} type="number" step="1" min={1} defaultValue={200} className={inputClass} disabled={formDisabled} />
      </label>
      <label className="grid gap-1 text-[10px] font-extrabold text-muted uppercase tracking-wider">
        Seed (optional)
        <input ref={seedRef} type="number" className={inputClass} disabled={formDisabled} placeholder="Random" />
      </label>
    </LobbyConfigShell>
  );
}
